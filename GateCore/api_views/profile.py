import logging
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from GateCore.api_views.device_sync import mark_device_sync_pending, queue_face_device_person_sync
from GateCore.models import AuditTrail
from GateCore.models.face_verification import FaceReference
from GateCore.services.compreface_client import (
    CompreFaceError,
    enroll_face,
    get_face_presence_details,
    extract_best_match,
    has_compreface_detection_config,
    has_compreface_verification_config,
    is_compreface_configured,
    is_detection_service_unavailable_error,
    verify_images,
)
from GateCore.services.photo_quality import (
    build_photo_analysis_report,
    PhotoQualityError,
    assess_photo_quality,
    describe_uploaded_photo,
    normalize_photo_upload,
    save_photo_debug_copy,
)
from GateCore.services.mobile_auth import build_photo_display_url

logger = logging.getLogger(__name__)


def _person_from_request(request):
    return getattr(request.user, "person_profile", None)


class MobileProfilePhotoUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        person = _person_from_request(request)
        if person is None:
            return Response({"detail": "No person profile is linked to this account."}, status=status.HTTP_400_BAD_REQUEST)

        photo = request.FILES.get("photo") or request.FILES.get("image")
        if photo is None:
            return Response({"detail": "photo is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uploaded_meta = describe_uploaded_photo(photo)
            logger.info(
                "Resident photo upload received person=%s filename=%s content_type=%s size=%s dims=%sx%s",
                person.id,
                uploaded_meta["filename"],
                uploaded_meta["content_type"] or "-",
                uploaded_meta["size_bytes"],
                uploaded_meta["width"],
                uploaded_meta["height"],
            )
            debug_path = save_photo_debug_copy(photo, prefix=f"person-{person.id}")
            if debug_path:
                logger.info("Resident photo debug copy saved person=%s path=%s", person.id, debug_path)
            normalized_photo = normalize_photo_upload(photo, filename=uploaded_meta["filename"])
            quality = assess_photo_quality(normalized_photo)
        except PhotoQualityError as exc:
            return Response(
                {"success": False, "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report_similarity_percent = None
        report_match_subject = ""
        report_face_count = None
        similarity_percent = None
        match_subject = ""
        detection_service_unavailable_message = ""
        threshold = quality.threshold
        capture_source = str(request.data.get("capture_source") or "").strip().lower()

        if not _is_camera_capture_source(capture_source):
            message = "Live camera capture is required. Gallery, file, or replay uploads are not allowed."
            AuditTrail.objects.create(
                person=person,
                action="photo_upload_rejected",
                performed_by=request.user if request.user.is_authenticated else None,
                details=f"Rejected photo upload for {person.full_name}: {message}",
            )
            return Response(
                {
                    "success": False,
                    "detail": message,
                    "quality_score": quality.score,
                    "quality_percent": quality.score,
                    "quality_threshold": threshold,
                    "quality_reasons": list(quality.reasons),
                    "spoof_risk_score": quality.spoof_risk_score,
                    "spoof_artifact_flags": list(quality.spoof_artifact_flags),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            face_details = get_face_presence_details(normalized_photo)
            report_face_count = int(face_details.get("face_count") or 0)
        except CompreFaceError as exc:
            message = str(exc)
            if not is_detection_service_unavailable_error(message):
                person.photo_review_status = "rejected"
                person.photo_review_error = message
                person.photo_reviewed_at = timezone.now()
                person.photo_similarity_score = None
                person.face_enrollment_status = "rejected"
                person.face_enrollment_error = message
                person.face_enrollment_quality_score = quality.score
                person.save(
                    update_fields=[
                        "photo_review_status",
                        "photo_review_error",
                        "photo_reviewed_at",
                        "photo_similarity_score",
                        "photo_review_attempt",
                        "face_enrollment_status",
                        "face_enrollment_error",
                        "face_enrollment_quality_score",
                        "modified_at",
                    ]
                )
                AuditTrail.objects.create(
                    person=person,
                    action="photo_upload_rejected",
                    performed_by=request.user if request.user.is_authenticated else None,
                    details=f"Rejected photo upload for {person.full_name}: {message}",
                )
                mark_device_sync_pending("Resident photo rejected")
                return Response(
                    {
                        "success": False,
                        "detail": message,
                        "quality_score": quality.score,
                        "quality_percent": quality.score,
                        "quality_threshold": threshold,
                        "quality_reasons": list(quality.reasons),
                        "photo_review_status": "rejected",
                        "photo_review_error": message,
                        "photo_analysis_report": build_photo_analysis_report(
                            person=person,
                            uploaded_meta=uploaded_meta,
                            quality=quality,
                            reviewer_name=getattr(request.user, "get_full_name", lambda: "")() or getattr(request.user, "username", "") or "Admin",
                            face_count=report_face_count,
                            similarity_percent=report_similarity_percent,
                            match_subject=report_match_subject,
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            logger.warning(
                "Detection service unavailable for resident photo upload person=%s: %s",
                person.id,
                message,
            )
            detection_service_unavailable_message = message

        if quality.spoof_risk_score >= _get_spoof_review_threshold():
            message = _build_spoof_rejection_message(quality)
            person.photo_review_status = "rejected"
            person.photo_review_error = message
            person.photo_reviewed_at = timezone.now()
            person.photo_similarity_score = None
            person.photo_review_attempt = normalized_photo
            person.face_enrollment_status = "rejected"
            person.face_enrollment_error = message
            person.face_enrollment_quality_score = quality.score
            person.save(
                update_fields=[
                    "photo_review_status",
                    "photo_review_error",
                    "photo_reviewed_at",
                    "photo_similarity_score",
                    "photo_review_attempt",
                    "face_enrollment_status",
                    "face_enrollment_error",
                    "face_enrollment_quality_score",
                    "modified_at",
                ]
            )
            AuditTrail.objects.create(
                person=person,
                action="photo_upload_rejected",
                performed_by=request.user if request.user.is_authenticated else None,
                details=(
                    f"Rejected photo upload for {person.full_name}: "
                    f"spoof risk {quality.spoof_risk_score}% flags={','.join(quality.spoof_artifact_flags) or 'none'}."
                ),
            )
            mark_device_sync_pending("Resident photo rejected")
            return Response(
                {
                    "success": False,
                    "detail": message,
                    "quality_score": quality.score,
                    "quality_percent": quality.score,
                    "quality_threshold": threshold,
                    "quality_reasons": list(quality.reasons),
                    "photo_review_status": "rejected",
                    "photo_review_error": message,
                    "spoof_risk_score": quality.spoof_risk_score,
                    "spoof_artifact_flags": list(quality.spoof_artifact_flags),
                    "photo_analysis_report": build_photo_analysis_report(
                        person=person,
                        uploaded_meta=uploaded_meta,
                        quality=quality,
                        reviewer_name=getattr(request.user, "get_full_name", lambda: "")() or getattr(request.user, "username", "") or "Admin",
                        face_count=report_face_count,
                        similarity_percent=report_similarity_percent,
                        match_subject=report_match_subject,
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not quality.is_acceptable:
            reason_text = " ".join(quality.reasons) if quality.reasons else "The photo does not meet the minimum quality requirements."
            message = f"Photo quality {quality.score}% is below the minimum required {threshold}%."
            if reason_text:
                message = f"{message} {reason_text}"
            person.photo_review_status = "rejected"
            person.photo_review_error = message
            person.photo_reviewed_at = timezone.now()
            person.photo_similarity_score = None
            person.photo_review_attempt = normalized_photo
            person.face_enrollment_status = "rejected"
            person.face_enrollment_error = message
            person.face_enrollment_quality_score = quality.score
            person.save(
                update_fields=[
                    "photo_review_status",
                    "photo_review_error",
                    "photo_reviewed_at",
                    "photo_similarity_score",
                    "photo_review_attempt",
                    "face_enrollment_status",
                    "face_enrollment_error",
                    "face_enrollment_quality_score",
                    "modified_at",
                ]
            )
            AuditTrail.objects.create(
                person=person,
                action="photo_upload_rejected",
                performed_by=request.user if request.user.is_authenticated else None,
                details=f"Rejected photo upload for {person.full_name}: {quality.score}% quality. {reason_text}",
            )
            mark_device_sync_pending("Resident photo rejected")
            return Response(
                {
                    "success": False,
                    "detail": message,
                    "quality_score": quality.score,
                    "quality_percent": quality.score,
                    "quality_threshold": threshold,
                    "quality_reasons": list(quality.reasons),
                    "photo_review_status": "rejected",
                    "photo_review_error": message,
                    "photo_analysis_report": build_photo_analysis_report(
                        person=person,
                        uploaded_meta=uploaded_meta,
                        quality=quality,
                        reviewer_name=getattr(request.user, "get_full_name", lambda: "")() or getattr(request.user, "username", "") or "Admin",
                        face_count=None,
                        similarity_percent=report_similarity_percent,
                        match_subject=report_match_subject,
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        primary_reference = _get_or_create_primary_reference(person)
        current_reference_photo = getattr(primary_reference, "image", None) if primary_reference else None
        if not _is_photo_review_configured(current_reference_photo):
            return Response(
                {"success": False, "detail": "CompreFace is not fully configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        review_threshold = _get_photo_match_threshold()
        person.photo_review_attempt = normalized_photo

        if detection_service_unavailable_message:
            user_message = "Face detection service is temporarily unavailable. Try again in a moment."
            return Response(
                {
                    "success": False,
                    "detail": user_message,
                    "error": detection_service_unavailable_message,
                    "quality_score": quality.score,
                    "quality_percent": quality.score,
                    "quality_threshold": threshold,
                    "quality_reasons": list(quality.reasons),
                    "spoof_risk_score": quality.spoof_risk_score,
                    "spoof_artifact_flags": list(quality.spoof_artifact_flags),
                    "photo_analysis_report": build_photo_analysis_report(
                        person=person,
                        uploaded_meta=uploaded_meta,
                        quality=quality,
                        reviewer_name=getattr(request.user, "get_full_name", lambda: "")() or getattr(request.user, "username", "") or "Admin",
                        face_count=report_face_count,
                        similarity_percent=report_similarity_percent,
                        match_subject=report_match_subject,
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if report_face_count != 1:
            message = "Multiple faces were detected. Upload a photo with one face only." if report_face_count else "No clear face was detected. Upload a front-facing photo with one face only."
            person.photo_review_status = "rejected"
            person.photo_review_error = message
            person.photo_reviewed_at = timezone.now()
            person.photo_similarity_score = None
            person.face_enrollment_status = "rejected"
            person.face_enrollment_error = message
            person.face_enrollment_quality_score = quality.score
            person.save(
                update_fields=[
                    "photo_review_status",
                    "photo_review_error",
                    "photo_reviewed_at",
                    "photo_similarity_score",
                    "photo_review_attempt",
                    "face_enrollment_status",
                    "face_enrollment_error",
                    "face_enrollment_quality_score",
                    "modified_at",
                ]
            )
            AuditTrail.objects.create(
                person=person,
                action="photo_upload_rejected",
                performed_by=request.user if request.user.is_authenticated else None,
                details=f"Rejected photo upload for {person.full_name}: {message}",
            )
            mark_device_sync_pending("Resident photo rejected")
            return Response(
                {
                    "success": False,
                    "detail": message,
                    "quality_score": quality.score,
                    "quality_percent": quality.score,
                    "quality_threshold": threshold,
                    "quality_reasons": list(quality.reasons),
                    "photo_review_status": "rejected",
                    "photo_review_error": message,
                    "photo_analysis_report": build_photo_analysis_report(
                        person=person,
                        uploaded_meta=uploaded_meta,
                        quality=quality,
                        reviewer_name=getattr(request.user, "get_full_name", lambda: "")() or getattr(request.user, "username", "") or "Admin",
                        face_count=report_face_count,
                        similarity_percent=report_similarity_percent,
                        match_subject=report_match_subject,
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if current_reference_photo and getattr(current_reference_photo, "name", ""):
            try:
                verification = verify_images(current_reference_photo, normalized_photo)
                similarity, matched_subject = extract_best_match(verification)
                if similarity is None:
                    raise CompreFaceError("CompreFace did not return a similarity score.")
                similarity_percent = _similarity_to_percent(similarity)
                report_similarity_percent = similarity_percent
                report_match_subject = matched_subject
                if similarity < review_threshold:
                    message = (
                        f"Photo match {similarity_percent:.2f}% is below the minimum required "
                        f"{_threshold_to_percent(review_threshold):.0f}%."
                    )
                    person.photo_review_status = "rejected"
                    person.photo_review_error = message
                    person.photo_similarity_score = Decimal(str(similarity_percent))
                    person.photo_reviewed_at = timezone.now()
                    person.face_enrollment_status = "rejected"
                    person.face_enrollment_error = message
                    person.face_enrollment_quality_score = quality.score
                    person.save(
                        update_fields=[
                            "photo_review_status",
                            "photo_review_error",
                            "photo_similarity_score",
                            "photo_reviewed_at",
                            "photo_review_attempt",
                            "face_enrollment_status",
                            "face_enrollment_error",
                            "face_enrollment_quality_score",
                            "modified_at",
                        ]
                    )
                    AuditTrail.objects.create(
                        person=person,
                        action="photo_upload_rejected",
                        performed_by=request.user if request.user.is_authenticated else None,
                        details=(
                            f"Rejected photo upload for {person.full_name}: "
                            f"quality {quality.score}%, match {similarity_percent:.2f}%."
                        ),
                    )
                    mark_device_sync_pending("Resident photo rejected")
                    return Response(
                        {
                            "success": False,
                            "detail": message,
                            "quality_score": quality.score,
                            "quality_percent": quality.score,
                            "quality_threshold": threshold,
                            "quality_reasons": list(quality.reasons),
                            "photo_review_status": "rejected",
                            "photo_similarity_score": similarity_percent,
                            "photo_match_threshold": _threshold_to_percent(review_threshold),
                            "photo_review_error": message,
                            "photo_analysis_report": build_photo_analysis_report(
                                person=person,
                                uploaded_meta=uploaded_meta,
                                quality=quality,
                                reviewer_name=getattr(request.user, "get_full_name", lambda: "")() or getattr(request.user, "username", "") or "Admin",
                                face_count=None,
                                similarity_percent=report_similarity_percent,
                                match_subject=report_match_subject,
                            ),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except CompreFaceError as exc:
                message = str(exc)
                person.photo_review_status = "rejected"
                person.photo_review_error = message
                person.photo_reviewed_at = timezone.now()
                person.face_enrollment_status = "rejected"
                person.face_enrollment_error = message
                person.face_enrollment_quality_score = quality.score
                person.photo_similarity_score = None
                person.save(
                    update_fields=[
                        "photo_review_status",
                        "photo_review_error",
                        "photo_reviewed_at",
                        "photo_review_attempt",
                        "photo_similarity_score",
                        "face_enrollment_status",
                        "face_enrollment_error",
                        "face_enrollment_quality_score",
                        "modified_at",
                    ]
                )
                AuditTrail.objects.create(
                    person=person,
                    action="photo_upload_rejected",
                    performed_by=request.user if request.user.is_authenticated else None,
                    details=f"Rejected photo upload for {person.full_name}: {message}",
                )
                mark_device_sync_pending("Resident photo rejected")
                return Response(
                    {
                        "success": False,
                        "detail": message,
                        "quality_score": quality.score,
                        "quality_percent": quality.score,
                        "quality_threshold": threshold,
                        "quality_reasons": list(quality.reasons),
                        "photo_review_status": "rejected",
                        "photo_review_error": message,
                        "photo_analysis_report": build_photo_analysis_report(
                            person=person,
                            uploaded_meta=uploaded_meta,
                            quality=quality,
                            reviewer_name=getattr(request.user, "get_full_name", lambda: "")() or getattr(request.user, "username", "") or "Admin",
                            face_count=report_face_count,
                            similarity_percent=report_similarity_percent,
                            match_subject=report_match_subject,
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        subject = (person.face_subject_id or str(person.id)).strip()
        try:
            compreface_result = enroll_face(subject=subject, image_file=normalized_photo)
        except CompreFaceError as exc:
            message = str(exc)
            if _should_keep_as_pending_baseline(message, current_reference_photo):
                person.photo = normalized_photo
                person.photo_review_attempt = normalized_photo
                person.face_provider = "compreface"
                person.face_subject_id = subject
                person.face_reference_image_id = ""
                person.face_enrollment_quality_score = quality.score
                person.face_enrollment_error = ""
                person.face_enrollment_status = "pending"
                person.facial_recognition_enabled = False
                person.face_enrolled_at = None
                person.face_last_synced_at = None
                person.photo_review_status = "pending"
                person.photo_similarity_score = None
                person.photo_review_error = "Face not detected yet. Upload a clearer photo to finalize review."
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
                        "photo_similarity_score",
                        "photo_review_error",
                        "photo_reviewed_at",
                        "modified_at",
                    ]
                )
                AuditTrail.objects.create(
                    person=person,
                    action="photo_upload_pending_review",
                    performed_by=request.user if request.user.is_authenticated else None,
                    details=(
                        f"Saved pending baseline for {person.full_name}: "
                        f"quality {quality.score}%, face not detected yet."
                    ),
                )
                mark_device_sync_pending("Resident photo pending review")
                return Response(
                    {
                        "success": True,
                        "detail": "Face not detected yet. Upload a clearer photo to finalize review.",
                        "quality_score": quality.score,
                        "quality_percent": quality.score,
                        "quality_threshold": threshold,
                        "quality_reasons": list(quality.reasons),
                        "photo_review_status": "pending",
                        "photo_review_error": person.photo_review_error,
                        "person": {
                            "id": str(person.id),
                            "full_name": person.full_name,
                            "phone": person.phone,
                            "photo_url": build_photo_display_url(person.photo),
                            "photo_review_attempt_url": build_photo_display_url(person.photo_review_attempt),
                            "photo_quality_score": str(person.face_enrollment_quality_score) if person.face_enrollment_quality_score is not None else "",
                            "face_enrollment_quality_score": str(person.face_enrollment_quality_score) if person.face_enrollment_quality_score is not None else "",
                            "photo_review_status": person.photo_review_status,
                            "photo_similarity_score": "",
                            "photo_review_error": person.photo_review_error,
                        },
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            person.photo_review_status = "rejected"
            person.photo_review_error = message
            person.photo_reviewed_at = timezone.now()
            person.face_enrollment_status = "rejected"
            person.face_enrollment_error = message
            person.face_enrollment_quality_score = quality.score
            person.save(
                update_fields=[
                    "photo_review_status",
                    "photo_review_error",
                    "photo_reviewed_at",
                    "photo_review_attempt",
                    "face_enrollment_status",
                    "face_enrollment_error",
                    "face_enrollment_quality_score",
                    "modified_at",
                ]
            )
            AuditTrail.objects.create(
                person=person,
                action="photo_upload_rejected",
                performed_by=request.user if request.user.is_authenticated else None,
                details=f"Rejected photo upload for {person.full_name}: {message}",
            )
            mark_device_sync_pending("Resident photo rejected")
            return Response(
                {
                    "success": False,
                    "detail": message,
                    "quality_score": quality.score,
                    "quality_percent": quality.score,
                    "quality_threshold": threshold,
                    "quality_reasons": list(quality.reasons),
                    "photo_review_status": "rejected",
                    "photo_review_error": message,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference_image_id = str(compreface_result.get("image_id") or "").strip()
        if not reference_image_id:
            message = "CompreFace did not return a reference image id."
            person.photo_review_status = "rejected"
            person.photo_review_error = message
            person.photo_reviewed_at = timezone.now()
            person.face_enrollment_status = "rejected"
            person.face_enrollment_error = message
            person.face_enrollment_quality_score = quality.score
            person.save(
                update_fields=[
                    "photo_review_status",
                    "photo_review_error",
                    "photo_reviewed_at",
                    "photo_review_attempt",
                    "face_enrollment_status",
                    "face_enrollment_error",
                    "face_enrollment_quality_score",
                    "modified_at",
                ]
            )
            AuditTrail.objects.create(
                person=person,
                action="photo_upload_rejected",
                performed_by=request.user if request.user.is_authenticated else None,
                details=f"Rejected photo upload for {person.full_name}: {message}",
            )
            mark_device_sync_pending("Resident photo rejected")
            return Response(
                {
                    "success": False,
                    "detail": message,
                    "quality_score": quality.score,
                    "quality_percent": quality.score,
                    "quality_threshold": threshold,
                    "quality_reasons": list(quality.reasons),
                    "photo_review_status": "rejected",
                    "photo_review_error": message,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        primary_reference_image_id = str(getattr(primary_reference, "compreface_image_id", "") or "").strip()
        if primary_reference is None:
            primary_reference = FaceReference.objects.create(
                person=person,
                image=_clone_image_file(normalized_photo, suffix="original"),
                role="primary",
                compreface_image_id=reference_image_id,
                quality_score=Decimal(str(quality.score)),
                notes="Original approved profile photo reference.",
            )
            primary_reference_image_id = reference_image_id

        person.photo = normalized_photo
        person.photo_review_attempt = normalized_photo
        person.face_provider = "compreface"
        person.face_subject_id = subject
        person.face_reference_image_id = primary_reference_image_id or reference_image_id
        person.face_enrollment_quality_score = quality.score
        person.face_enrollment_error = ""
        person.face_enrollment_status = "approved"
        person.facial_recognition_enabled = True
        person.face_enrolled_at = timezone.now()
        person.face_last_synced_at = timezone.now()
        person.photo_review_status = "approved"
        person.photo_similarity_score = (
            Decimal(str(similarity_percent)) if similarity_percent is not None else None
        )
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
                "photo_similarity_score",
                "photo_review_error",
                "photo_reviewed_at",
                "modified_at",
            ]
        )
        AuditTrail.objects.create(
            person=person,
            action="photo_upload",
            performed_by=request.user if request.user.is_authenticated else None,
            details=(
                f"Accepted photo upload for {person.full_name}: quality {quality.score}%"
                + (f", face match {similarity_percent:.2f}%" if similarity_percent is not None else "")
                + (f", matched subject {match_subject}" if match_subject else "")
            ),
        )
        mark_device_sync_pending("Resident photo updated")
        queued_terminals = queue_face_device_person_sync(person, requested_by=request.user)
        if queued_terminals:
            logger.info(
                "Queued resident face sync for person=%s terminals=%s",
                person.id,
                queued_terminals,
            )

        photo_url = build_photo_display_url(person.photo)

        return Response(
                {
                    "success": True,
                    "quality_score": quality.score,
                    "quality_percent": quality.score,
                    "photo_quality_score": quality.score,
                "quality_threshold": threshold,
                "quality_reasons": list(quality.reasons),
                    "photo_review_status": person.photo_review_status,
                    "photo_similarity_score": similarity_percent,
                    "spoof_risk_score": quality.spoof_risk_score,
                    "spoof_artifact_flags": list(quality.spoof_artifact_flags),
                    "photo_match_threshold": _threshold_to_percent(review_threshold),
                    "photo_analysis_report": build_photo_analysis_report(
                        person=person,
                        uploaded_meta=uploaded_meta,
                        quality=quality,
                        reviewer_name=getattr(request.user, "get_full_name", lambda: "")() or getattr(request.user, "username", "") or "Admin",
                        face_count=report_face_count,
                        similarity_percent=report_similarity_percent,
                        match_subject=report_match_subject,
                    ),
                    "person": {
                        "id": str(person.id),
                        "full_name": person.full_name,
                        "phone": person.phone,
                    "photo_url": photo_url,
                    "photo_review_attempt_url": build_photo_display_url(person.photo_review_attempt),
                    "photo_quality_score": str(person.face_enrollment_quality_score) if person.face_enrollment_quality_score is not None else "",
                    "face_enrollment_quality_score": str(person.face_enrollment_quality_score) if person.face_enrollment_quality_score is not None else "",
                    "photo_review_status": person.photo_review_status,
                    "photo_similarity_score": str(person.photo_similarity_score) if person.photo_similarity_score is not None else "",
                    "photo_review_error": person.photo_review_error or "",
                },
            }
        )


def _get_photo_match_threshold() -> float:
    value = getattr(settings, "PERSON_PHOTO_MATCH_THRESHOLD", 0.81) or 0.81
    try:
        threshold = float(value)
    except Exception:
        threshold = 0.81
    return threshold if threshold <= 1 else threshold / 100.0


def _get_spoof_review_threshold() -> int:
    value = getattr(settings, "PERSON_PHOTO_SPOOF_REVIEW_THRESHOLD", 45) or 45
    try:
        return int(value)
    except Exception:
        return 45


def _read_file_bytes(image_file) -> bytes:
    if image_file is None:
        return b""
    if hasattr(image_file, "seek"):
        try:
            image_file.seek(0)
        except Exception:
            pass
    try:
        data = image_file.read() if hasattr(image_file, "read") else b""
    finally:
        if hasattr(image_file, "seek"):
            try:
                image_file.seek(0)
            except Exception:
                pass
    return data or b""


def _clone_image_file(image_file, *, suffix: str = "reference") -> ContentFile:
    data = _read_file_bytes(image_file)
    original_name = str(getattr(image_file, "name", "") or f"{suffix}.jpg")
    stem = Path(original_name).stem or suffix
    return ContentFile(data, name=f"{stem}-{suffix}.jpg")


def _get_primary_reference(person):
    return (
        FaceReference.objects.filter(person=person, role="primary", is_deleted=False)
        .exclude(image="")
        .order_by("created_at")
        .first()
    )


def _get_or_create_primary_reference(person):
    primary = _get_primary_reference(person)
    if primary is not None:
        return primary

    photo = getattr(person, "photo", None)
    if not photo or not getattr(photo, "name", ""):
        return None

    primary = FaceReference.objects.create(
        person=person,
        image=_clone_image_file(photo, suffix="original"),
        role="primary",
        compreface_image_id=str(getattr(person, "face_reference_image_id", "") or "").strip(),
        quality_score=getattr(person, "face_enrollment_quality_score", None),
        notes="Bootstrapped from an existing approved profile photo.",
    )
    return primary


def _is_camera_capture_source(capture_source: str) -> bool:
    return str(capture_source or "").strip().lower() == "camera"


def _build_spoof_rejection_message(quality) -> str:
    flags = list(getattr(quality, "spoof_artifact_flags", ()) or ())
    if getattr(quality, "spoof_risk_score", 0) >= getattr(settings, "PERSON_PHOTO_SPOOF_REJECT_THRESHOLD", 70):
        return "Possible screen, printed photo, or replay attack detected. Capture a live camera photo directly."
    if "screen_ui_bar" in flags or "screen_boundary" in flags:
        return "Possible screen photo detected. Do not photograph a laptop, monitor, or another phone screen."
    return "The image looks like a replay or display capture. Capture a live camera photo directly."


def _is_photo_review_configured(current_reference_photo=None) -> bool:
    if not is_compreface_configured():
        return False
    if not has_compreface_detection_config():
        return False
    if current_reference_photo and not has_compreface_verification_config():
        return False
    return True


def _threshold_to_percent(threshold: float) -> float:
    return round(threshold * 100.0, 2)


def _similarity_to_percent(similarity: float) -> float:
    return round(max(0.0, min(1.0, similarity)) * 100.0, 2)


def _should_keep_as_pending_baseline(message: str, current_reference_photo) -> bool:
    if current_reference_photo and getattr(current_reference_photo, "name", ""):
        return False
    return "No face is found in the given image" in (message or "")

