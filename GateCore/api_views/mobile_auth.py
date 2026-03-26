from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from GateCore.models.occupancy import Occupancy
from GateCore.models.people import Person
from GateCore.services.mobile_auth import (
    build_token_response,
    ensure_mobile_user,
    generate_otp,
    is_otp_valid,
    normalize_phone,
    phone_numbers_equal,
    send_sms,
)


def _active_occupancies(person: Person):
    return (
        person.occupancies.filter(is_active=True, is_deleted=False)
        .select_related("unit__property__site")
    )


class MobileOtpRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        raw_phone = request.data.get("phone")
        normalized_phone = normalize_phone(raw_phone)
        if not normalized_phone:
            return Response({"detail": "Valid phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        persons = [
            person
            for person in Person.objects.filter(is_active=True, is_deleted=False)
            if phone_numbers_equal(person.phone, normalized_phone)
        ]
        if not persons:
            return Response({"memberships": [], "otp_sent": False})

        otp_code = generate_otp()
        now = timezone.now()
        # Bulk update OTP fields so we don't trigger Person.save()/full_clean() (some Person rows may have blank last_name etc.)
        person_ids = [p.id for p in persons]
        Person.objects.filter(id__in=person_ids).update(phone_otp=otp_code, phone_otp_created=now)
        memberships = []
        for person in persons:
            for occupancy in _active_occupancies(person):
                unit = occupancy.unit
                property_ = unit.property if unit else None
                site = property_.site if property_ else None
                if not (unit and property_ and site):
                    continue
                memberships.append(
                    {
                        "membership_id": str(occupancy.id),
                        "person_id": str(person.id),
                        "site_id": str(site.id),
                        "site_name": site.name,
                        "property_id": str(property_.id),
                        "property_name": property_.name,
                        "unit_id": str(unit.id),
                        "unit_code": unit.unit_code,
                        "role": occupancy.role,
                    }
                )

        expires_in = getattr(settings, "PHONE_OTP_EXPIRATION_MINUTES", 5) * 60
        message = (
            f"Your AccessControll login code is {otp_code}. "
            f"It will expire in {int(expires_in / 60)} minutes."
        )
        primary_person = persons[0] if len(persons) == 1 else None
        primary_unit = None
        if len(memberships) == 1:
            occupancy = (
                Occupancy.objects.select_related("unit")
                .filter(id=memberships[0]["membership_id"])
                .first()
            )
            if occupancy:
                primary_unit = occupancy.unit
        send_sms(
            normalized_phone,
            message,
            context={
                "trigger": "mobile_login_otp",
                "person": primary_person,
                "unit": primary_unit,
                "recipient_name": primary_person.full_name if primary_person else "",
                "visitor_name": primary_person.full_name if primary_person else "",
                "visitor_phone": normalized_phone,
                "context_data": {
                    "person_ids": [str(p.id) for p in persons],
                    "membership_ids": [m["membership_id"] for m in memberships],
                    "site_ids": [m["site_id"] for m in memberships],
                },
            },
        )
        expose_otp = getattr(settings, "EXPOSE_PHONE_OTP", settings.DEBUG)
        response_data = {
            "phone": normalized_phone,
            "otp_sent": True,
            "expires_in": expires_in,
            "memberships": memberships,
        }
        if expose_otp:
            response_data["otp"] = otp_code
        return Response(response_data)


class MobileOtpVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        membership_id = request.data.get("membership_id")
        otp = request.data.get("otp")
        phone = request.data.get("phone")

        if not membership_id or not otp or not phone:
            return Response(
                {"detail": "phone, otp, and membership_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            occupancy = Occupancy.objects.select_related("person", "unit__property__site").get(
                id=membership_id, is_active=True, is_deleted=False
            )
        except Occupancy.DoesNotExist:
            return Response({"detail": "Invalid membership selection."}, status=status.HTTP_404_NOT_FOUND)

        person = occupancy.person
        if person.access_expires_on and timezone.now().date() > person.access_expires_on:
            return Response({"detail": "This resident access has expired."}, status=status.HTTP_403_FORBIDDEN)
        if not (phone_numbers_equal(person.phone, phone) and person.phone_otp == otp and is_otp_valid(person)):
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_401_UNAUTHORIZED)

        unit = occupancy.unit
        property_ = unit.property if unit else None
        site = property_.site if property_ else None
        if not (unit and property_ and site):
            return Response({"detail": "Membership is not linked to a site."}, status=status.HTTP_400_BAD_REQUEST)

        user = ensure_mobile_user(person)
        now_seen = timezone.now()
        person.phone_otp = ""
        person.phone_otp_created = None
        person.last_seen = now_seen
        person.device_identifier = request.data.get("device_id") or person.device_identifier
        person.device_name = request.data.get("device_name") or person.device_name
        person.device_model = request.data.get("device_model") or person.device_model
        person.device_serial_number = request.data.get("device_serial") or person.device_serial_number
        person.device_os = request.data.get("device_os") or person.device_os
        person.device_app_version = request.data.get("device_app_version") or person.device_app_version
        device_info = dict(person.device_info or {})
        incoming_device_info = request.data.get("device_info")
        if isinstance(incoming_device_info, dict):
            device_info.update(incoming_device_info)
        manufacturer = request.data.get("device_manufacturer")
        if manufacturer:
            device_info["manufacturer"] = manufacturer
        sdk_int = request.data.get("device_sdk")
        if sdk_int is not None:
            device_info["sdk_int"] = sdk_int
        latitude = request.data.get("latitude")
        if latitude is not None:
            device_info["latitude"] = latitude
        longitude = request.data.get("longitude")
        if longitude is not None:
            device_info["longitude"] = longitude
        # Use queryset update to avoid Person.save()/full_clean() when Person has blank last_name etc.
        Person.objects.filter(pk=person.pk).update(
            phone_otp="",
            phone_otp_created=None,
            last_seen=now_seen,
            device_identifier=person.device_identifier,
            device_name=person.device_name,
            device_model=person.device_model,
            device_serial_number=person.device_serial_number,
            device_os=person.device_os,
            device_app_version=person.device_app_version,
            device_info=device_info,
        )
        return Response(build_token_response(user, person, site, unit=unit, request=request))
