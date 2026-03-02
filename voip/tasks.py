"""
VoIP tasks: Asterisk AMI integration for call origination.

initiate_sip_call connects to Asterisk via AMI, originates a call and
stores the AMI ActionID as provider_call_id on the VoipCall record.
Asterisk is expected to POST back to /api/v1/voip/ami-event/ to update
call_status as the call progresses.
"""
import logging
import socket
import time
import uuid as uuid_mod
from django.utils import timezone

logger = logging.getLogger(__name__)


def _ami_send_originate(host, port, username, secret, channel, context, exten, action_id, timeout_ms=30000):
    """
    Connect to Asterisk AMI, authenticate, send an Originate action and
    return the server response lines.

    Returns a list of response lines on success, raises RuntimeError on
    authentication or connection failure.
    """
    try:
        sock = socket.create_connection((host, port), timeout=10)
    except OSError as exc:
        raise RuntimeError(f"Cannot connect to Asterisk AMI at {host}:{port}: {exc}") from exc

    def _read_until_empty(sock, timeout=5):
        """Read all lines until a blank line (end of AMI message)."""
        sock.settimeout(timeout)
        buf = b""
        max_buf = 65536  # 64 KB cap to prevent memory exhaustion
        while len(buf) < max_buf:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if b"\r\n\r\n" in buf or b"\n\n" in buf:
                    break
            except socket.timeout:
                break
        return buf.decode(errors="replace")

    try:
        # Read AMI banner
        banner = _read_until_empty(sock)
        if "Asterisk Call Manager" not in banner:
            raise RuntimeError(f"Unexpected AMI banner: {banner!r}")

        # Login
        login = (
            f"Action: Login\r\n"
            f"Username: {username}\r\n"
            f"Secret: {secret}\r\n"
            f"\r\n"
        )
        sock.sendall(login.encode())
        login_resp = _read_until_empty(sock)
        if "Success" not in login_resp:
            raise RuntimeError(f"AMI login failed: {login_resp!r}")

        # Originate
        originate = (
            f"Action: Originate\r\n"
            f"ActionID: {action_id}\r\n"
            f"Channel: {channel}\r\n"
            f"Context: {context}\r\n"
            f"Exten: {exten}\r\n"
            f"Priority: 1\r\n"
            f"Timeout: {timeout_ms}\r\n"
            f"Async: true\r\n"
            f"\r\n"
        )
        sock.sendall(originate.encode())
        orig_resp = _read_until_empty(sock)

        # Logoff
        sock.sendall(b"Action: Logoff\r\n\r\n")

        return orig_resp.splitlines()
    finally:
        try:
            sock.close()
        except OSError:
            pass


def initiate_sip_call(call_id, target, account_id, destination=None):
    """
    Originate a SIP call via Asterisk AMI and update the VoipCall record.

    Parameters
    ----------
    call_id : str | UUID
        The VoipCall primary key (UUID).
    target : str
        The phone number to dial (e.g. ``+27656231093``).
    account_id : int
        The Django auth.User pk for the account making the call.
    destination : str, optional
        Alias for *target*; if given, *target* is used as the channel
        number and *destination* as the dialplan extension.
    """
    from django.conf import settings
    from .models import VoipCall

    dest = destination or target
    logger.info(
        "VoIP initiate_sip_call: call_id=%s target=%s destination=%s account_id=%s",
        call_id, target, dest, account_id,
    )

    try:
        call = VoipCall.objects.get(id=call_id)
    except VoipCall.DoesNotExist:
        logger.error("VoIP initiate_sip_call: VoipCall %s not found", call_id)
        return

    action_id = str(uuid_mod.uuid4())

    # Pre-store the action_id so it can be correlated with AMI events even
    # if the process is interrupted after the originate is sent.
    call.provider_call_id = action_id
    call.save(update_fields=["provider_call_id", "updated_at"])

    ami_host = getattr(settings, "ASTERISK_HOST", "127.0.0.1")
    ami_port = getattr(settings, "ASTERISK_AMI_PORT", 5038)
    ami_user = getattr(settings, "ASTERISK_AMI_USER", "admin")
    ami_secret = getattr(settings, "ASTERISK_AMI_SECRET", "")
    trunk = getattr(settings, "ASTERISK_TRUNK", "SIP/trunk")
    context = getattr(settings, "ASTERISK_CONTEXT", "from-internal")

    channel = f"{trunk}/{dest}"

    try:
        response_lines = _ami_send_originate(
            host=ami_host,
            port=ami_port,
            username=ami_user,
            secret=ami_secret,
            channel=channel,
            context=context,
            exten=dest,
            action_id=action_id,
        )
        logger.info(
            "VoIP Asterisk script OK: destination=%s (check Asterisk CLI if no ring: asterisk -rvvv)",
            dest,
        )

        # Use the AMI ActionID as the provider_call_id so we can correlate
        # Asterisk events back to this call record.
        call.provider_call_id = action_id
        call.call_status = "initiated"
        call.started_at = timezone.now()
        call.save(update_fields=["provider_call_id", "call_status", "started_at", "updated_at"])

        logger.info(
            "VoIP call %s initiated: provider_call_id=%s channel=%s",
            call_id, action_id, channel,
        )

    except RuntimeError as exc:
        logger.error("VoIP AMI error for call %s: %s", call_id, exc)
        call.call_status = "failed"
        call.ended_at = timezone.now()
        call.save(update_fields=["call_status", "ended_at", "updated_at"])
