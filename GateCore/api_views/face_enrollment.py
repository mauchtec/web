from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from GateCore.api_views.mutations import _serialize_person
from GateCore.api_views.device_sync import mark_device_sync_pending, queue_face_device_person_sync
from GateCore.api_views.profile import (
    _build_spoof_rejection_message,
    _get_spoof_review_threshold,
    _is_camera_capture_source,
)
from GateCore.models import AuditTrail, Person
from GateCore.services.compreface_client import (
    CompreFaceError,
    enroll_face,
    ensure_single_face_present,
    get_face_presence_details,
    is_compreface_configured,
    is_detection_service_unavailable_error,
)
from GateCore.services.photo_quality import (
    PhotoQualityError,
    assess_photo_quality,
    describe_uploaded_photo,
    normalize_photo_upload,
    save_photo_debug_copy,
)
from GateCore.services.visitor_face_pass import activate_visitor_face_grant_for_person


def _can_enroll_face(request, person: Person) -> bool:
    if request.user.is_staff:
        return True
    person_profile = getattr(request.user, "person_profile", None)
    return bool(person_profile and str(person_profile.id) == str(person.id))


def _set_rejected_enrollment(person: Person, *, message: str, quality_score=None, review_attempt=None) -> None:
    person.face_enrollment_status = "rejected"
    person.face_enrollment_error = message
    person.photo_review_status = "rejected"
    person.photo_review_error = message
    person.photo_reviewed_at = timezone.now()
    if quality_score is not None:
        person.face_enrollment_quality_score = quality_score
    if review_attempt is not None:
        person.photo_review_attempt = review_attempt
    person.save(
        update_fields=[
            "face_enrollment_status",
            "face_enrollment_error",
            "face_enrollment_quality_score",
            "photo_review_status",
            "photo_review_error",
            "photo_review_attempt",
            "photo_reviewed_at",
            "modified_at",
        ]
    )


def _record_enrollment_failure(request, person: Person, message: str) -> None:
    AuditTrail.objects.create(
        person=person,
        action="face_enroll_failed",
        performed_by=request.user if request.user.is_authenticated else None,
        details=message,
    )


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def enroll_person_face(request, person_id):
    person = get_object_or_404(Person, id=person_id)

    if not _can_enroll_face(request, person):
        return Response({"success": False, "error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    image = request.FILES.get("photo") or request.FILES.get("image") or request.FILES.get("file")
    if image is None:
        return Response({"success": False, "error": "photo is required."}, status=status.HTTP_400_BAD_REQUEST)

    capture_source = str(request.data.get("capture_source") or "").strip().lower()
    if not request.user.is_staff and not _is_camera_capture_source(capture_source):
        message = "Live camera capture is required. Gallery, file, or replay uploads are not allowed."
        _set_rejected_enrollment(person, message=message)
        _record_enrollment_failure(request, person, message)
        mark_device_sync_pending("Face enrollment failed")
        return Response({"success": False, "error": message}, status=status.HTTP_400_BAD_REQUEST)

    if not is_compreface_configured():
        person.face_enrollment_status = "not_started"
        person.face_enrollment_error = "CompreFace is not configured."
        person.photo_review_status = "rejected"
        person.photo_review_error = "CompreFace is not configured."
        person.photo_reviewed_at = timezone.now()
        person.save(update_fields=["face_enrollment_status", "face_enrollment_error", "photo_review_status", "photo_review_error", "photo_reviewed_at", "modified_at"])
        AuditTrail.objects.create(
            person=person,
            action="face_enroll_failed",
            performed_by=request.user if request.user.is_authenticated else None,
            details="CompreFace is not configured.",
        )
        return Response(
            {"success": False, "error": "CompreFace is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        uploaded_meta = describe_uploaded_photo(image)
        save_photo_debug_copy(image, prefix=f"face-enroll-{person.id}")
        normalized_photo = normalize_photo_upload(image, filename=uploaded_meta["filename"])
        quality = assess_photo_quality(normalized_photo)
    except PhotoQualityError as exc:
        _set_rejected_enrollment(person, message=str(exc))
        _record_enrollment_failure(request, person, str(exc))
        mark_device_sync_pending("Face enrollment failed")
        return Response({"success": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    spoof_review_threshold = _get_spoof_review_threshold()
    if quality.spoof_risk_score >= spoof_review_threshold:
        message = _build_spoof_rejection_message(quality)
        _set_rejected_enrollment(
            person,
            message=message,
            quality_score=quality.score,
            review_attempt=normalized_photo,
        )
        _record_enrollment_failure(
            request,
            person,
            (
                f"{message} risk={quality.spoof_risk_score} "
                f"flags={','.join(quality.spoof_artifact_flags) or 'none'}"
            ),
        )
        mark_device_sync_pending("Face enrollment failed")
        return Response(
            {
                "success": False,
                "error": message,
                "quality_score": quality.score,
                "quality_threshold": quality.threshold,
                "quality_reasons": list(quality.reasons),
                "spoof_risk_score": quality.spoof_risk_score,
                "spoof_artifact_flags": list(quality.spoof_artifact_flags),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        face_details = get_face_presence_details(normalized_photo)
        face_count = int(face_details.get("face_count") or 0)
        if face_count != 1:
            message = (
                "Multiple faces were detected. Upload a photo with one face only."
                if face_count
                else "No clear face was detected. Upload a front-facing photo with one face only."
            )
            _set_rejected_enrollment(
                person,
                message=message,
                quality_score=quality.score,
                review_attempt=normalized_photo,
            )
            _record_enrollment_failure(request, person, message)
            mark_device_sync_pending("Face enrollment failed")
            return Response({"success": False, "error": message}, status=status.HTTP_400_BAD_REQUEST)
        ensure_single_face_present(normalized_photo)
    except CompreFaceError as exc:
        message = str(exc)
        if not is_detection_service_unavailable_error(message):
            _set_rejected_enrollment(
                person,
                message=message,
                quality_score=quality.score,
                review_attempt=normalized_photo,
            )
            _record_enrollment_failure(request, person, message)
            mark_device_sync_pending("Face enrollment failed")
            return Response({"success": False, "error": message}, status=status.HTTP_400_BAD_REQUEST)

    person.photo_review_attempt = normalized_photo
    person.save(update_fields=["photo_review_attempt", "modified_at"])

    person.face_enrollment_quality_score = quality.score
    person.save(update_fields=["face_enrollment_quality_score", "modified_at"])

    if not quality.is_acceptable:
        message = (
            f"Photo quality {quality.score}% is below the minimum required {quality.threshold}%."
        )
        if quality.reasons:
            message = f"{message} {' '.join(quality.reasons)}"
        _set_rejected_enrollment(
            person,
            message=message,
            quality_score=quality.score,
            review_attempt=normalized_photo,
        )
        _record_enrollment_failure(request, person, message)
        mark_device_sync_pending("Face enrollment failed")
        return Response(
            {
                "success": False,
                "error": message,
                "quality_score": quality.score,
                "quality_threshold": quality.threshold,
                "quality_reasons": list(quality.reasons),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    subject = (person.face_subject_id or str(person.id)).strip()
    person.face_provider = "compreface"
    person.face_subject_id = subject
    person.face_enrollment_status = "pending"
    person.face_enrollment_error = ""
    person.save(
        update_fields=[
            "face_provider",
            "face_subject_id",
            "face_enrollment_status",
            "face_enrollment_error",
            "modified_at",
        ]
    )

    try:
        compreface_result = enroll_face(subject=subject, image_file=normalized_photo)
        reference_image_id = str(compreface_result.get("image_id") or "").strip()
        if not reference_image_id:
            raise CompreFaceError("CompreFace did not return a reference image id.")
        person.photo = normalized_photo
        person.photo_review_attempt = normalized_photo
        person.face_enrollment_status = "approved"
        person.facial_recognition_enabled = True
        person.face_enrolled_at = timezone.now()
        person.face_last_synced_at = timezone.now()
        person.face_reference_image_id = reference_image_id
        person.photo_review_status = "approved"
        person.photo_review_error = ""
        person.photo_reviewed_at = timezone.now()
        person.face_enrollment_error = ""
        person.save(
            update_fields=[
                "photo",
                "photo_review_attempt",
                "face_provider",
                "face_subject_id",
                "face_reference_image_id",
                "face_enrollment_status",
                "facial_recognition_enabled",
                "face_enrolled_at",
                "face_last_synced_at",
                "photo_review_status",
                "photo_review_error",
                "photo_reviewed_at",
                "face_enrollment_error",
                "modified_at",
            ]
        )
        AuditTrail.objects.create(
            person=person,
            action="face_enroll",
            performed_by=request.user if request.user.is_authenticated else None,
            details=f"Enrolled face for {person.full_name} via CompreFace subject {subject}",
        )
        mark_device_sync_pending("Face enrolled")
        visitor_activation = activate_visitor_face_grant_for_person(person, requested_by=request.user)
        queued_terminals = 0
        if visitor_activation.get("activated"):
            queued_terminals = int((visitor_activation.get("queued") or {}).get("total") or 0)
            print(
                f"visitor-face-grant activated person={person.id} "
                f"grant={getattr(visitor_activation.get('grant'), 'id', '')} "
                f"queued={visitor_activation.get('queued')}",
                flush=True,
            )
        else:
            queued_terminals = queue_face_device_person_sync(person, requested_by=request.user)
        if queued_terminals:
            print(
                f"face-enrollment queued device sync person={person.id} terminals={queued_terminals}",
                flush=True,
        )
        return Response(
            {
                "success": True,
                "person": _serialize_person(person),
                "compreface": compreface_result,
                "quality_score": quality.score,
                "quality_threshold": quality.threshold,
                "quality_reasons": list(quality.reasons),
                "photo_review_status": person.photo_review_status,
                "photo_review_error": person.photo_review_error or "",
                "face_reference_image_id": person.face_reference_image_id or "",
                "spoof_risk_score": quality.spoof_risk_score,
                "spoof_artifact_flags": list(quality.spoof_artifact_flags),
            }
        )
    except CompreFaceError as exc:
        _set_rejected_enrollment(
            person,
            message=str(exc),
            quality_score=quality.score,
            review_attempt=normalized_photo,
        )
        _record_enrollment_failure(request, person, str(exc))
        mark_device_sync_pending("Face enrollment failed")
        return Response({"success": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        _set_rejected_enrollment(
            person,
            message=str(exc),
            quality_score=quality.score,
            review_attempt=normalized_photo,
        )
        _record_enrollment_failure(request, person, str(exc))
        mark_device_sync_pending("Face enrollment failed")
        return Response({"success": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
