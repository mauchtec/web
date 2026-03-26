from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from GateCore.services.photo_quality import PhotoQualityError, assess_photo_quality


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def assess_person_photo_quality(request):
    photo = request.FILES.get("photo") or request.FILES.get("image") or request.FILES.get("file")
    if photo is None:
        return Response({"success": False, "detail": "photo is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        quality = assess_photo_quality(photo)
    except PhotoQualityError as exc:
        return Response({"success": False, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "success": True,
            "quality_score": quality.score,
            "quality_percent": quality.score,
            "quality_threshold": quality.threshold,
            "quality_reasons": list(quality.reasons),
            "spoof_risk_score": quality.spoof_risk_score,
            "spoof_artifact_flags": list(quality.spoof_artifact_flags),
            "is_acceptable": quality.is_acceptable,
            "assessment": quality.as_dict(),
        }
    )
