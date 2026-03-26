import logging

from datetime import timedelta
from urllib.parse import urlencode
from django.conf import settings
from rest_framework.authtoken.models import Token
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from GateCore.models import GateTerminal, Occupancy, Site
from GateCore.services.mobile_remotes import (
    REMOTE_PROXIMITY_RADIUS_METERS,
    RESIDENT_PHONE_QR_TTL_SECONDS,
    REMOTE_TERMINAL_COOLDOWN_SECONDS,
    REMOTE_USER_COOLDOWN_SECONDS,
    consume_remote_challenge,
    haversine_distance_meters,
    issue_remote_challenge,
    issue_resident_phone_qr,
    parse_coordinates,
    qr_code_data_url,
    same_private_subnet,
    verify_remote_challenge,
)
from face_devices.models import FaceDeviceAction, FaceDeviceEvent
from face_devices.services import queue_face_device_action, record_face_device_event

logger = logging.getLogger(__name__)


REMOTE_OPEN_ONLINE_WINDOW_SECONDS = 90
REMOTE_OPEN_ALERT_WINDOW_SECONDS = 300
REMOTE_OPEN_ALERT_THRESHOLD = 5
REMOTE_QR_DISABLED_MESSAGE = "QR remote access is temporarily disabled."


def _qr_remotes_enabled() -> bool:
    return bool(getattr(settings, "MOBILE_REMOTE_QR_ENABLED", False))


def _qr_disabled_response():
    return Response(
        {
            "success": False,
            "detail": REMOTE_QR_DISABLED_MESSAGE,
            "message": REMOTE_QR_DISABLED_MESSAGE,
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    return ""


def _client_ip(request) -> str:
    return (
        (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR")
        or ""
    )


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _terminal_site(terminal: GateTerminal | None):
    if terminal is None:
        return None
    if terminal.site_id:
        return terminal.site
    access_point = getattr(terminal, "access_point", None)
    property_obj = getattr(access_point, "property", None) if access_point else None
    return getattr(property_obj, "site", None) if property_obj else None


def _person_active_site_ids(person) -> set[str]:
    today = timezone.now().date()
    queryset = (
        Occupancy.objects.select_related("unit__property__site")
        .filter(
            person=person,
            is_active=True,
            is_deleted=False,
            start_date__lte=today,
        )
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
    )
    return {
        str(occupancy.unit.property.site_id)
        for occupancy in queryset
        if getattr(getattr(getattr(occupancy, "unit", None), "property", None), "site_id", None)
    }


def _resolve_selected_site(person, requested_site_id: str) -> Site | None:
    accessible_ids = _person_active_site_ids(person)
    if requested_site_id:
        if requested_site_id not in accessible_ids:
            return None
        return Site.objects.filter(id=requested_site_id, is_active=True, is_deleted=False).first()

    if len(accessible_ids) != 1:
        return None
    only_id = next(iter(accessible_ids))
    return Site.objects.filter(id=only_id, is_active=True, is_deleted=False).first()


def _is_terminal_online(terminal: GateTerminal) -> bool:
    seen_at = terminal.last_heartbeat_at or terminal.last_seen_at
    if seen_at is None:
        return False
    return (timezone.now() - seen_at).total_seconds() <= REMOTE_OPEN_ONLINE_WINDOW_SECONDS


def _request_token(request) -> Token | None:
    auth_obj = getattr(request, "auth", None)
    if isinstance(auth_obj, Token):
        return auth_obj
    token_key = _stringify(auth_obj)
    if not token_key:
        header = _stringify(request.META.get("HTTP_AUTHORIZATION"))
        if header.lower().startswith("token "):
            token_key = header.split(" ", 1)[1].strip()
    if not token_key:
        return None
    return Token.objects.filter(key=token_key).first()


def _reference_coordinates(terminal: GateTerminal | None) -> tuple[float | None, float | None, int]:
    if terminal is None:
        return None, None, REMOTE_PROXIMITY_RADIUS_METERS
    config = terminal.config if isinstance(terminal.config, dict) else {}
    radius = int(config.get("remote_open_radius_meters") or REMOTE_PROXIMITY_RADIUS_METERS)

    lat = _float_or_none(config.get("remote_open_latitude"))
    lon = _float_or_none(config.get("remote_open_longitude"))
    if lat is not None and lon is not None:
        return lat, lon, radius

    access_point = getattr(terminal, "access_point", None)
    lat, lon = parse_coordinates(getattr(access_point, "location_coordinates", ""))
    return lat, lon, radius


def _proximity_check(request, terminal: GateTerminal) -> dict:
    remote_ip = _client_ip(request)
    terminal_ip = _stringify(terminal.ip_address)
    same_subnet = same_private_subnet(remote_ip, terminal_ip)

    latitude = _float_or_none(
        request.data.get("latitude")
        or request.data.get("lat")
        or request.data.get("device_latitude")
    )
    longitude = _float_or_none(
        request.data.get("longitude")
        or request.data.get("lng")
        or request.data.get("device_longitude")
    )

    ref_lat, ref_lon, radius_m = _reference_coordinates(terminal)
    geofence_ok = False
    distance_m = None
    if latitude is not None and longitude is not None and ref_lat is not None and ref_lon is not None:
        distance_m = round(haversine_distance_meters(latitude, longitude, ref_lat, ref_lon), 2)
        geofence_ok = distance_m <= float(radius_m)

    return {
        "client_ip": remote_ip,
        "terminal_ip": terminal_ip,
        "same_private_subnet": same_subnet,
        "latitude": latitude,
        "longitude": longitude,
        "reference_latitude": ref_lat,
        "reference_longitude": ref_lon,
        "distance_meters": distance_m,
        "radius_meters": radius_m,
        "geofence_ok": geofence_ok,
        "passed": same_subnet or geofence_ok,
    }


def _recent_remote_open_for_user(user) -> bool:
    return FaceDeviceAction.objects.filter(
        action="open_door",
        requested_by=user,
        created_at__gte=timezone.now() - timedelta(seconds=REMOTE_USER_COOLDOWN_SECONDS),
    ).exclude(status__in=["error", "timeout"]).exists()


def _recent_remote_open_for_terminal(terminal: GateTerminal) -> bool:
    return FaceDeviceAction.objects.filter(
        action="open_door",
        terminal=terminal,
        created_at__gte=timezone.now() - timedelta(seconds=REMOTE_TERMINAL_COOLDOWN_SECONDS),
    ).exclude(status__in=["error", "timeout"]).exists()


def _record_remote_denial(*, terminal: GateTerminal | None, device_identifier: str, payload: dict, reason: str) -> None:
    record_face_device_event(
        terminal=terminal,
        device_identifier=device_identifier,
        direction="inbound",
        command="mobileRemoteOpenDenied",
        payload=payload,
        status="error",
        remote_ip=_stringify(payload.get("client_ip")) or None,
        error=reason,
    )
    if terminal is None:
        return
    recent_failures = FaceDeviceEvent.objects.filter(
        terminal=terminal,
        command="mobileRemoteOpenDenied",
        status="error",
        event_time__gte=timezone.now() - timedelta(seconds=REMOTE_OPEN_ALERT_WINDOW_SECONDS),
    ).count()
    if recent_failures >= REMOTE_OPEN_ALERT_THRESHOLD and not FaceDeviceEvent.objects.filter(
        terminal=terminal,
        command="mobileRemoteOpenAlert",
        event_time__gte=timezone.now() - timedelta(minutes=2),
    ).exists():
        record_face_device_event(
            terminal=terminal,
            device_identifier=device_identifier,
            direction="outbound",
            command="mobileRemoteOpenAlert",
            payload={
                "reason": "Repeated mobile remote open denials detected.",
                "recent_failures": recent_failures,
            },
            status="error",
            error="Repeated mobile remote open denials detected.",
        )


def _scan_preview(scan_value: str, limit: int = 180) -> str:
    text = _stringify(scan_value)
    if not text:
        return "<empty>"
    return text if len(text) <= limit else f"{text[:limit]}..."


def _preferred_site_terminal(site: Site | None) -> GateTerminal | None:
    if site is None:
        return None
    direct = (
        GateTerminal.objects.select_related("site", "access_point__property__site")
        .filter(
            site=site,
            approval_status="approved",
            is_active=True,
            is_deleted=False,
        )
        .order_by("-last_heartbeat_at", "-last_seen_at", "display_name", "serial_number")
        .first()
    )
    if direct is not None:
        return direct
    return (
        GateTerminal.objects.select_related("site", "access_point__property__site")
        .filter(
            access_point__property__site=site,
            approval_status="approved",
            is_active=True,
            is_deleted=False,
        )
        .order_by("-last_heartbeat_at", "-last_seen_at", "display_name", "serial_number")
        .first()
    )


def _site_estate_id(site: Site | None, terminal: GateTerminal | None) -> str:
    config = terminal.config if terminal and isinstance(terminal.config, dict) else {}
    for key in ("estate_id", "platform_id"):
        value = _stringify(config.get(key))
        if value:
            return value
    return "1" if site is not None else ""


def _site_platform_id(site: Site | None, terminal: GateTerminal | None) -> str:
    config = terminal.config if terminal and isinstance(terminal.config, dict) else {}
    value = _stringify(config.get("platform_id"))
    if value:
        return value
    return _site_estate_id(site, terminal)


def _resident_phone_qr_url(request, *, site: Site | None, terminal: GateTerminal | None, pin_value: str) -> str:
    query: list[tuple[str, str]] = []
    estate_id = _site_estate_id(site, terminal)
    if estate_id:
        query.append(("estate_id", estate_id))
    if terminal and terminal.serial_number:
        query.append(("sn", terminal.serial_number))
    if pin_value:
        query.append(("pin", pin_value))
        query.append(("password", pin_value))
    query.append(("pin_type", "preclearance"))
    suffix = f"?{urlencode(query)}" if query else ""
    return request.build_absolute_uri(f"/visitor/application-entry/{suffix}")


def _platform_visitor_qr_url(request, *, site: Site | None, terminal: GateTerminal | None) -> str:
    query: list[tuple[str, str]] = []
    estate_id = _site_estate_id(site, terminal)
    if estate_id:
        query.append(("estate_id", estate_id))
    if terminal and terminal.serial_number:
        query.append(("sn", terminal.serial_number))
    suffix = f"?{urlencode(query)}" if query else ""
    return request.build_absolute_uri(f"/visitor/application-entry/{suffix}")


def _terminal_for_identifier(device_identifier: str) -> GateTerminal | None:
    if not device_identifier:
        return None
    return GateTerminal.objects.select_related("site", "access_point__property__site").filter(
        serial_number=device_identifier,
        is_active=True,
        is_deleted=False,
    ).first()


@api_view(["GET"])
@permission_classes([AllowAny])
def mobile_remote_challenge_screen(request):
    if not _qr_remotes_enabled():
        return _qr_disabled_response()

    device_identifier = _stringify(request.query_params.get("sn") or request.GET.get("sn"))
    if not device_identifier:
        return Response({"detail": "sn is required."}, status=status.HTTP_400_BAD_REQUEST)

    terminal = _terminal_for_identifier(device_identifier)
    if terminal is None:
        return Response({"detail": "Unknown terminal."}, status=status.HTTP_404_NOT_FOUND)

    estate_id = _stringify(request.query_params.get("estate_id") or request.GET.get("estate_id"))
    platform_id = _stringify(request.query_params.get("platform_id") or request.GET.get("platform_id")) or estate_id
    estate_name = _stringify(request.query_params.get("estate_name") or request.GET.get("estate_name"))
    if not estate_name:
        terminal_site = _terminal_site(terminal)
        estate_name = terminal_site.name if terminal_site else ""

    issued = issue_remote_challenge(
        terminal=terminal,
        estate_id=estate_id,
        platform_id=platform_id,
        estate_name=estate_name,
    )
    challenge = issued["challenge"]
    image_data_url = qr_code_data_url(issued["qr_payload"])
    client_ip = _client_ip(request)

    update_fields = ["last_seen_at"]
    terminal.last_seen_at = timezone.now()
    if client_ip and terminal.ip_address != client_ip:
        terminal.ip_address = client_ip
        update_fields.append("ip_address")
    terminal.save(update_fields=update_fields)

    record_face_device_event(
        terminal=terminal,
        device_identifier=terminal.serial_number,
        direction="outbound",
        command="mobileRemoteChallengeIssued",
        payload={
            "challenge_id": str(challenge.id),
            "estate_id": estate_id,
            "platform_id": platform_id,
            "expires_at": issued["expires_at"].isoformat(),
            "ttl_seconds": issued["ttl_seconds"],
            "refresh_after_seconds": issued["refresh_after_seconds"],
        },
        status="sent",
        remote_ip=client_ip or None,
    )
    return Response(
        {
            "success": True,
            "challenge_id": str(challenge.id),
            "device_identifier": terminal.serial_number,
            "expires_at": issued["expires_at"].isoformat(),
            "ttl_seconds": issued["ttl_seconds"],
            "refresh_after_seconds": issued["refresh_after_seconds"],
            "qr_payload": issued["qr_payload"],
            "qr_image_data_url": image_data_url,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mobile_issue_resident_qr(request):
    if not _qr_remotes_enabled():
        return _qr_disabled_response()

    person = getattr(request.user, "person_profile", None)
    if person is None:
        return Response(
            {"detail": "Authenticated user is not linked to a resident profile."},
            status=status.HTTP_403_FORBIDDEN,
        )

    selected_site = _resolve_selected_site(person, _stringify(request.data.get("site_id")))
    if selected_site is None:
        return Response(
            {"detail": "This app session is not authorized for the requested site."},
            status=status.HTTP_403_FORBIDDEN,
        )

    issued = issue_resident_phone_qr(person=person, site=selected_site, user=request.user)
    target_terminal = _preferred_site_terminal(selected_site)
    qr_payload = _resident_phone_qr_url(
        request,
        site=selected_site,
        terminal=target_terminal,
        pin_value=issued["rule"].pin,
    )
    return Response(
        {
            "success": True,
            "message": "Show this QR to the TMT camera before it expires.",
            "schedule_rule_id": str(issued["rule"].id),
            "credential_id": str(issued["rule"].id),
            "qr_payload": qr_payload,
            "qr_image_data_url": qr_code_data_url(qr_payload),
            "expires_at": issued["expires_at"].isoformat(),
            "ttl_seconds": RESIDENT_PHONE_QR_TTL_SECONDS,
            "selected_site": {
                "id": str(selected_site.id),
                "name": selected_site.name,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mobile_issue_platform_visitor_qr(request):
    if not _qr_remotes_enabled():
        return _qr_disabled_response()

    person = getattr(request.user, "person_profile", None)
    if person is None:
        return Response(
            {"detail": "Authenticated user is not linked to a resident profile."},
            status=status.HTTP_403_FORBIDDEN,
        )

    selected_site = _resolve_selected_site(person, _stringify(request.data.get("site_id")))
    if selected_site is None:
        return Response(
            {"detail": "This app session is not authorized for the requested site."},
            status=status.HTTP_403_FORBIDDEN,
        )

    target_terminal = _preferred_site_terminal(selected_site)
    if target_terminal is None:
        return Response(
            {"detail": "No approved terminal is linked to the requested site."},
            status=status.HTTP_409_CONFLICT,
        )

    qr_payload = _platform_visitor_qr_url(
        request,
        site=selected_site,
        terminal=target_terminal,
    )
    return Response(
        {
            "success": True,
            "message": (
                "Show this visitor application-entry QR to the TMT camera. "
                "If the firmware accepts the format, it should reach the backend instead of saying wrong format."
            ),
            "qr_payload": qr_payload,
            "qr_image_data_url": qr_code_data_url(qr_payload),
            "application_entry_url": qr_payload,
            "estate_id": _site_estate_id(selected_site, target_terminal),
            "platform_id": _site_platform_id(selected_site, target_terminal),
            "selected_site": {
                "id": str(selected_site.id),
                "name": selected_site.name,
            },
            "terminal": {
                "id": str(target_terminal.id),
                "serial_number": target_terminal.serial_number,
                "display_name": target_terminal.display_name,
                "access_point_name": getattr(getattr(target_terminal, "access_point", None), "name", ""),
                "online": _is_terminal_online(target_terminal),
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mobile_scan_remote_qr(request):
    if not _qr_remotes_enabled():
        return _qr_disabled_response()

    person = getattr(request.user, "person_profile", None)
    if person is None:
        return Response(
            {"detail": "Authenticated user is not linked to a resident profile."},
            status=status.HTTP_403_FORBIDDEN,
        )

    scan_value = _stringify(
        request.data.get("qr_payload")
        or request.data.get("qr_data")
        or request.data.get("scan_value")
        or request.data.get("value")
    )
    if not scan_value:
        return Response({"detail": "qr_payload is required."}, status=status.HTTP_400_BAD_REQUEST)

    selected_site = _resolve_selected_site(person, _stringify(request.data.get("site_id")))
    if selected_site is None:
        return Response(
            {"detail": "This app session is not authorized for the requested site."},
            status=status.HTTP_403_FORBIDDEN,
        )

    challenge, challenge_error = verify_remote_challenge(scan_value)
    if challenge is None:
        scan_preview = _scan_preview(scan_value)
        logger.warning(
            "mobile remote denied: invalid challenge person=%s site=%s scan_preview=%s reason=%s",
            getattr(person, "id", ""),
            getattr(selected_site, "id", ""),
            scan_preview,
            challenge_error,
        )
        _record_remote_denial(
            terminal=None,
            device_identifier="unknown",
            payload={
                "person_id": str(person.id),
                "person_name": person.full_name,
                "site_id": str(selected_site.id),
                "site_name": selected_site.name,
                "scan_value": scan_preview,
                "client_ip": _client_ip(request),
            },
            reason=challenge_error,
        )
        status_code = status.HTTP_409_CONFLICT if "expired" in challenge_error.lower() or "already used" in challenge_error.lower() else status.HTTP_400_BAD_REQUEST
        return Response(
            {
                "detail": f"{challenge_error} Scan preview: {scan_preview}",
                "scan_preview": scan_preview,
            },
            status=status_code,
        )

    terminal = challenge.terminal or _terminal_for_identifier(challenge.device_identifier)
    device_identifier = challenge.device_identifier
    if terminal is None:
        _record_remote_denial(
            terminal=None,
            device_identifier=device_identifier,
            payload={"challenge_id": str(challenge.id), "client_ip": _client_ip(request)},
            reason="The scanned QR challenge is not linked to an active terminal.",
        )
        return Response(
            {"detail": "The scanned QR challenge is not linked to an active terminal."},
            status=status.HTTP_404_NOT_FOUND,
        )

    terminal_site = _terminal_site(terminal)
    if terminal_site is None:
        reason = "The scanned terminal is not linked to a site."
        _record_remote_denial(
            terminal=terminal,
            device_identifier=device_identifier,
            payload={"challenge_id": str(challenge.id), "client_ip": _client_ip(request)},
            reason=reason,
        )
        return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)
    if str(terminal_site.id) != str(selected_site.id):
        reason = "The scanned terminal belongs to a different site."
        _record_remote_denial(
            terminal=terminal,
            device_identifier=device_identifier,
            payload={
                "challenge_id": str(challenge.id),
                "client_ip": _client_ip(request),
                "selected_site_id": str(selected_site.id),
                "terminal_site_id": str(terminal_site.id),
            },
            reason=reason,
        )
        return Response({"detail": reason}, status=status.HTTP_403_FORBIDDEN)
    if not terminal.is_approved:
        reason = "The scanned terminal is not approved for remote access."
        _record_remote_denial(
            terminal=terminal,
            device_identifier=device_identifier,
            payload={"challenge_id": str(challenge.id), "client_ip": _client_ip(request)},
            reason=reason,
        )
        return Response({"detail": reason}, status=status.HTTP_409_CONFLICT)
    if not _is_terminal_online(terminal):
        reason = "The scanned terminal is offline. Ask the device to reconnect before retrying."
        _record_remote_denial(
            terminal=terminal,
            device_identifier=device_identifier,
            payload={"challenge_id": str(challenge.id), "client_ip": _client_ip(request)},
            reason=reason,
        )
        return Response({"detail": reason}, status=status.HTTP_409_CONFLICT)

    proximity = _proximity_check(request, terminal)
    if not proximity["passed"]:
        reason = "Remote open requires gate proximity. Connect on the same local network or move inside the site geofence."
        _record_remote_denial(
            terminal=terminal,
            device_identifier=device_identifier,
            payload={
                "challenge_id": str(challenge.id),
                "person_id": str(person.id),
                "person_name": person.full_name,
                "site_id": str(selected_site.id),
                "site_name": selected_site.name,
                **proximity,
            },
            reason=reason,
        )
        return Response(
            {
                "detail": reason,
                "proximity": proximity,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if _recent_remote_open_for_user(request.user):
        reason = f"Remote open is cooling down for this user. Wait about {REMOTE_USER_COOLDOWN_SECONDS} seconds before retrying."
        _record_remote_denial(
            terminal=terminal,
            device_identifier=device_identifier,
            payload={"challenge_id": str(challenge.id), "person_id": str(person.id), **proximity},
            reason=reason,
        )
        return Response({"detail": reason}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    if _recent_remote_open_for_terminal(terminal):
        reason = f"This terminal was opened remotely moments ago. Wait about {REMOTE_TERMINAL_COOLDOWN_SECONDS} seconds before retrying."
        _record_remote_denial(
            terminal=terminal,
            device_identifier=device_identifier,
            payload={"challenge_id": str(challenge.id), "person_id": str(person.id), **proximity},
            reason=reason,
        )
        return Response({"detail": reason}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    try:
        challenge = consume_remote_challenge(challenge, user=request.user)
    except ValueError:
        return Response(
            {"detail": "This QR challenge is no longer active. Scan the live TMT screen again."},
            status=status.HTTP_409_CONFLICT,
        )

    token = _request_token(request)
    token_age_seconds = int((timezone.now() - token.created).total_seconds()) if token and token.created else None

    action_payload = {
        "value": "on",
        "command_name": "setDoor",
        "source": "mobile_remote_qr",
        "challenge_mode": "live_screen_challenge",
        "person_id": str(person.id),
        "person_name": person.full_name,
        "site_id": str(selected_site.id),
        "site_name": selected_site.name,
        "estate_id": challenge.estate_id,
        "platform_id": challenge.platform_id,
        "challenge_id": str(challenge.id),
        "requested_at": timezone.now().isoformat(),
        "proximity": proximity,
        "session_token_age_seconds": token_age_seconds if token_age_seconds is not None else "",
    }
    action = queue_face_device_action(
        terminal=terminal,
        action="open_door",
        request_payload=action_payload,
        requested_by=request.user,
    )
    record_face_device_event(
        terminal=terminal,
        device_identifier=terminal.serial_number,
        direction="outbound",
        command="mobileRemoteOpenRequest",
        payload={
            "action_id": str(action.id),
            "challenge_id": str(challenge.id),
            "person_id": str(person.id),
            "person_name": person.full_name,
            "site_id": str(selected_site.id),
            "site_name": selected_site.name,
            "command_name": "setDoor",
            "delivery_mode": "heartbeat_queue",
            "challenge_mode": "live_screen_challenge",
            "proximity": proximity,
        },
        status="sent",
        remote_ip=proximity["client_ip"] or None,
    )
    return Response(
        {
            "success": True,
            "authorized": True,
            "action_enqueued": True,
            "remote_open_supported": True,
            "delivery_mode": "heartbeat_queue",
            "message": "Remote door open queued for the scanned terminal.",
            "action": {
                "id": str(action.id),
                "status": action.status,
                "command_name": "setDoor",
                "value": "on",
            },
            "terminal": {
                "id": str(terminal.id),
                "serial_number": terminal.serial_number,
                "display_name": terminal.display_name,
                "direction": terminal.direction,
                "site_id": str(terminal_site.id),
                "site_name": terminal_site.name,
                "access_point_name": terminal.access_point.name if terminal.access_point else "",
                "online": True,
            },
            "selected_site": {
                "id": str(selected_site.id),
                "name": selected_site.name,
            },
            "challenge": {
                "id": str(challenge.id),
                "expires_at": challenge.expires_at.isoformat(),
                "consumed_at": challenge.consumed_at.isoformat() if challenge.consumed_at else "",
                "mode": "live_screen_challenge",
            },
            "proximity": proximity,
        },
        status=status.HTTP_200_OK,
    )
