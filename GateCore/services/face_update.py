"""Service layer for face verification updates.

Handles the logic of comparing a new face image to the primary reference,
applying thresholds, rate limiting, and creating audit logs.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone

from GateCore.models import Person
from GateCore.models.face_verification import FaceReference, FaceVerificationLog
from GateCore.services.compreface_client import (
    CompreFaceError,
    ensure_single_face_present,
    has_compreface_verification_config,
    is_compreface_configured,
    is_detection_service_unavailable_error,
    verify_images,
)
from GateCore.services.photo_quality import PhotoQualityError, assess_photo_quality


def _get_threshold(name: str, default: float) -> float:
    return float(getattr(settings, name, default))


def _get_int_threshold(name: str, default: int) -> int:
    try:
        return int(getattr(settings, name, default))
    except Exception:
        return default


def _get_client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _get_device_info(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")


def _check_rate_limit(person: Person) -> bool:
    """Return True if the person is within the rate limit."""
    max_attempts = int(getattr(settings, "FACE_UPDATE_RATE_LIMIT", 3))
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent = FaceVerificationLog.objects.filter(
        person=person,
        action="update_face",
        created_at__gte=one_hour_ago,
    ).count()
    return recent < max_attempts


def get_primary_reference(person: Person):
    """Return the primary FaceReference for a person, or None."""
    return (
        FaceReference.objects.filter(
            person=person,
            role="primary",
            is_deleted=False,
        )
        .order_by("-created_at")
        .first()
    )


def _log_event(person, action, result, similarity, request, face_ref=None, details=""):
    return FaceVerificationLog.objects.create(
        person=person,
        action=action,
        result=result,
        similarity_score=Decimal(str(round(similarity, 2))) if similarity is not None else None,
        ip_address=_get_client_ip(request),
        device_info=_get_device_info(request),
        face_reference=face_ref,
        details=details,
    )


def enroll_primary_face(person: Person, image_file, request) -> dict:
    """Store the first face image as primary reference (no comparison needed).
    Quality check and face detection still required."""

    # Quality check
    try:
        quality = assess_photo_quality(image_file)
    except PhotoQualityError as exc:
        _log_event(person, "enroll", "rejected", None, request, details=str(exc))
        return {"status": "rejected", "reason": str(exc)}

    if quality.spoof_risk_score >= _get_int_threshold("PERSON_PHOTO_SPOOF_REJECT_THRESHOLD", 70):
        msg = "Possible screen, printed photo, or replay attack detected."
        _log_event(person, "enroll", "rejected", None, request, details=f"{msg} risk={quality.spoof_risk_score} flags={','.join(quality.spoof_artifact_flags)}")
        return {"status": "rejected", "reason": msg, "quality_score": quality.score, "spoof_risk_score": quality.spoof_risk_score}

    if not quality.is_acceptable:
        msg = f"Photo quality {quality.score}% is below the minimum required {quality.threshold}%."
        _log_event(person, "enroll", "rejected", None, request, details=msg)
        return {"status": "rejected", "reason": msg}

    # Face detection
    try:
        ensure_single_face_present(image_file)
    except CompreFaceError as exc:
        if not is_detection_service_unavailable_error(str(exc)):
            _log_event(person, "enroll", "rejected", None, request, details=str(exc))
            return {"status": "rejected", "reason": str(exc)}

    # Save as primary reference
    face_ref = FaceReference.objects.create(
        person=person,
        image=image_file,
        role="primary",
        quality_score=Decimal(str(quality.score)),
    )

    _log_event(person, "enroll", "approved", None, request, face_ref=face_ref,
               details="First face image saved as primary reference.")

    return {
        "status": "approved",
        "message": "First face image saved as reference.",
        "face_reference_id": str(face_ref.id),
        "quality_score": quality.score,
    }


def request_face_update(person: Person, image_file, request) -> dict:
    """Compare a new face image to the primary reference.
    Returns the comparison result and next steps."""

    # Rate limit
    if not _check_rate_limit(person):
        return {
            "status": "rate_limited",
            "message": "Too many face update attempts. Try again later.",
        }

    # Check primary reference exists
    primary = get_primary_reference(person)
    if not primary:
        return enroll_primary_face(person, image_file, request)

    # Quality check
    try:
        quality = assess_photo_quality(image_file)
    except PhotoQualityError as exc:
        _log_event(person, "update_face", "rejected", None, request, details=str(exc))
        return {"status": "rejected", "reason": str(exc)}

    spoof_review_threshold = _get_int_threshold("PERSON_PHOTO_SPOOF_REVIEW_THRESHOLD", 45)
    spoof_reject_threshold = _get_int_threshold("PERSON_PHOTO_SPOOF_REJECT_THRESHOLD", 70)

    if quality.spoof_risk_score >= spoof_reject_threshold:
        msg = "Possible screen, printed photo, or replay attack detected."
        _log_event(person, "update_face", "rejected", None, request, details=f"{msg} risk={quality.spoof_risk_score} flags={','.join(quality.spoof_artifact_flags)}")
        return {"status": "rejected", "reason": msg, "quality_score": quality.score, "spoof_risk_score": quality.spoof_risk_score}

    if not quality.is_acceptable:
        msg = f"Photo quality {quality.score}% is below the minimum required {quality.threshold}%."
        _log_event(person, "update_face", "rejected", None, request, details=msg)
        return {"status": "rejected", "reason": msg}

    # Face detection
    try:
        ensure_single_face_present(image_file)
    except CompreFaceError as exc:
        if not is_detection_service_unavailable_error(str(exc)):
            _log_event(person, "update_face", "rejected", None, request, details=str(exc))
            return {"status": "rejected", "reason": str(exc)}

    # Compare to primary reference via CompreFace verification
    if not has_compreface_verification_config():
        _log_event(person, "update_face", "error", None, request,
                   details="CompreFace verification service not configured.")
        return {"status": "error", "message": "Face verification service not available."}

    try:
        primary.image.open()
        result = verify_images(primary.image, image_file)
    except CompreFaceError as exc:
        _log_event(person, "update_face", "error", None, request, details=str(exc))
        return {"status": "error", "message": f"Verification failed: {exc}"}
    finally:
        try:
            primary.image.close()
        except Exception:
            pass

    # Extract similarity — CompreFace verify returns result[].face_matches[].similarity
    similarity = _extract_similarity(result)
    if similarity is None:
        _log_event(person, "update_face", "error", None, request,
                   details=f"Could not extract similarity from CompreFace response: {result}")
        return {"status": "error", "message": "Could not determine face similarity."}

    similarity_pct = similarity * 100.0  # CompreFace returns 0-1

    verification_threshold = _get_threshold("FACE_VERIFICATION_THRESHOLD", 90.0)
    review_threshold = _get_threshold("FACE_REVIEW_THRESHOLD", 80.0)

    if similarity_pct >= verification_threshold and quality.spoof_risk_score >= spoof_review_threshold:
        face_ref = FaceReference.objects.create(
            person=person,
            image=image_file,
            role="pending",
            quality_score=Decimal(str(quality.score)),
            similarity_to_primary=Decimal(str(round(similarity_pct, 2))),
            notes=f"Spoof review required. risk={quality.spoof_risk_score} flags={','.join(quality.spoof_artifact_flags)}",
        )
        _log_event(person, "update_face", "needs_review", similarity_pct, request,
                   face_ref=face_ref, details=f"Similarity passed but spoof review required. risk={quality.spoof_risk_score} flags={','.join(quality.spoof_artifact_flags)}")
        return {
            "status": "needs_review",
            "similarity": round(similarity_pct, 2),
            "face_reference_id": str(face_ref.id),
            "message": "Image matched the face reference but looks like a possible replay or screen capture. Admin review is required.",
            "quality_score": quality.score,
            "spoof_risk_score": quality.spoof_risk_score,
        }

    if similarity_pct >= verification_threshold:
        # Save as pending — will become verified after step-up auth
        face_ref = FaceReference.objects.create(
            person=person,
            image=image_file,
            role="pending",
            quality_score=Decimal(str(quality.score)),
            similarity_to_primary=Decimal(str(round(similarity_pct, 2))),
        )
        _log_event(person, "update_face", "approved", similarity_pct, request,
                   face_ref=face_ref, details="Above verification threshold. Awaiting step-up auth.")
        return {
            "status": "approved",
            "similarity": round(similarity_pct, 2),
            "face_reference_id": str(face_ref.id),
            "message": "Face matches. Please confirm with OTP to finalize.",
            "requires_otp": True,
            "quality_score": quality.score,
            "spoof_risk_score": quality.spoof_risk_score,
        }

    if similarity_pct >= review_threshold:
        face_ref = FaceReference.objects.create(
            person=person,
            image=image_file,
            role="pending",
            quality_score=Decimal(str(quality.score)),
            similarity_to_primary=Decimal(str(round(similarity_pct, 2))),
        )
        _log_event(person, "update_face", "needs_review", similarity_pct, request,
                   face_ref=face_ref, details="Between review and verification threshold.")
        return {
            "status": "needs_review",
            "similarity": round(similarity_pct, 2),
            "face_reference_id": str(face_ref.id),
            "message": "Additional verification required. An admin will review.",
            "quality_score": quality.score,
            "spoof_risk_score": quality.spoof_risk_score,
        }

    # Below review threshold — reject
    _log_event(person, "update_face", "rejected", similarity_pct, request,
               details="Below review threshold.")
    return {
        "status": "rejected",
        "similarity": round(similarity_pct, 2),
        "message": "Face does not match reference.",
        "quality_score": quality.score,
        "spoof_risk_score": quality.spoof_risk_score,
    }


def confirm_face_update(person: Person, face_reference_id: str, request) -> dict:
    """Finalize a face update after step-up auth (OTP verified).
    Promotes the pending reference to 'verified'."""

    try:
        face_ref = FaceReference.objects.get(
            id=face_reference_id,
            person=person,
            role="pending",
            is_deleted=False,
        )
    except FaceReference.DoesNotExist:
        return {"status": "error", "message": "Pending face update not found."}

    face_ref.role = "verified"
    face_ref.save(update_fields=["role", "modified_at"])

    # Update person's photo to the new verified image (keep original reference intact)
    person.photo = face_ref.image
    person.photo_review_status = "approved"
    person.photo_similarity_score = face_ref.similarity_to_primary
    person.photo_reviewed_at = timezone.now()
    person.save(update_fields=[
        "photo", "photo_review_status", "photo_similarity_score",
        "photo_reviewed_at", "modified_at",
    ])

    _log_event(person, "update_face", "approved", float(face_ref.similarity_to_primary or 0),
               request, face_ref=face_ref, details="Step-up auth passed. Face update confirmed.")

    return {
        "status": "confirmed",
        "face_reference_id": str(face_ref.id),
        "message": "Face updated successfully.",
    }


def admin_resolve_review(person: Person, face_reference_id: str, approve: bool, request, notes: str = "") -> dict:
    """Admin approves or rejects a pending face review."""

    try:
        face_ref = FaceReference.objects.get(
            id=face_reference_id,
            person=person,
            role="pending",
            is_deleted=False,
        )
    except FaceReference.DoesNotExist:
        return {"status": "error", "message": "Pending face review not found."}

    if approve:
        face_ref.role = "verified"
        face_ref.notes = notes
        face_ref.save(update_fields=["role", "notes", "modified_at"])

        person.photo = face_ref.image
        person.photo_review_status = "approved"
        person.photo_similarity_score = face_ref.similarity_to_primary
        person.photo_reviewed_at = timezone.now()
        person.save(update_fields=[
            "photo", "photo_review_status", "photo_similarity_score",
            "photo_reviewed_at", "modified_at",
        ])

        _log_event(person, "admin_review", "approved",
                   float(face_ref.similarity_to_primary or 0), request,
                   face_ref=face_ref, details=f"Admin approved. {notes}".strip())

        return {"status": "approved", "message": "Face update approved by admin."}
    else:
        face_ref.is_deleted = True
        face_ref.deleted_at = timezone.now()
        face_ref.notes = notes
        face_ref.save(update_fields=["is_deleted", "deleted_at", "notes", "modified_at"])

        _log_event(person, "admin_review", "rejected",
                   float(face_ref.similarity_to_primary or 0), request,
                   face_ref=face_ref, details=f"Admin rejected. {notes}".strip())

        return {"status": "rejected", "message": "Face update rejected by admin."}


def cleanup_expired_pending(dry_run: bool = False) -> dict:
    """Remove expired pending FaceReferences and their image files.

    - Rejected (is_deleted=True) references: delete image files immediately
    - Pending references older than FACE_REVIEW_EXPIRY_HOURS: soft-delete + remove images

    Primary and verified references are NEVER deleted.
    Returns a summary dict with counts.
    """
    expiry_hours = int(getattr(settings, "FACE_REVIEW_EXPIRY_HOURS", 48))
    cutoff = timezone.now() - timedelta(hours=expiry_hours)

    # 1) Already soft-deleted references — purge image files
    soft_deleted = FaceReference.objects.filter(is_deleted=True).exclude(role="primary")
    deleted_images = 0
    for ref in soft_deleted:
        if ref.image:
            if not dry_run:
                ref.image.delete(save=False)
            deleted_images += 1
    if not dry_run:
        soft_deleted.update(image="")

    # 2) Expired pending references — soft-delete and purge
    expired_pending = FaceReference.objects.filter(
        role="pending",
        is_deleted=False,
        created_at__lt=cutoff,
    )
    expired_count = expired_pending.count()
    for ref in expired_pending:
        if ref.image and not dry_run:
            ref.image.delete(save=False)
    if not dry_run:
        expired_pending.update(
            is_deleted=True,
            deleted_at=timezone.now(),
            image="",
            notes="Auto-expired: pending review timed out.",
        )

    return {
        "deleted_images": deleted_images,
        "expired_pending": expired_count,
        "dry_run": dry_run,
    }


def _extract_similarity(result: dict):
    """Extract the best similarity score from CompreFace verification response.
    Returns float 0-1 or None."""
    # verify_images response: {"result": [{"face_matches": [{"similarity": 0.95, ...}], ...}]}
    results = result.get("result") or []
    if not results:
        return None
    face_matches = results[0].get("face_matches") or []
    if not face_matches:
        # Fallback: direct similarity field (some CompreFace versions)
        sim = results[0].get("similarity")
        if sim is not None:
            try:
                return float(sim)
            except (TypeError, ValueError):
                return None
        return None
    best = max(face_matches, key=lambda m: float(m.get("similarity") or 0))
    try:
        return float(best.get("similarity"))
    except (TypeError, ValueError):
        return None
