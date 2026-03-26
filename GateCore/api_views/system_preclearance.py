from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from GateCore.services.system_preclearance import get_system_preclearance_config, refresh_system_preclearance_config


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def system_preclearance_api(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    config = get_system_preclearance_config()
    if request.method == "POST":
        refresh_system_preclearance_config(config, rotate_key=True)
        config.refresh_from_db()

    payload = config.payload or {}
    return Response({
        "key": config.key,
        "qr_base64": config.qr_base64,
        "payload": payload,
        "trigger_payload": config.trigger_payload or {"trigger_key": config.key},
        "last_rotated": timezone.localtime(config.last_rotated).isoformat() if config.last_rotated else "",
        "trigger_endpoint": "/api/gatecore/system-preclearance/",
    })
