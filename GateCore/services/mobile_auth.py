import logging
import random
import string
import re
import uuid
from xml.sax.saxutils import escape
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.authtoken.models import Token
from workflows.models import Workflow
from GateCore.models import SMSDeliveryLog
from GateCore.models.people import Person
from GateCore.services.runtime_settings import should_send_visitor_sms

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_CHARACTERS = string.digits

COUNTRY_DIAL_CODES = {
    "ZA": "27",
    "US": "1",
    "CA": "1",
    "GB": "44",
    "IE": "353",
    "AU": "61",
    "NZ": "64",
    "IN": "91",
    "AE": "971",
}


def _parse_sms_portal_client_id(value) -> int:
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        pass
    try:
        parsed = uuid.UUID(text)
        first_block = str(parsed).split("-")[0]
        return int(first_block)
    except Exception:
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return 0
        return int(digits[:10])


def _resolve_country_code(country_hint: str | None = None) -> str:
    default_code = str(getattr(settings, "SEND_SMS_DEFAULT_COUNTRY_CODE", "27") or "27")
    default_code = re.sub(r"\D", "", default_code) or "27"
    if not country_hint:
        return default_code
    raw = str(country_hint).strip()
    if not raw:
        return default_code
    digits = re.sub(r"\D", "", raw)
    if digits:
        return digits
    iso = raw.upper()
    return COUNTRY_DIAL_CODES.get(iso, default_code)


def normalize_phone(phone: str | None, country_hint: str | None = None) -> str:
    if not phone:
        return ""
    raw = str(phone).strip()
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""

    # Keep internal PBX extensions stable instead of forcing country-code normalization.
    if re.fullmatch(r"\d{3,5}", raw) or (raw.isdigit() and 3 <= len(raw) <= 5):
        return digits

    if raw.startswith("+"):
        return f"+{digits}"
    if digits.startswith("00"):
        return f"+{digits[2:]}"

    # Local-format numbers (leading 0) should use configured site default country code.
    # This avoids device-locale mistakes (e.g., locale US but South African local numbers).
    if digits.startswith("0"):
        country_code = _resolve_country_code(None)
    else:
        country_code = _resolve_country_code(country_hint)
    local_digits = digits.lstrip("0")
    if not local_digits:
        return ""

    if local_digits.startswith(country_code):
        return f"+{local_digits}"
    return f"+{country_code}{local_digits}"


def phone_numbers_equal(raw: str | None, candidate: str) -> bool:
    return normalize_phone(raw) == normalize_phone(candidate)


def build_photo_display_url(photo_field) -> str:
    if not photo_field:
        return ""

    try:
        return photo_field.url
    except Exception:
        return ""


def generate_otp(length: int = OTP_LENGTH) -> str:
    return "".join(random.choice(OTP_CHARACTERS) for _ in range(length))


def is_otp_valid(person) -> bool:
    created = person.phone_otp_created
    if not created:
        return False
    expiration = getattr(settings, "PHONE_OTP_EXPIRATION_MINUTES", 5)
    deadline = created + timedelta(minutes=expiration)
    return timezone.now() <= deadline


def _create_sms_log(phone: str, message: str, provider: str, context: dict | None) -> SMSDeliveryLog:
    context = context or {}
    person = context.get("person")
    unit = context.get("unit")
    schedule_rule = context.get("schedule_rule")
    context_data = context.get("context_data") if isinstance(context.get("context_data"), dict) else {}
    return SMSDeliveryLog.objects.create(
        trigger=str(context.get("trigger") or ""),
        provider=provider or "",
        status="attempt",
        recipient_phone=phone or "",
        recipient_name=str(context.get("recipient_name") or ""),
        message=message,
        person=person if getattr(person, "pk", None) else None,
        unit=unit if getattr(unit, "pk", None) else None,
        visitor_name=str(context.get("visitor_name") or ""),
        visitor_phone=str(context.get("visitor_phone") or ""),
        schedule_rule=schedule_rule if getattr(schedule_rule, "pk", None) else None,
        context_data=context_data,
    )


def _finalize_sms_log(
    log_entry: SMSDeliveryLog,
    *,
    status_value: str,
    provider_message_id: str = "",
    error_message: str = "",
) -> None:
    log_entry.status = status_value
    log_entry.provider_message_id = provider_message_id[:120]
    log_entry.error_message = error_message
    log_entry.completed_at = timezone.now()
    log_entry.save(update_fields=["status", "provider_message_id", "error_message", "completed_at", "modified_at"])


def send_sms(phone: str, message: str, context: dict | None = None) -> None:
    context = context or {}
    provider = getattr(settings, "SMS_GATEWAY_PROVIDER", "console")
    config = getattr(settings, "SMS_GATEWAY_CONFIG", {})
    trigger = str(context.get("trigger") or "").strip()
    if not should_send_visitor_sms(trigger):
        logger.info("Skipping SMS to %s because trigger %s is disabled by runtime settings", phone, trigger or "<missing>")
        return
    enforce_logged_path = bool(getattr(settings, "SEND_SMS_ENFORCE_LOGGED_PATH", True))
    allowed_triggers = set(getattr(settings, "SEND_SMS_ALLOWED_TRIGGERS", []))

    log_entry = _create_sms_log(phone, message, provider, context)
    if enforce_logged_path and trigger not in allowed_triggers:
        _finalize_sms_log(
            log_entry,
            status_value="failure",
            error_message=f"Blocked: unapproved SMS trigger '{trigger or 'missing'}'",
        )
        logger.warning("Blocked SMS send to %s due to unapproved trigger: %s", phone, trigger or "<missing>")
        return

    if provider == "infobip":
        try:
            info = config.get("infobip", {})
            headers = {
                "Authorization": f"App {info.get('api_key')}",
                "Content-Type": "application/json",
            }
            payload = {
                "messages": [
                    {
                        "from": info.get("sender", "AccessControll"),
                        "destinations": [{"to": phone}],
                        "text": message,
                    }
                ]
            }
            response = requests.post(info.get("base_url", ""), json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            _finalize_sms_log(log_entry, status_value="success", provider_message_id=str(response.status_code))
            logger.info("Sent OTP via Infobip to %s", phone)
            return
        except Exception as exc:
            _finalize_sms_log(log_entry, status_value="failure", error_message=str(exc))
            logger.warning("Failed to send Infobip SMS: %s", exc)
            return
    elif provider == "stouf":
        try:
            stouf = config.get("stouf", {})
            endpoint = stouf.get("endpoint") or getattr(settings, "SEND_SMS_URL", "")
            if endpoint.lower().endswith("/sendquicksms"):
                endpoint = endpoint[: -len("/sendquicksms")]
            username = stouf.get("username") or getattr(settings, "SEND_SMS_USERNAME", "")
            password = stouf.get("password") or getattr(settings, "SEND_SMS_PASSWORD", "")
            app_name = getattr(settings, "SEND_SMS_APP_NAME", username)
            customer_id = getattr(settings, "SMS_PORTAL_API_SECRET", "")
            client_id = _parse_sms_portal_client_id(getattr(settings, "SMS_PORTAL_CLIENT_ID", ""))

            # The live Stouf WSDL exposes SendSMSSimple under nux.co.za namespace.
            body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <SendSMSSimple xmlns="http://nux.co.za/webservices/">
      <eMail>{escape(username)}</eMail>
      <appName>{escape(app_name)}</appName>
      <Password>{escape(password)}</Password>
      <CustomerId>{escape(str(customer_id))}</CustomerId>
      <ClientId>{client_id}</ClientId>
      <TelNo>{escape(phone)}</TelNo>
      <ContactName>Visitor</ContactName>
      <Message>{escape(message)}</Message>
    </SendSMSSimple>
  </soap:Body>
</soap:Envelope>"""
            headers = {
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "http://nux.co.za/webservices/SendSMSSimple",
            }
            response = requests.post(
                endpoint, data=body, headers=headers, timeout=10
            )
            response.raise_for_status()
            match = re.search(r"<SendSMSSimpleResult>(-?\d+)</SendSMSSimpleResult>", response.text or "")
            result_code = int(match.group(1)) if match else None
            if result_code is not None and result_code > 0:
                _finalize_sms_log(log_entry, status_value="success", provider_message_id=str(result_code))
                logger.info("Sent OTP via Stouf to %s (seq=%s)", phone, result_code)
            else:
                _finalize_sms_log(
                    log_entry,
                    status_value="failure",
                    provider_message_id="" if result_code is None else str(result_code),
                    error_message=f"Non-success provider result: {result_code}",
                )
                logger.warning("Stouf accepted request but returned non-success result for %s: %s", phone, result_code)
            return
        except Exception as exc:
            _finalize_sms_log(log_entry, status_value="failure", error_message=str(exc))
            logger.warning("Failed to send Stouf SMS: %s", exc)
            return
    _finalize_sms_log(log_entry, status_value="success", provider_message_id="mock")
    logger.info("SMS to %s (mock): %s", phone, message)


def _person_in_workflow_access_group(person):
    """
    True if person should get workflow access (Operator) on mobile login.

    Rules:
    - If at least one GateCore Group has grants_workflow_access=True, units in those groups grant workflow access.
    - If at least one Unit has permissions='security', those units grant workflow access (unit-level inheritance).
    - Backward compatible: if neither of the above exists, everyone gets workflow access.
    """
    from GateCore.models.groups import Group as GateCoreGroup
    from GateCore.models import UnitGroupMembership
    from GateCore.models import Occupancy
    from GateCore.models import Unit

    workflow_groups = GateCoreGroup.objects.filter(
        grants_workflow_access=True, is_active=True, is_deleted=False
    )
    security_units = Unit.objects.filter(
        permissions="security", is_active=True, is_deleted=False
    ).values_list("id", flat=True).distinct()

    # If no unit-level or group-level configuration exists, default to allow (legacy behavior).
    if not workflow_groups.exists() and not security_units.exists():
        return True

    group_unit_ids = UnitGroupMembership.objects.filter(
        group__in=workflow_groups, is_active=True, is_deleted=False
    ).values_list("unit_id", flat=True).distinct()

    unit_ids = set(group_unit_ids) | set(security_units)
    return Occupancy.objects.filter(
        person=person,
        unit_id__in=unit_ids,
        is_active=True,
        is_deleted=False,
    ).exists()


def ensure_mobile_user(person):
    User = get_user_model()
    workflow_ct = ContentType.objects.get_for_model(Workflow)
    view_perm, _ = Permission.objects.get_or_create(
        codename="view_workflow",
        content_type=workflow_ct,
        defaults={"name": "Can view workflow"},
    )
    operator_group, _ = Group.objects.get_or_create(name="Operator")
    operator_group.permissions.add(view_perm)

    give_operator = _person_in_workflow_access_group(person)

    if person.user:
        user = person.user
        updated_fields = []
        if not user.is_active:
            user.is_active = True
            updated_fields.append("is_active")
        if not user.is_staff:
            user.is_staff = True
            updated_fields.append("is_staff")
        if updated_fields:
            user.save(update_fields=updated_fields)
        if give_operator and not user.groups.filter(name=operator_group.name).exists():
            user.groups.add(operator_group)
        elif not give_operator and user.groups.filter(name=operator_group.name).exists():
            user.groups.remove(operator_group)
        return user

    username_base = f"mobile-{person.id}"
    username = username_base
    suffix = 0
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{username_base}-{suffix}"

    password = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=person.first_name,
        last_name=person.last_name,
    )
    user.is_active = True
    user.is_staff = True
    user.save(update_fields=["is_active", "is_staff"])
    person.user = user
    # Use queryset update to avoid Person.save()/full_clean() when Person has blank last_name etc.
    Person.objects.filter(pk=person.pk).update(user=user)
    if give_operator:
        user.groups.add(operator_group)
    return user


def build_token_response(user, person, site, unit=None, request=None):
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    photo_url = build_photo_display_url(getattr(person, "photo", None))
    photo_review_attempt_url = build_photo_display_url(getattr(person, "photo_review_attempt", None))
    payload = {
        "token": token.key,
        "site": {
            "id": str(site.id),
            "name": site.name,
            "code": site.code,
        },
        "person": {
            "id": str(person.id),
            "full_name": person.full_name,
            "phone": person.phone,
            "card_number": getattr(person, "card_number", "") or "",
            "photo_url": photo_url,
            "photo_review_attempt_url": photo_review_attempt_url,
            "face_provider": getattr(person, "face_provider", "") or "",
            "face_subject_id": getattr(person, "face_subject_id", "") or "",
            "face_enrollment_status": getattr(person, "face_enrollment_status", "not_started") or "not_started",
            "face_enrollment_status_display": person.get_face_enrollment_status_display() if getattr(person, "face_enrollment_status", "") else "",
            "face_enrollment_quality_score": str(person.face_enrollment_quality_score) if getattr(person, "face_enrollment_quality_score", None) is not None else "",
            "photo_quality_score": str(person.face_enrollment_quality_score) if getattr(person, "face_enrollment_quality_score", None) is not None else "",
            "access_expires_on": person.access_expires_on.isoformat() if getattr(person, "access_expires_on", None) else "",
            "face_reference_image_id": getattr(person, "face_reference_image_id", "") or "",
            "face_user_type": getattr(person, "face_user_type", None) if getattr(person, "face_user_type", None) is not None else "",
            "face_access_password": getattr(person, "face_access_password", "") or "",
            "face_pass_rule_id": getattr(person, "face_pass_rule_id", "") or "",
            "face_tts_name": getattr(person, "face_tts_name", "") or "",
            "face_effective_from": person.face_effective_from.isoformat() if getattr(person, "face_effective_from", None) else "",
            "face_max_pass_count": getattr(person, "face_max_pass_count", None) if getattr(person, "face_max_pass_count", None) is not None else "",
            "face_pass_count_cycle": getattr(person, "face_pass_count_cycle", None) if getattr(person, "face_pass_count_cycle", None) is not None else "",
            "photo_review_status": getattr(person, "photo_review_status", "not_started") or "not_started",
            "photo_review_status_display": person.get_photo_review_status_display() if getattr(person, "photo_review_status", "") else "",
            "photo_similarity_score": str(person.photo_similarity_score) if getattr(person, "photo_similarity_score", None) is not None else "",
            "photo_reviewed_at": person.photo_reviewed_at.isoformat() if getattr(person, "photo_reviewed_at", None) else "",
            "photo_review_error": getattr(person, "photo_review_error", "") or "",
        },
    }
    if unit is not None:
        payload["unit"] = {
            "id": str(unit.id),
            "unit_code": unit.unit_code,
            "permissions": unit.permissions,
        }
        from GateCore.residence_features import get_capabilities_for_resident_app
        payload["capabilities"] = get_capabilities_for_resident_app(unit.permissions)
    return payload
