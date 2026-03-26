import base64
import io
import ipaddress
import json
import math
import re
import secrets
import string
from datetime import timedelta
from typing import Any
from urllib.parse import unquote

from django.core import signing
from django.db import transaction
from django.utils import timezone

from GateCore.models import AccessCredential, GateTerminal, ScheduleRule
from face_devices.models import FaceDeviceRemoteChallenge

import qrcode


REMOTE_CHALLENGE_PREFIX = "GCR1:"
REMOTE_CHALLENGE_SALT = "gatecore.mobile_remotes.challenge.v1"
REMOTE_CHALLENGE_TTL_SECONDS = 90
REMOTE_CHALLENGE_REFRESH_SECONDS = 30
REMOTE_SESSION_MAX_AGE_SECONDS = 60 * 60
REMOTE_USER_COOLDOWN_SECONDS = 45
REMOTE_TERMINAL_COOLDOWN_SECONDS = 6
REMOTE_PROXIMITY_RADIUS_METERS = 250
RESIDENT_PHONE_QR_PREFIX = "GCP1"
RESIDENT_PHONE_QR_TTL_SECONDS = 60
RESIDENT_PHONE_QR_NOTES = "mobile_resident_qr"


def _challenge_claims(challenge: FaceDeviceRemoteChallenge) -> dict[str, Any]:
    return {
        "nonce": challenge.nonce,
    }


def _signed_payload_for_challenge(challenge: FaceDeviceRemoteChallenge) -> str:
    token = signing.dumps(_challenge_claims(challenge), salt=REMOTE_CHALLENGE_SALT, compress=True)
    return f"{REMOTE_CHALLENGE_PREFIX}{token}"


def expire_remote_challenges(*, terminal: GateTerminal | None = None) -> int:
    queryset = FaceDeviceRemoteChallenge.objects.filter(status="active", expires_at__lte=timezone.now())
    if terminal is not None:
        queryset = queryset.filter(terminal=terminal)
    return queryset.update(status="expired", modified_at=timezone.now())


def issue_remote_challenge(
    *,
    terminal: GateTerminal,
    estate_id: str = "",
    platform_id: str = "",
    estate_name: str = "",
) -> dict[str, Any]:
    now = timezone.now()
    expires_at = now + timedelta(seconds=REMOTE_CHALLENGE_TTL_SECONDS)

    with transaction.atomic():
        expire_remote_challenges(terminal=terminal)
        FaceDeviceRemoteChallenge.objects.select_for_update().filter(
            terminal=terminal,
            status="active",
            consumed_at__isnull=True,
        ).update(status="revoked", modified_at=now)
        challenge = FaceDeviceRemoteChallenge.objects.create(
            terminal=terminal,
            device_identifier=terminal.serial_number,
            nonce=secrets.token_urlsafe(18),
            status="active",
            estate_id=str(estate_id or "").strip(),
            platform_id=str(platform_id or "").strip(),
            estate_name=str(estate_name or "").strip(),
            issued_at=now,
            expires_at=expires_at,
        )
        qr_payload = _signed_payload_for_challenge(challenge)
        challenge.challenge_payload = {
            "qr_payload": qr_payload,
            "claims": _challenge_claims(challenge),
        }
        challenge.save(update_fields=["challenge_payload", "modified_at"])

    return {
        "challenge": challenge,
        "qr_payload": qr_payload,
        "expires_at": expires_at,
        "refresh_after_seconds": REMOTE_CHALLENGE_REFRESH_SECONDS,
        "ttl_seconds": REMOTE_CHALLENGE_TTL_SECONDS,
    }


def is_mobile_resident_qr_credential(credential: AccessCredential | None) -> bool:
    if credential is None:
        return False
    return (
        credential.credential_type == "qr"
        and credential.is_temporary
        and str(credential.notes or "").strip().startswith(RESIDENT_PHONE_QR_NOTES)
    )


def mobile_resident_qr_rule_context(rule: ScheduleRule | None) -> dict[str, Any]:
    if rule is None or rule.schedule_kind != "preclearance":
        return {}
    notes = str(rule.notes or "").strip()
    prefix = f"{RESIDENT_PHONE_QR_NOTES}:"
    if not notes.startswith(prefix):
        return {}
    try:
        payload = json.loads(notes[len(prefix):])
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def is_mobile_resident_qr_rule(rule: ScheduleRule | None) -> bool:
    return bool(mobile_resident_qr_rule_context(rule))


def issue_resident_phone_qr(*, person, site=None, user=None) -> dict[str, Any]:
    now = timezone.now()
    expires_at = now + timedelta(seconds=RESIDENT_PHONE_QR_TTL_SECONDS)
    qr_payload = json.dumps({"pin_type": "preclearance"}, separators=(",", ":"))

    with transaction.atomic():
        ScheduleRule.objects.select_for_update().filter(
            visitor=person,
            schedule_kind="preclearance",
            is_active=True,
            is_deleted=False,
            notes__startswith=RESIDENT_PHONE_QR_NOTES,
        ).update(is_active=False, modified_at=now)
        rule = ScheduleRule.objects.create(
            name=f"Resident Mobile QR {person.full_name or person.id}",
            visitor=person,
            visitor_full_name=person.full_name or "",
            visitor_mobile=getattr(person, "phone", "") or "",
            schedule_kind="preclearance",
            valid_from=now.date(),
            created_by=user if getattr(user, "is_authenticated", False) else None,
            modified_by=user if getattr(user, "is_authenticated", False) else None,
            notes=f"{RESIDENT_PHONE_QR_NOTES}:{json.dumps({'site_id': str(getattr(site, 'id', '') or ''), 'expires_at': expires_at.isoformat()}, separators=(',', ':'))}",
        )
        qr_payload = json.dumps({"pin": rule.pin, "pin_type": "preclearance"}, separators=(",", ":"))

    return {
        "rule": rule,
        "qr_payload": qr_payload,
        "qr_image_data_url": qr_code_data_url(qr_payload),
        "expires_at": expires_at,
        "ttl_seconds": RESIDENT_PHONE_QR_TTL_SECONDS,
    }


def extract_remote_challenge_token(scan_value: Any) -> str:
    def _clean_token(value: str) -> str:
        token_text = unquote(str(value or "").strip())
        token_text = re.split(r"[?#&\s]", token_text, maxsplit=1)[0].strip()
        if token_text.startswith(REMOTE_CHALLENGE_PREFIX):
            token_text = token_text[len(REMOTE_CHALLENGE_PREFIX):].strip()
        return token_text

    text = str(scan_value or "").strip()
    if not text:
        return ""
    decoded = unquote(text)
    if decoded.startswith(REMOTE_CHALLENGE_PREFIX):
        return _clean_token(decoded)
    if text.startswith(REMOTE_CHALLENGE_PREFIX):
        return _clean_token(text)
    match = re.search(r"(?:^|[?&])(remote_challenge|gcr1)=([^&#]+)", decoded, flags=re.IGNORECASE)
    if match:
        return _clean_token(match.group(2))
    return ""


def verify_remote_challenge(scan_value: Any) -> tuple[FaceDeviceRemoteChallenge | None, str]:
    expire_remote_challenges()
    token = extract_remote_challenge_token(scan_value)
    if not token:
        return None, "The scanned QR is not a live remote-open challenge."
    try:
        claims = signing.loads(token, salt=REMOTE_CHALLENGE_SALT, max_age=REMOTE_CHALLENGE_TTL_SECONDS + 5)
    except signing.SignatureExpired:
        return None, "The scanned QR challenge has expired. Scan the live TMT screen again."
    except signing.BadSignature:
        return None, "The scanned QR challenge is invalid."

    nonce = str(claims.get("nonce") or "").strip()
    challenge_id = str(claims.get("cid") or "").strip()
    device_identifier = str(claims.get("sn") or "").strip()
    if not nonce:
        return None, "The scanned QR challenge is malformed."

    challenge_query = FaceDeviceRemoteChallenge.objects.select_related("terminal").filter(nonce=nonce)
    if challenge_id:
        challenge_query = challenge_query.filter(id=challenge_id)
    if device_identifier:
        challenge_query = challenge_query.filter(device_identifier=device_identifier)
    challenge = challenge_query.first()
    if challenge is None:
        return None, "The scanned QR challenge no longer exists."
    if challenge.nonce != nonce:
        return None, "The scanned QR challenge failed verification."
    if challenge.status != "active":
        if challenge.status == "consumed":
            return None, "This QR challenge was already used. Scan the live TMT screen again."
        return None, "This QR challenge is no longer active."
    if challenge.consumed_at is not None:
        challenge.status = "consumed"
        challenge.save(update_fields=["status", "modified_at"])
        return None, "This QR challenge was already used. Scan the live TMT screen again."
    if challenge.expires_at <= timezone.now():
        challenge.status = "expired"
        challenge.save(update_fields=["status", "modified_at"])
        return None, "The scanned QR challenge has expired. Scan the live TMT screen again."
    return challenge, ""


def consume_remote_challenge(challenge: FaceDeviceRemoteChallenge, *, user=None) -> FaceDeviceRemoteChallenge:
    with transaction.atomic():
        locked = FaceDeviceRemoteChallenge.objects.select_for_update().get(id=challenge.id)
        if locked.status != "active" or locked.consumed_at is not None or locked.expires_at <= timezone.now():
            if locked.status == "active" and locked.expires_at <= timezone.now():
                locked.status = "expired"
                locked.save(update_fields=["status", "modified_at"])
            raise ValueError("Challenge is no longer active.")
        locked.status = "consumed"
        locked.consumed_at = timezone.now()
        locked.consumed_by = user if getattr(user, "is_authenticated", False) else None
        locked.save(update_fields=["status", "consumed_at", "consumed_by", "modified_at"])
        return locked


def qr_code_data_url(value: str) -> str:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0f172a", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def same_private_subnet(ip_a: str, ip_b: str, prefix: int = 24) -> bool:
    try:
        addr_a = ipaddress.ip_address((ip_a or "").strip())
        addr_b = ipaddress.ip_address((ip_b or "").strip())
    except ValueError:
        return False
    if addr_a.version != 4 or addr_b.version != 4:
        return False
    if not (addr_a.is_private and addr_b.is_private):
        return False
    network_a = ipaddress.ip_network(f"{addr_a}/{prefix}", strict=False)
    network_b = ipaddress.ip_network(f"{addr_b}/{prefix}", strict=False)
    return network_a.network_address == network_b.network_address


def parse_coordinates(value: Any) -> tuple[float | None, float | None]:
    if value is None:
        return None, None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError):
            return None, None
    text = str(value).strip()
    if not text:
        return None, None
    matches = re.findall(r"-?\d+(?:\.\d+)?", text)
    if len(matches) < 2:
        return None, None
    try:
        return float(matches[0]), float(matches[1])
    except ValueError:
        return None, None


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_m * c
