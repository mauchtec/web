import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from typing import Iterable

from django.utils import timezone

from django.conf import settings
from PIL import Image, ImageOps, ImageStat

logger = logging.getLogger(__name__)


class PhotoQualityError(Exception):
    pass


@dataclass(frozen=True)
class PhotoQualityResult:
    score: int
    width: int
    height: int
    resolution_score: int
    sharpness_score: int
    exposure_score: int
    contrast_score: int
    aspect_score: int
    mean_brightness: float
    edge_strength: float
    spoof_risk_score: int
    spoof_artifact_flags: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def threshold(self) -> int:
        value = getattr(settings, "PERSON_PHOTO_MIN_QUALITY_SCORE", 70) or 70
        try:
            return int(value)
        except Exception:
            return 70

    @property
    def is_acceptable(self) -> bool:
        return self.score >= self.threshold and self.spoof_risk_score < self.spoof_reject_threshold

    @property
    def spoof_review_threshold(self) -> int:
        value = getattr(settings, "PERSON_PHOTO_SPOOF_REVIEW_THRESHOLD", 45) or 45
        try:
            return int(value)
        except Exception:
            return 45

    @property
    def spoof_reject_threshold(self) -> int:
        value = getattr(settings, "PERSON_PHOTO_SPOOF_REJECT_THRESHOLD", 70) or 70
        try:
            return int(value)
        except Exception:
            return 70

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "threshold": self.threshold,
            "is_acceptable": self.is_acceptable,
            "width": self.width,
            "height": self.height,
            "resolution_score": self.resolution_score,
            "sharpness_score": self.sharpness_score,
            "exposure_score": self.exposure_score,
            "contrast_score": self.contrast_score,
            "aspect_score": self.aspect_score,
            "mean_brightness": round(self.mean_brightness, 2),
            "edge_strength": round(self.edge_strength, 2),
            "spoof_risk_score": self.spoof_risk_score,
            "spoof_artifact_flags": list(self.spoof_artifact_flags),
            "spoof_review_threshold": self.spoof_review_threshold,
            "spoof_reject_threshold": self.spoof_reject_threshold,
            "reasons": list(self.reasons),
        }


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def _resample_filter():
    return getattr(Image, "Resampling", Image).BILINEAR


def _crop_to_portrait(image, target_ratio: float = 4 / 5, top_bias: float = 0.20):
    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    current_ratio = width / height
    if abs(current_ratio - target_ratio) <= 0.05:
        return image

    if current_ratio > target_ratio:
        new_width = int(round(height * target_ratio))
        left = max(0, (width - new_width) // 2)
        right = left + new_width
        return image.crop((left, 0, right, height))

    new_height = int(round(width / target_ratio))
    if new_height >= height:
        return image
    top = max(0, int(round((height - new_height) * max(0.0, min(0.8, top_bias)))))
    bottom = top + new_height
    if bottom > height:
        bottom = height
        top = max(0, bottom - new_height)
    return image.crop((0, top, width, bottom))


def _photo_crop_settings() -> tuple[float, float]:
    target_ratio = float(getattr(settings, "PERSON_PHOTO_CROP_RATIO", 0.72) or 0.72)
    top_bias = float(getattr(settings, "PERSON_PHOTO_CROP_TOP_BIAS", 0.20) or 0.20)
    return max(0.5, min(1.0, target_ratio)), max(0.0, min(0.8, top_bias))


def _photo_max_upload_bytes() -> int:
    value = getattr(settings, "PERSON_PHOTO_MAX_UPLOAD_BYTES", 4_800_000) or 4_800_000
    try:
        return max(512_000, int(value))
    except Exception:
        return 4_800_000


def _photo_max_dimension() -> int:
    value = getattr(settings, "PERSON_PHOTO_MAX_DIMENSION", 1600) or 1600
    try:
        return max(640, int(value))
    except Exception:
        return 1600


def _encode_normalized_jpeg(image, *, filename: str) -> bytes:
    max_bytes = _photo_max_upload_bytes()
    max_dimension = _photo_max_dimension()
    working = image.copy()

    if max(working.size) > max_dimension:
        working.thumbnail((max_dimension, max_dimension), _resample_filter())

    quality_steps = (92, 88, 84, 80, 76, 72)
    min_dimension = 640

    while True:
        for quality in quality_steps:
            output = BytesIO()
            working.save(output, format="JPEG", quality=quality, optimize=True)
            data = output.getvalue()
            if len(data) <= max_bytes:
                return data

        width, height = working.size
        next_width = max(min_dimension, int(round(width * 0.85)))
        next_height = max(min_dimension, int(round(height * 0.85)))
        if next_width >= width and next_height >= height:
            return data
        if width <= min_dimension or height <= min_dimension:
            return data
        working = working.resize((next_width, next_height), _resample_filter())


def describe_uploaded_photo(image_file) -> dict:
    if image_file is None:
        raise PhotoQualityError("An image is required.")

    filename = str(getattr(image_file, "name", "") or "upload.jpg")
    content_type = str(getattr(image_file, "content_type", "") or "")
    size_bytes = int(getattr(image_file, "size", 0) or 0)
    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass
    try:
        with Image.open(image_file) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            format_name = str(getattr(image, "format", "") or "").upper()
            dpi = image.info.get("dpi") or image.info.get("resolution") or ()
            if isinstance(dpi, (list, tuple)) and len(dpi) >= 2:
                dpi_x = int(round(float(dpi[0] or 0)))
                dpi_y = int(round(float(dpi[1] or 0)))
            else:
                dpi_x = 0
                dpi_y = 0
    except Exception as exc:
        raise PhotoQualityError(f"Unable to inspect image: {exc}") from exc
    finally:
        if hasattr(image_file, "seek"):
            try:
                image_file.seek(0)
            except Exception:
                pass

    return {
        "filename": filename,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "width": width,
        "height": height,
        "format": format_name,
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
    }


def normalize_photo_upload(image_file, *, filename: str | None = None) -> ContentFile:
    if image_file is None:
        raise PhotoQualityError("An image is required.")

    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass

    try:
        with Image.open(image_file) as image:
            image = ImageOps.exif_transpose(image)
            target_ratio, top_bias = _photo_crop_settings()
            image = _crop_to_portrait(image, target_ratio=target_ratio, top_bias=top_bias)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            elif image.mode == "L":
                image = image.convert("RGB")
            normalized_name = filename or getattr(image_file, "name", "") or f"photo-{uuid4().hex}.jpg"
            data = _encode_normalized_jpeg(image, filename=normalized_name)
    except Exception as exc:
        raise PhotoQualityError(f"Unable to normalize image: {exc}") from exc
    finally:
        if hasattr(image_file, "seek"):
            try:
                image_file.seek(0)
            except Exception:
                pass

    if not data:
        raise PhotoQualityError("Unable to normalize image.")

    normalized_name = filename or getattr(image_file, "name", "") or f"photo-{uuid4().hex}.jpg"
    normalized_stem = Path(str(normalized_name)).stem or f"photo-{uuid4().hex}"
    return ContentFile(data, name=f"{normalized_stem}.jpg")


def save_photo_debug_copy(image_file, *, prefix: str = "person-photo") -> str:
    debug_enabled = bool(getattr(settings, "PERSON_PHOTO_DEBUG_SAVE", True))
    if not debug_enabled:
        return ""

    normalized = normalize_photo_upload(image_file)
    safe_prefix = "".join(ch for ch in str(prefix or "person-photo") if ch.isalnum() or ch in ("-", "_")).strip("-_") or "person-photo"
    debug_path = f"debug/person_photos/{safe_prefix}-{uuid4().hex}.jpg"
    saved_path = default_storage.save(debug_path, normalized)
    logger.info("Saved photo debug copy to %s", saved_path)
    return saved_path


def _resolution_score(width: int, height: int) -> int:
    min_dim = min(width, height)
    if min_dim >= 1600:
        return 100
    if min_dim >= 1200:
        return 92
    if min_dim >= 1024:
        return 85
    if min_dim >= 800:
        return 76
    if min_dim >= 640:
        return 64
    if min_dim >= 480:
        return 50
    if min_dim >= 360:
        return 36
    return max(0, int((min_dim / 360) * 36))


def _aspect_score(width: int, height: int) -> int:
    if width <= 0 or height <= 0:
        return 0
    ratio = max(width, height) / min(width, height)
    if ratio <= 1.25:
        return 100
    if ratio <= 1.5:
        return 92
    if ratio <= 1.9:
        return 82
    if ratio <= 2.4:
        return 68
    return 48


def _edge_strength(gray_pixels: Iterable[int], width: int, height: int) -> float:
    pixels = list(gray_pixels)
    if not pixels or width < 2 or height < 2:
        return 0.0

    total = 0
    count = 0

    for y in range(height):
        row_offset = y * width
        for x in range(width - 1):
            total += abs(pixels[row_offset + x] - pixels[row_offset + x + 1])
            count += 1

    for y in range(height - 1):
        row_offset = y * width
        for x in range(width):
            total += abs(pixels[row_offset + x] - pixels[row_offset + x + width])
            count += 1

    return (total / count) if count else 0.0


def _blur_score(edge_strength: float) -> int:
    return _clamp(edge_strength * 10.0)


def _exposure_score(mean_brightness: float) -> int:
    # 128 is neutral for an 8-bit grayscale image.
    return _clamp(100 - (abs(mean_brightness - 128.0) * 1.25))


def _contrast_score(stddev: float) -> int:
    return _clamp(stddev * 2.4)


def _band_stats(gray_image, top_ratio: float, bottom_ratio: float):
    width, height = gray_image.size
    top = max(0, min(height - 1, int(round(height * top_ratio))))
    bottom = max(top + 1, min(height, int(round(height * bottom_ratio))))
    band = gray_image.crop((0, top, width, bottom))
    stat = ImageStat.Stat(band)
    mean = float(stat.mean[0]) if stat.mean else 0.0
    stddev = float(stat.stddev[0]) if stat.stddev else 0.0
    pixels = list(band.getdata())
    total = len(pixels) or 1
    bright_ratio = sum(1 for px in pixels if px >= 225) / total
    dark_ratio = sum(1 for px in pixels if px <= 55) / total
    return {
        "mean": mean,
        "stddev": stddev,
        "bright_ratio": bright_ratio,
        "dark_ratio": dark_ratio,
    }


def _row_mean_transitions(gray_image) -> float:
    width, height = gray_image.size
    if width <= 0 or height <= 1:
        return 0.0
    rows = []
    for y in range(height):
        row = gray_image.crop((0, y, width, y + 1))
        stat = ImageStat.Stat(row)
        rows.append(float(stat.mean[0]) if stat.mean else 0.0)
    jumps = [abs(rows[idx + 1] - rows[idx]) for idx in range(len(rows) - 1)]
    return max(jumps) if jumps else 0.0


def _alternating_pattern_score(gray_image) -> float:
    width, height = gray_image.size
    pixels = list(gray_image.getdata())
    if width < 4 or height < 4 or not pixels:
        return 0.0

    flips = 0
    comparisons = 0
    for y in range(0, height, 2):
        row_offset = y * width
        last_sign = 0
        for x in range(width - 1):
            delta = pixels[row_offset + x + 1] - pixels[row_offset + x]
            sign = 1 if delta > 3 else (-1 if delta < -3 else 0)
            if sign == 0:
                continue
            if last_sign and sign != last_sign:
                flips += 1
            last_sign = sign
            comparisons += 1

    for x in range(0, width, 2):
        last_sign = 0
        for y in range(height - 1):
            delta = pixels[(y + 1) * width + x] - pixels[y * width + x]
            sign = 1 if delta > 3 else (-1 if delta < -3 else 0)
            if sign == 0:
                continue
            if last_sign and sign != last_sign:
                flips += 1
            last_sign = sign
            comparisons += 1

    if comparisons <= 0:
        return 0.0
    return min(1.0, flips / comparisons)


def _screen_spoof_signals(image) -> tuple[int, tuple[str, ...]]:
    rgb = image.convert("RGB").resize((192, 192), _resample_filter())
    gray = rgb.convert("L")

    flags: list[str] = []
    risk = 0.0

    top_band = _band_stats(gray, 0.0, 0.10)
    upper_band = _band_stats(gray, 0.10, 0.25)
    full_stat = ImageStat.Stat(gray)
    mean_brightness = float(full_stat.mean[0]) if full_stat.mean else 0.0

    if (
        top_band["dark_ratio"] >= 0.35
        and top_band["bright_ratio"] >= 0.01
        and upper_band["mean"] >= top_band["mean"] + 20
    ):
        flags.append("screen_ui_bar")
        risk += 38

    row_jump = _row_mean_transitions(gray)
    if row_jump >= 35 and top_band["mean"] + 12 < upper_band["mean"]:
        flags.append("screen_boundary")
        risk += 18

    alternating = _alternating_pattern_score(gray)
    if alternating >= 0.58:
        flags.append("moire_pattern")
        risk += 24
    elif alternating >= 0.48:
        flags.append("pixel_grid_pattern")
        risk += 14

    bright_pixels = list(gray.getdata())
    bright_ratio = sum(1 for px in bright_pixels if px >= 248) / (len(bright_pixels) or 1)
    if bright_ratio >= 0.07 and mean_brightness >= 120:
        flags.append("screen_glare")
        risk += 12

    if top_band["stddev"] <= 32 and top_band["dark_ratio"] >= 0.25 and upper_band["stddev"] >= top_band["stddev"] + 8:
        flags.append("flat_panel_header")
        risk += 10

    return _clamp(risk), tuple(dict.fromkeys(flags))




def assess_photo_quality(image_file) -> PhotoQualityResult:
    if image_file is None:
        raise PhotoQualityError("An image is required.")

    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass

    try:
        with Image.open(image_file) as image:
            image = ImageOps.exif_transpose(image)
            target_ratio, top_bias = _photo_crop_settings()
            image = _crop_to_portrait(image, target_ratio=target_ratio, top_bias=top_bias)
            width, height = image.size
            if width <= 0 or height <= 0:
                raise PhotoQualityError("Invalid image dimensions.")

            gray = image.convert("L").resize((128, 128), _resample_filter())
            stat = ImageStat.Stat(gray)
            mean_brightness = float(stat.mean[0]) if stat.mean else 0.0
            contrast_stddev = float(stat.stddev[0]) if stat.stddev else 0.0
            edge_strength = _edge_strength(gray.getdata(), gray.size[0], gray.size[1])

            resolution_score = _resolution_score(width, height)
            aspect_score = _aspect_score(width, height)
            sharpness_score = _blur_score(edge_strength)
            exposure_score = _exposure_score(mean_brightness)
            contrast_score = _contrast_score(contrast_stddev)
            spoof_risk_score, spoof_artifact_flags = _screen_spoof_signals(image)

            score = _clamp(
                (resolution_score * 0.24)
                + (sharpness_score * 0.40)
                + (exposure_score * 0.16)
                + (contrast_score * 0.10)
                + (aspect_score * 0.10)
            )

            reasons = []
            if resolution_score < 60:
                reasons.append("Image resolution is too low.")
            if sharpness_score < 55:
                reasons.append("Image is blurry.")
            if exposure_score < 45:
                reasons.append("Image is too dark or too bright.")
            if contrast_score < 35:
                reasons.append("Image contrast is too flat.")
            if aspect_score < 60:
                reasons.append("Image framing is poor for face enrollment.")
            if spoof_risk_score >= getattr(settings, "PERSON_PHOTO_SPOOF_REJECT_THRESHOLD", 70):
                reasons.append("Possible screen, printed photo, or replay attack detected.")
            elif spoof_risk_score >= getattr(settings, "PERSON_PHOTO_SPOOF_REVIEW_THRESHOLD", 45):
                reasons.append("Image shows possible display or replay artifacts.")
            if score < getattr(settings, "PERSON_PHOTO_MIN_QUALITY_SCORE", 70):
                reasons.append(
                    f"Overall quality is {score}%, below the minimum required {getattr(settings, 'PERSON_PHOTO_MIN_QUALITY_SCORE', 70)}%."
                )

            return PhotoQualityResult(
                score=score,
                width=width,
                height=height,
                resolution_score=resolution_score,
                sharpness_score=sharpness_score,
                exposure_score=exposure_score,
                contrast_score=contrast_score,
                aspect_score=aspect_score,
                mean_brightness=mean_brightness,
                edge_strength=edge_strength,
                spoof_risk_score=spoof_risk_score,
                spoof_artifact_flags=spoof_artifact_flags,
                reasons=tuple(dict.fromkeys(reasons)),
            )
    except PhotoQualityError:
        raise
    except Exception as exc:
        raise PhotoQualityError(f"Unable to assess photo quality: {exc}") from exc
    finally:
        if hasattr(image_file, "seek"):
            try:
                image_file.seek(0)
            except Exception:
                pass


def build_photo_analysis_report(*, person, uploaded_meta: dict, quality: PhotoQualityResult, reviewer_name: str = "", face_count: int | None = None, similarity_percent: float | None = None, match_subject: str = "") -> dict:
    size_bytes = int(uploaded_meta.get("size_bytes") or 0)
    width = int(uploaded_meta.get("width") or 0)
    height = int(uploaded_meta.get("height") or 0)
    dpi_x = int(uploaded_meta.get("dpi_x") or 0)
    dpi_y = int(uploaded_meta.get("dpi_y") or 0)
    quality_score = int(getattr(quality, "score", 0) or 0)
    file_size_kb = max(1, int(round(size_bytes / 1024))) if size_bytes else 0
    labels = []
    if face_count == 1:
        labels.extend([
            {"label": "Face", "confidence": 100},
            {"label": "Head", "confidence": 99},
            {"label": "Person", "confidence": 99},
            {"label": "Portrait", "confidence": min(100, max(85, quality_score))},
        ])
    elif face_count == 0:
        labels.append({"label": "Face", "confidence": 0})
    else:
        labels.append({"label": "Face", "confidence": 100})
        labels.append({"label": "Multiple Faces", "confidence": 100})

    confidence = similarity_percent if similarity_percent is not None else quality_score
    if confidence is None:
        confidence = 0

    logged_at = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    photo_text = f"{getattr(person, 'full_name', '')} - {getattr(person, 'phone', '')}".strip(" -")
    file_size_text = f"{file_size_kb}KB" if file_size_kb else ""
    format_text = uploaded_meta.get("format") or ""
    resolution_text = f"{dpi_x}(PPI)x{dpi_y}(PPI)" if dpi_x and dpi_y else ""
    dimensions_text = f"{width}(w) * {height}(h)" if width and height else ""
    confidence_text = f"{int(round(confidence))}%" if confidence else ""

    return {
        "photo_type": "Contact",
        "Photo Type": "Contact",
        "contact": f"{getattr(person, 'full_name', '')} {getattr(person, 'phone', '')}".strip(),
        "Contact": f"{getattr(person, 'full_name', '')} {getattr(person, 'phone', '')}".strip(),
        "creation_date": logged_at,
        "Creation Date": logged_at,
        "date_logged": logged_at,
        "Date Logged": logged_at,
        "photo_text": photo_text,
        "Photo Text": photo_text,
        "user": reviewer_name or "Admin",
        "User": reviewer_name or "Admin",
        "file_size": file_size_text,
        "File Size": file_size_text,
        "file_format": format_text,
        "File Format": format_text,
        "resolution": resolution_text,
        "Resolution": resolution_text,
        "dimensions": dimensions_text,
        "Dimensions": dimensions_text,
        "confidence": confidence_text,
        "Confidence": confidence_text,
        "quality_score": quality_score,
        "spoof_risk_score": int(getattr(quality, "spoof_risk_score", 0) or 0),
        "spoof_artifact_flags": list(getattr(quality, "spoof_artifact_flags", ()) or ()),
        "face_count": face_count if face_count is not None else "",
        "Face Count": face_count if face_count is not None else "",
        "match_subject": match_subject or "",
        "Match Subject": match_subject or "",
        "object_detection_labels": labels,
        "Object Detection Labels": labels,
        "analysis_notes": [
            "Quality score covers resolution, sharpness, exposure, contrast, and framing.",
            "Face count confirms the image contains exactly one face before identity matching.",
            "Identity confidence comes from similarity when an approved reference exists.",
            "Spoof risk flags try to detect screen, print, or replay artifacts before approval.",
        ],
    }
