import logging
import threading

from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import VoipCall
from .serializers import VoipCallSerializer
from . import tasks as voip_tasks

logger = logging.getLogger(__name__)


class VoipCallViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    list:   GET  /api/v1/voip/calls/
    create: POST /api/v1/voip/calls/
    retrieve: GET /api/v1/voip/calls/{id}/

    Creating a call triggers an Asterisk AMI Originate action in a
    background thread so the POST returns quickly with the new record.
    """
    serializer_class = VoipCallSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VoipCall.objects.filter(account=self.request.user)

    def perform_create(self, serializer):
        call = serializer.save(
            account=self.request.user,
            started_at=timezone.now(),
        )
        destination = self.request.data.get("destination") or self.request.data.get("target", "")

        # Store destination on the call so callers can see it
        if destination:
            call.destination = destination
            call.save(update_fields=["destination", "updated_at"])

        # Fire off the AMI originate in a daemon thread so the HTTP response
        # is returned immediately (avoids a 30-second timeout on the client).
        thread = threading.Thread(
            target=voip_tasks.initiate_sip_call,
            args=(str(call.id), destination, self.request.user.pk),
            daemon=True,
        )
        thread.start()


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def ami_event_webhook(request):
    """
    Receive Asterisk AMI events and update VoipCall.call_status.

    Asterisk posts events here via the dialplan (e.g. using AGI or
    ``System(curl -s -X POST ...)``).  The expected payload:

    .. code-block:: json

        {
            "event":          "OriginateResponse | Hangup | ...",
            "action_id":      "<AMI ActionID = VoipCall.provider_call_id>",
            "dial_status":    "ANSWER | BUSY | NOANSWER | CANCEL | CONGESTION",
            "uniqueid":       "<optional Asterisk UniqueID>",
            "recording_url":  "<optional>"
        }
    """
    data = request.data
    action_id = data.get("action_id") or data.get("ActionID", "")
    event = (data.get("event") or data.get("Event", "")).lower()
    dial_status = (data.get("dial_status") or data.get("DialStatus", "")).lower()
    recording_url = data.get("recording_url") or data.get("RecordingURL", "")
    uniqueid = data.get("uniqueid") or data.get("Uniqueid", "")

    if not action_id:
        return Response({"detail": "action_id required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        call = VoipCall.objects.get(provider_call_id=action_id)
    except VoipCall.DoesNotExist:
        logger.warning("VoIP ami_event_webhook: no call with provider_call_id=%s", action_id)
        return Response({"detail": "call not found"}, status=status.HTTP_404_NOT_FOUND)

    # Map Asterisk event/dial_status → our call_status
    new_status = _map_asterisk_status(event, dial_status)
    update_fields = ["call_status", "updated_at"]

    if new_status:
        call.call_status = new_status

    if new_status in ("completed", "failed", "busy", "no-answer", "cancelled"):
        call.ended_at = timezone.now()
        update_fields.append("ended_at")

    if uniqueid and not call.provider_call_id:
        # Only store the Asterisk UniqueID if no provider_call_id is set yet
        call.provider_call_id = uniqueid
        update_fields.append("provider_call_id")

    if recording_url:
        call.recording_url = recording_url
        update_fields.append("recording_url")

    call.save(update_fields=update_fields)

    logger.info(
        "VoIP ami_event_webhook: call=%s event=%s dial_status=%s → call_status=%s",
        call.id, event, dial_status, call.call_status,
    )
    return Response(VoipCallSerializer(call).data)


def _map_asterisk_status(event, dial_status):
    """Convert an Asterisk event/dial_status pair to a VoipCall call_status."""
    # OriginateResponse events
    if event == "originateresponse":
        if dial_status in ("answer",):
            return "answered"
        if dial_status in ("busy",):
            return "busy"
        if dial_status in ("noanswer", "no-answer"):
            return "no-answer"
        if dial_status in ("cancel", "cancelled"):
            return "cancelled"
        if dial_status in ("congestion", "failed", "chanunavail"):
            return "failed"
        return "initiated"

    # Dial-begin / ringing
    if event in ("dial", "dialing"):
        return "ringing"

    # Connected
    if event in ("bridge", "bridgecreate", "bridgeenter"):
        return "answered"

    # Hangup
    if event == "hangup":
        if dial_status in ("answer",):
            return "completed"
        if dial_status in ("busy",):
            return "busy"
        if dial_status in ("noanswer", "no-answer"):
            return "no-answer"
        if dial_status in ("cancel",):
            return "cancelled"
        return "completed"

    return ""
