import mimetypes
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests
from django.conf import settings


class CompreFaceError(Exception):
    pass


@dataclass(frozen=True)
class CompreFaceConfig:
    base_url: str
    recognition_api_key: str
    detection_api_key: str
    verification_api_key: str
    recognition_faces_path: str
    timeout_seconds: int = 30

    @property
    def faces_url(self) -> str:
        path = self.recognition_faces_path.strip()
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url.rstrip('/')}{path}"

    def verify_url(self, image_id: str) -> str:
        image_id = str(image_id or "").strip()
        if not image_id:
            raise CompreFaceError("Reference image id is required.")
        return f"{self.faces_url.rstrip('/')}/{image_id}/verify"

    @property
    def detection_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/detection/detect"

    @property
    def verification_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/verification/verify"


def get_compreface_config() -> CompreFaceConfig:
    return CompreFaceConfig(
        base_url=(getattr(settings, "COMPREFACE_BASE_URL", "") or "").rstrip("/"),
        recognition_api_key=(getattr(settings, "COMPREFACE_API_KEY", "") or "").strip(),
        detection_api_key=(getattr(settings, "COMPREFACE_DETECTION_API_KEY", "") or "").strip(),
        verification_api_key=(getattr(settings, "COMPREFACE_VERIFICATION_API_KEY", "") or "").strip(),
        recognition_faces_path=(getattr(settings, "COMPREFACE_RECOGNITION_FACES_PATH", "/api/v1/recognition/faces/") or "/api/v1/recognition/faces/").strip() or "/api/v1/recognition/faces/",
        timeout_seconds=int(getattr(settings, "COMPREFACE_TIMEOUT_SECONDS", 30) or 30),
    )


def is_compreface_configured() -> bool:
    config = get_compreface_config()
    return bool(config.base_url and config.recognition_api_key)


def has_compreface_detection_config() -> bool:
    config = get_compreface_config()
    return bool(config.base_url and config.detection_api_key)


def has_compreface_verification_config() -> bool:
    config = get_compreface_config()
    return bool(config.base_url and config.verification_api_key)


def is_detection_service_unavailable_error(message: str) -> bool:
    text = str(message or "").lower()
    return (
        "detection service with api key" in text
        or "compreface detection failed (404)" in text
        or "code 10" in text
        or "service not found" in text
        or "unable to reach compreface detection service" in text
        or "failed to establish a new connection" in text
        or "actively refused" in text
        or "max retries exceeded with url: /api/v1/detection/detect" in text
    )


def _read_uploaded_bytes(image_file) -> bytes:
    if image_file is None:
        raise CompreFaceError("An image is required.")

    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass

    if hasattr(image_file, "read"):
        data = image_file.read()
    elif isinstance(image_file, (bytes, bytearray)):
        data = bytes(image_file)
    else:
        data = bytes(image_file)

    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass

    if not data:
        raise CompreFaceError("An image is required.")

    return data


def _normalize_base_url(base_url: str) -> tuple[str, int]:
    parsed = urlsplit(base_url if "://" in base_url else f"http://{base_url}")
    scheme = parsed.scheme or "http"
    hostname = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 8000)
    return f"{scheme}://{hostname}:{port}", port


def _build_files(image_file, *, field_name: str = "file"):
    filename = getattr(image_file, "name", "") or "face.jpg"
    content_type = getattr(image_file, "content_type", "") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass
    return {
        field_name: (filename, image_file, content_type),
    }


def enroll_face(subject: str, image_file, *, timeout_seconds: int | None = None) -> dict:
    config = get_compreface_config()
    if not config.base_url:
        raise CompreFaceError("CompreFace base URL is not configured.")
    if not config.recognition_api_key:
        raise CompreFaceError("CompreFace API key is not configured.")

    subject = str(subject or "").strip()
    if not subject:
        raise CompreFaceError("Subject is required.")

    if image_file is None:
        raise CompreFaceError("An image is required.")

    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass

    try:
        response = requests.post(
            config.faces_url,
            headers={"x-api-key": config.recognition_api_key},
            params={"subject": subject},
            files=_build_files(image_file),
            timeout=timeout_seconds or config.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise CompreFaceError(f"Unable to reach CompreFace enrollment service: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text.strip()
        raise CompreFaceError(f"CompreFace enrollment failed ({response.status_code}): {detail[:500]}")

    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def detect_faces(image_file, *, timeout_seconds: int | None = None) -> dict:
    config = get_compreface_config()
    if not config.base_url:
        raise CompreFaceError("CompreFace base URL is not configured.")
    if not config.detection_api_key:
        raise CompreFaceError("CompreFace detection API key is not configured.")

    if image_file is None:
        raise CompreFaceError("An image is required.")

    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass

    try:
        response = requests.post(
            config.detection_url,
            headers={"x-api-key": config.detection_api_key},
            files=_build_files(image_file),
            timeout=timeout_seconds or config.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise CompreFaceError(f"Unable to reach CompreFace detection service: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text.strip()
        raise CompreFaceError(f"CompreFace detection failed ({response.status_code}): {detail[:500]}")

    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def get_face_presence_details(image_file, *, timeout_seconds: int | None = None) -> dict:
    result = detect_faces(image_file, timeout_seconds=timeout_seconds)
    detected = result.get("result") or []
    return {
        "face_count": len(detected),
        "detected_faces": detected,
        "raw": result,
    }


def ensure_single_face_present(image_file, *, timeout_seconds: int | None = None) -> None:
    details = get_face_presence_details(image_file, timeout_seconds=timeout_seconds)
    detected = details.get("detected_faces") or []
    if not detected:
        raise CompreFaceError("No clear face was detected. Upload a front-facing photo with one face only.")
    if len(detected) != 1:
        raise CompreFaceError("Multiple faces were detected. Upload a photo with one face only.")


def ensure_face_present(image_file, *, timeout_seconds: int | None = None) -> None:
    ensure_single_face_present(image_file, timeout_seconds=timeout_seconds)


def verify_against_reference(reference_image_id: str, image_file, *, timeout_seconds: int | None = None) -> dict:
    config = get_compreface_config()
    if not config.base_url:
        raise CompreFaceError("CompreFace base URL is not configured.")
    if not config.recognition_api_key:
        raise CompreFaceError("CompreFace API key is not configured.")

    image_id = str(reference_image_id or "").strip()
    if not image_id:
        raise CompreFaceError("Reference image id is required.")
    if image_file is None:
        raise CompreFaceError("An image is required.")

    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass

    try:
        response = requests.post(
            config.verify_url(image_id),
            headers={"x-api-key": config.recognition_api_key},
            files=_build_files(image_file),
            timeout=timeout_seconds or config.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise CompreFaceError(f"Unable to reach CompreFace verification service: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text.strip()
        raise CompreFaceError(f"CompreFace verification failed ({response.status_code}): {detail[:500]}")

    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def verify_images(source_image, target_image, *, timeout_seconds: int | None = None) -> dict:
    config = get_compreface_config()
    if not config.base_url:
        raise CompreFaceError("CompreFace base URL is not configured.")
    if not config.verification_api_key:
        raise CompreFaceError("CompreFace verification API key is not configured.")
    if source_image is None or target_image is None:
        raise CompreFaceError("Two images are required for verification.")

    if hasattr(source_image, "seek"):
        try:
            source_image.seek(0)
        except Exception:
            pass
    if hasattr(target_image, "seek"):
        try:
            target_image.seek(0)
        except Exception:
            pass

    try:
        response = requests.post(
            config.verification_url,
            headers={"x-api-key": config.verification_api_key},
            files={
                "source_image": _build_files(source_image, field_name="source_image")["source_image"],
                "target_image": _build_files(target_image, field_name="target_image")["target_image"],
            },
            timeout=timeout_seconds or config.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise CompreFaceError(f"Unable to reach CompreFace verification service: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text.strip()
        raise CompreFaceError(f"CompreFace verification failed ({response.status_code}): {detail[:500]}")

    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def extract_best_match(result: dict) -> tuple[float | None, str]:
    responses = result.get("result") or []
    if not responses:
        return None, ""

    face_matches = responses[0].get("face_matches") or []
    if not face_matches:
        return None, ""

    best = max(
        face_matches,
        key=lambda item: float(item.get("similarity") or 0.0),
    )
    similarity = best.get("similarity")
    subject = str(best.get("subject") or "").strip()
    try:
        similarity_value = float(similarity) if similarity is not None else None
    except Exception:
        similarity_value = None
    return similarity_value, subject
