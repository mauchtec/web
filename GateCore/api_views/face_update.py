"""API views for face verification update flow.

Endpoints:
    POST /api/gatecore/mobile/face/update/       — upload new face, compare to primary
    POST /api/gatecore/mobile/face/confirm-update/ — OTP step-up auth to finalize
    GET  /api/gatecore/admin/face/review-queue/   — list pending reviews
    POST /api/gatecore/admin/face/review/<id>/resolve/ — admin approve/reject
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from GateCore.models import Person
from GateCore.models.face_verification import FaceReference, FaceVerificationLog
from GateCore.services.face_update import (
    admin_resolve_review,
    confirm_face_update,
    request_face_update,
)
from GateCore.services.mobile_auth import is_otp_valid


# ——— Mobile endpoints ————————————————————————————————————————

@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def mobile_face_update(request):
    """Upload a new face image. Compares to primary reference and returns status."""
    person_profile = getattr(request.user, "person_profile", None)
    if not person_profile:
        return Response(
            {"status": "error", "message": "No person profile linked to this account."},
            status=status.HTTP_403_FORBIDDEN,
        )

    image = request.FILES.get("photo") or request.FILES.get("image") or request.FILES.get("file")
    if image is None:
        return Response(
            {"status": "error", "message": "photo is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    capture_source = str(request.data.get("capture_source") or "").strip().lower()
    if capture_source != "camera":
        return Response(
            {
                "status": "rejected",
                "message": "Live camera capture is required. Gallery, file, or replay uploads are not allowed.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = request_face_update(person_profile, image, request)

    status_map = {
        "approved": status.HTTP_200_OK,
        "needs_review": status.HTTP_200_OK,
        "rejected": status.HTTP_200_OK,
        "rate_limited": status.HTTP_429_TOO_MANY_REQUESTS,
        "error": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    return Response(result, status=status_map.get(result["status"], status.HTTP_200_OK))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mobile_face_confirm_update(request):
    """Confirm a face update with OTP step-up auth.

    Expects: { "face_reference_id": "uuid", "otp": "123456" }
    """
    person_profile = getattr(request.user, "person_profile", None)
    if not person_profile:
        return Response(
            {"status": "error", "message": "No person profile linked to this account."},
            status=status.HTTP_403_FORBIDDEN,
        )

    face_reference_id = request.data.get("face_reference_id")
    otp = request.data.get("otp", "").strip()

    if not face_reference_id:
        return Response(
            {"status": "error", "message": "face_reference_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not otp:
        return Response(
            {"status": "error", "message": "OTP is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify OTP — match the code and check expiry
    person_profile.refresh_from_db()
    if not (person_profile.phone_otp == otp and is_otp_valid(person_profile)):
        return Response(
            {"status": "error", "message": "Invalid or expired OTP."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Clear OTP after successful verification
    Person.objects.filter(id=person_profile.id).update(phone_otp="", phone_otp_created=None)

    result = confirm_face_update(person_profile, face_reference_id, request)

    if result["status"] == "error":
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_200_OK)


# ——— Admin endpoints ————————————————————————————————————————

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_face_review_queue(request):
    """List all pending face reviews for admin."""
    pending = (
        FaceReference.objects.filter(role="pending", is_deleted=False)
        .select_related("person")
        .order_by("created_at")
    )

    items = []
    for ref in pending:
        person = ref.person
        items.append({
            "face_reference_id": str(ref.id),
            "person_id": str(person.id),
            "person_name": f"{person.first_name} {person.last_name}".strip(),
            "phone": person.phone or "",
            "similarity_to_primary": float(ref.similarity_to_primary) if ref.similarity_to_primary else None,
            "quality_score": float(ref.quality_score) if ref.quality_score else None,
            "submitted_at": ref.created_at.isoformat(),
            "new_image_url": ref.image.url if ref.image else "",
            "primary_image_url": _get_primary_image_url(person),
        })

    return Response({"count": len(items), "results": items})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_face_review_resolve(request, face_reference_id):
    """Admin approves or rejects a pending face update.

    Expects: { "action": "approve" | "reject", "notes": "optional" }
    """
    face_ref = get_object_or_404(FaceReference, id=face_reference_id, role="pending", is_deleted=False)
    person = face_ref.person

    action = request.data.get("action", "").strip().lower()
    if action not in ("approve", "reject"):
        return Response(
            {"status": "error", "message": "action must be 'approve' or 'reject'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    notes = request.data.get("notes", "")
    result = admin_resolve_review(person, str(face_ref.id), approve=(action == "approve"), request=request, notes=notes)

    if result["status"] == "error":
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_200_OK)


# ——— Helpers ————————————————————————————————————————————————

def _get_primary_image_url(person):
    primary = (
        FaceReference.objects.filter(person=person, role="primary", is_deleted=False)
        .order_by("-created_at")
        .first()
    )
    if primary and primary.image:
        return primary.image.url
    if person.photo:
        return person.photo.url
    return ""
