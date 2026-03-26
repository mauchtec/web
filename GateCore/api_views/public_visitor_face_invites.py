from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from GateCore.api_views.profile import (
    _build_spoof_rejection_message,
    _get_spoof_review_threshold,
    _is_camera_capture_source,
)
from GateCore.models import AuditTrail, GuestRegistration
from GateCore.services.compreface_client import (
    CompreFaceError,
    enroll_face,
    ensure_single_face_present,
    is_compreface_configured,
    is_detection_service_unavailable_error,
)
from GateCore.services.mobile_auth import build_photo_display_url
from GateCore.services.photo_quality import (
    PhotoQualityError,
    assess_photo_quality,
    describe_uploaded_photo,
    normalize_photo_upload,
    save_photo_debug_copy,
)
from GateCore.services.visitor_face_pass import activate_visitor_face_grant_for_person


def _resolve_invite(booking_id, pin):
    booking = (
        GuestRegistration.objects.select_related("guest", "host", "unit", "approved_by")
        .filter(id=booking_id)
        .first()
    )
    if booking is None:
        return None, Response({"detail": "Invite not found."}, status=status.HTTP_404_NOT_FOUND)

    if str(booking.purpose or "").strip().lower() != "visitor face invite":
        return None, Response({"detail": "This booking is not enabled for visitor face enrollment."}, status=status.HTTP_400_BAD_REQUEST)

    if booking.status != "approved":
        return None, Response({"detail": "This invite is not active."}, status=status.HTTP_400_BAD_REQUEST)

    if str(booking.temporary_pin or "").strip() != str(pin or "").strip():
        return None, Response({"detail": "Invalid invite PIN."}, status=status.HTTP_403_FORBIDDEN)

    now = timezone.now()
    if booking.pin_expires_at and booking.pin_expires_at < now:
        return None, Response({"detail": "This invite has expired."}, status=status.HTTP_410_GONE)

    return booking, None


def _public_visitor_quality_threshold():
    value = getattr(settings, "PUBLIC_VISITOR_FACE_MIN_QUALITY_SCORE", 70)
    try:
        return int(value)
    except Exception:
        return 70


def _serialize_invite(booking):
    person = booking.guest
    return {
        "booking_id": str(booking.id),
        "guest": {
            "id": str(person.id) if person else "",
            "full_name": person.full_name if person else "",
            "phone": getattr(person, "phone", "") or "",
            "photo_url": build_photo_display_url(getattr(person, "photo", None)) if person else "",
            "face_enrollment_status": getattr(person, "face_enrollment_status", "not_started") if person else "not_started",
            "face_enrollment_status_display": person.get_face_enrollment_status_display() if person and getattr(person, "face_enrollment_status", "") else "",
            "face_enrollment_quality_score": str(person.face_enrollment_quality_score) if person and getattr(person, "face_enrollment_quality_score", None) is not None else "",
            "face_enrollment_error": getattr(person, "face_enrollment_error", "") if person else "",
        },
        "host": {
            "full_name": booking.host.full_name if booking.host else "",
        },
        "unit": {
            "unit_code": booking.unit.unit_code if booking.unit else "",
        },
        "expected_arrival": booking.expected_arrival.isoformat() if booking.expected_arrival else "",
        "expected_arrival_display": booking.expected_arrival.strftime("%Y-%m-%d %H:%M") if booking.expected_arrival else "",
        "expected_departure": booking.expected_departure.isoformat() if booking.expected_departure else "",
        "expected_departure_display": booking.expected_departure.strftime("%Y-%m-%d %H:%M") if booking.expected_departure else "",
        "pin_expires_at": booking.pin_expires_at.isoformat() if booking.pin_expires_at else "",
        "pin_expires_at_display": booking.pin_expires_at.strftime("%Y-%m-%d %H:%M") if booking.pin_expires_at else "",
        "status": booking.status,
        "status_display": booking.get_status_display(),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def public_visitor_face_invite_detail(request):
    booking_id = request.GET.get("booking_id")
    pin = request.GET.get("pin")
    booking, error = _resolve_invite(booking_id, pin)
    if error is not None:
        return error
    return Response({"invite": _serialize_invite(booking)})


@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def public_visitor_face_invite_enroll(request):
    booking_id = request.data.get("booking_id")
    pin = request.data.get("pin")
    booking, error = _resolve_invite(booking_id, pin)
    if error is not None:
        return error

    person = booking.guest
    photo = request.FILES.get("photo") or request.FILES.get("image") or request.FILES.get("file")
    if person is None:
        return Response({"detail": "Invite guest profile is missing."}, status=status.HTTP_400_BAD_REQUEST)
    if (
        str(getattr(person, "face_enrollment_status", "")).strip() in {"approved", "synced"}
        and str(getattr(person, "face_reference_image_id", "")).strip()
    ):
        return Response(
            {
                "detail": (
                    "Face enrollment is already completed for this visitor. "
                    "Re-enrollment is not allowed."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )
    if photo is None:
        return Response({"detail": "photo is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not is_compreface_configured():
        return Response({"detail": "Face enrollment service is not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    capture_source = str(request.data.get("capture_source") or "").strip().lower()
    if not _is_camera_capture_source(capture_source):
        return Response(
            {"detail": "Live camera capture is required. Gallery, file, or replay uploads are not allowed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        uploaded_meta = describe_uploaded_photo(photo)
        save_photo_debug_copy(photo, prefix=f"visitor-face-{person.id}")
        normalized_photo = normalize_photo_upload(photo, filename=uploaded_meta["filename"])
        quality = assess_photo_quality(normalized_photo)
    except PhotoQualityError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if quality.spoof_risk_score >= _get_spoof_review_threshold():
        message = _build_spoof_rejection_message(quality)
        person.face_enrollment_status = "rejected"
        person.face_enrollment_error = message
        person.face_enrollment_quality_score = quality.score
        person.save(update_fields=["face_enrollment_status", "face_enrollment_error", "face_enrollment_quality_score", "modified_at"])
        AuditTrail.objects.create(person=person, action="visitor_face_enroll_rejected", details=message)
        return Response(
            {
                "detail": message,
                "quality_score": quality.score,
                "quality_threshold": _public_visitor_quality_threshold(),
                "quality_reasons": list(quality.reasons),
                "spoof_risk_score": quality.spoof_risk_score,
                "spoof_artifact_flags": list(quality.spoof_artifact_flags),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    public_threshold = _public_visitor_quality_threshold()
    if int(quality.score) < public_threshold:
        message = f"Photo quality {quality.score}% is below the minimum required {public_threshold}%."
        if quality.reasons:
            message = f"{message} {' '.join(quality.reasons)}"
        person.face_enrollment_status = "rejected"
        person.face_enrollment_error = message
        person.face_enrollment_quality_score = quality.score
        person.save(update_fields=["face_enrollment_status", "face_enrollment_error", "face_enrollment_quality_score", "modified_at"])
        AuditTrail.objects.create(person=person, action="visitor_face_enroll_rejected", details=message)
        return Response(
            {
                "detail": message,
                "quality_score": quality.score,
                "quality_threshold": public_threshold,
                "quality_reasons": list(quality.reasons),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        ensure_single_face_present(normalized_photo)
    except CompreFaceError as exc:
        message = str(exc)
        if not is_detection_service_unavailable_error(message):
            person.face_enrollment_status = "rejected"
            person.face_enrollment_error = message
            person.face_enrollment_quality_score = quality.score
            person.save(update_fields=["face_enrollment_status", "face_enrollment_error", "face_enrollment_quality_score", "modified_at"])
            AuditTrail.objects.create(person=person, action="visitor_face_enroll_rejected", details=message)
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

    try:
        subject = (person.face_subject_id or str(person.id)).strip()
        compreface_result = enroll_face(subject=subject, image_file=photo)
        reference_image_id = str(compreface_result.get("image_id") or "").strip()
        if not reference_image_id:
            raise CompreFaceError("CompreFace did not return a reference image id.")
    except CompreFaceError as exc:
        message = str(exc)
        person.face_enrollment_status = "rejected"
        person.face_enrollment_error = message
        person.face_enrollment_quality_score = quality.score
        person.save(update_fields=["face_enrollment_status", "face_enrollment_error", "face_enrollment_quality_score", "modified_at"])
        AuditTrail.objects.create(person=person, action="visitor_face_enroll_rejected", details=message)
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

    person.photo = normalized_photo
    person.photo_review_attempt = normalized_photo
    person.face_provider = "compreface"
    person.face_subject_id = subject
    person.face_reference_image_id = reference_image_id
    person.face_enrollment_quality_score = quality.score
    person.face_enrollment_error = ""
    person.face_enrollment_status = "approved"
    person.facial_recognition_enabled = True
    person.face_enrolled_at = timezone.now()
    person.face_last_synced_at = timezone.now()
    person.photo_review_status = "approved"
    person.photo_review_error = ""
    person.photo_reviewed_at = timezone.now()
    person.save(
        update_fields=[
            "photo",
            "photo_review_attempt",
            "face_provider",
            "face_subject_id",
            "face_reference_image_id",
            "face_enrollment_quality_score",
            "face_enrollment_error",
            "face_enrollment_status",
            "facial_recognition_enabled",
            "face_enrolled_at",
            "face_last_synced_at",
            "photo_review_status",
            "photo_review_error",
            "photo_reviewed_at",
            "modified_at",
        ]
    )
    AuditTrail.objects.create(
        person=person,
        action="visitor_face_enrolled",
        details=f"Visitor face enrolled from public invite. quality={quality.score} booking={booking.id}",
    )
    activation = activate_visitor_face_grant_for_person(person, requested_by=None)
    return Response(
        {
            "success": True,
            "detail": "Face enrollment completed successfully.",
            "invite": _serialize_invite(booking),
            "quality_score": quality.score,
            "quality_threshold": public_threshold,
            "quality_reasons": list(quality.reasons),
            "queued": activation.get("queued"),
        }
    )
