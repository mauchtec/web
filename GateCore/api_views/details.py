from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from GateCore.models import AccessLog, Person, Site, Unit, Vehicle, VisitorFaceAccessGrant
from GateCore.services.mobile_auth import build_photo_display_url
from frontend.views import _build_vehicle_log_rows

DETAIL_PAGE_SIZE = 5


def _require_staff(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    return None


def _get_page_number(request, param_name):
    raw_value = request.query_params.get(param_name, "1")
    try:
        page = int(raw_value)
    except (TypeError, ValueError):
        return 1
    return max(page, 1)


def _paginate_queryset(queryset, page):
    total_items = queryset.count()
    total_pages = max(1, (total_items + DETAIL_PAGE_SIZE - 1) // DETAIL_PAGE_SIZE)
    page = min(max(page, 1), total_pages)
    start = (page - 1) * DETAIL_PAGE_SIZE
    items = list(queryset[start:start + DETAIL_PAGE_SIZE])
    return items, {
        "page": page,
        "page_size": DETAIL_PAGE_SIZE,
        "total_items": total_items,
        "total_pages": total_pages,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def person_detail(request, person_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    person = get_object_or_404(Person.objects.select_related("user"), id=person_id)
    occupancies = person.occupancies.select_related("unit__property__site").all()
    vehicles = person.vehicles.all()
    credentials = person.credentials.all()
    permissions = person.permissions.select_related("access_point", "schedule_rule").all()
    access_logs = person.access_logs.select_related("access_point", "device", "credential").order_by("-timestamp")
    guest_registrations = person.guest_registrations.select_related("unit", "host").all()
    hosted_guests = person.hosted_guests.select_related("unit", "guest").all()
    blacklist_entries = person.blacklist_entries.all()
    audit_trails = person.audit_trails.select_related("performed_by", "unit").all()
    visitor_face_grant = (
        VisitorFaceAccessGrant.objects.select_related("guest_registration", "entry_terminal", "exit_terminal")
        .filter(person=person)
        .order_by("-created_at")
        .first()
    )

    occupancies_page, occupancies_pagination = _paginate_queryset(occupancies, _get_page_number(request, "occupancies_page"))
    vehicles_page, vehicles_pagination = _paginate_queryset(vehicles, _get_page_number(request, "vehicles_page"))
    credentials_page, credentials_pagination = _paginate_queryset(credentials, _get_page_number(request, "credentials_page"))
    permissions_page, permissions_pagination = _paginate_queryset(permissions, _get_page_number(request, "permissions_page"))
    access_logs_page, access_logs_pagination = _paginate_queryset(access_logs, _get_page_number(request, "access_logs_page"))
    guest_registrations_page, guest_registrations_pagination = _paginate_queryset(guest_registrations, _get_page_number(request, "guest_registrations_page"))
    hosted_guests_page, hosted_guests_pagination = _paginate_queryset(hosted_guests, _get_page_number(request, "hosted_guests_page"))
    blacklist_entries_page, blacklist_entries_pagination = _paginate_queryset(blacklist_entries, _get_page_number(request, "blacklist_entries_page"))
    audit_trails_page, audit_trails_pagination = _paginate_queryset(audit_trails, _get_page_number(request, "audit_trails_page"))

    return Response({
        "person": {
            "id": str(person.id),
            "full_name": person.full_name,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "middle_name": person.middle_name or "",
            "gender": person.gender or "",
            "gender_display": person.get_gender_display() if person.gender else "",
            "id_number": person.id_number or "",
            "card_number": person.card_number or "",
            "phone": person.phone or "",
            "email": person.email or "",
            "photo_url": build_photo_display_url(person.photo),
            "photo_review_attempt_url": build_photo_display_url(person.photo_review_attempt),
            "face_provider": person.face_provider or "",
            "face_subject_id": person.face_subject_id or "",
            "face_enrollment_status": person.face_enrollment_status or "not_started",
            "face_enrollment_status_display": person.get_face_enrollment_status_display() if person.face_enrollment_status else "",
            "face_enrollment_quality_score": str(person.face_enrollment_quality_score) if person.face_enrollment_quality_score is not None else "",
            "photo_quality_score": str(person.face_enrollment_quality_score) if person.face_enrollment_quality_score is not None else "",
            "face_enrolled_at": person.face_enrolled_at.isoformat() if person.face_enrolled_at else "",
            "face_last_synced_at": person.face_last_synced_at.isoformat() if person.face_last_synced_at else "",
            "face_enrollment_error": person.face_enrollment_error or "",
            "face_reference_image_id": person.face_reference_image_id or "",
            "face_user_type": person.face_user_type if person.face_user_type is not None else "",
            "face_access_password": person.face_access_password or "",
            "face_pass_rule_id": person.face_pass_rule_id or "",
            "face_tts_name": person.face_tts_name or "",
            "face_effective_from": person.face_effective_from.isoformat() if person.face_effective_from else "",
            "face_effective_from_display": person.face_effective_from.strftime("%Y-%m-%d %H:%M") if person.face_effective_from else "",
            "face_valid_until": visitor_face_grant.valid_until.isoformat() if visitor_face_grant and visitor_face_grant.valid_until else "",
            "face_valid_until_display": visitor_face_grant.valid_until.strftime("%Y-%m-%d %H:%M") if visitor_face_grant and visitor_face_grant.valid_until else "",
            "face_max_pass_count": person.face_max_pass_count if person.face_max_pass_count is not None else "",
            "face_pass_count_cycle": person.face_pass_count_cycle if person.face_pass_count_cycle is not None else "",
            "photo_review_status": person.photo_review_status or "not_started",
            "photo_review_status_display": person.get_photo_review_status_display() if person.photo_review_status else "",
            "photo_similarity_score": str(person.photo_similarity_score) if person.photo_similarity_score is not None else "",
            "photo_reviewed_at": person.photo_reviewed_at.isoformat() if person.photo_reviewed_at else "",
            "photo_review_error": person.photo_review_error or "",
            "date_of_birth": person.date_of_birth.isoformat() if person.date_of_birth else "",
            "access_expires_on": person.access_expires_on.isoformat() if person.access_expires_on else "",
            "emergency_contact_name": person.emergency_contact_name or "",
            "emergency_contact_phone": person.emergency_contact_phone or "",
            "notes": person.notes or "",
            "tags": person.tags or [],
        },
        "occupancies": [
            {
                "id": str(occ.id),
                "role": occ.role,
                "role_display": occ.get_role_display(),
                "start_date": occ.start_date.isoformat() if occ.start_date else "",
                "end_date": occ.end_date.isoformat() if occ.end_date else "",
                "unit_code": occ.unit.unit_code if occ.unit else "",
                "property_name": occ.unit.property.name if occ.unit and occ.unit.property else "",
                "site_name": occ.unit.property.site.name if occ.unit and occ.unit.property and occ.unit.property.site else "",
                "detail_url": reverse("gatecore_unit_detail", args=[occ.unit.id]) if occ.unit else "",
            }
            for occ in occupancies_page
        ],
        "occupancies_pagination": occupancies_pagination,
        "vehicles": [
            {
                "id": str(vehicle.id),
                "license_plate": vehicle.license_plate,
                "vehicle_type": vehicle.vehicle_type,
                "vehicle_type_display": vehicle.get_vehicle_type_display(),
                "make": vehicle.make or "",
                "model": vehicle.model or "",
                "color": vehicle.color or "",
                "year": vehicle.year if vehicle.year is not None else "",
                "fuel_type": vehicle.fuel_type or "",
                "fuel_type_display": vehicle.get_fuel_type_display() if vehicle.fuel_type else "",
                "registration_number": vehicle.registration_number or "",
                "detail_url": reverse("gatecore_vehicle_detail", args=[vehicle.id]),
            }
            for vehicle in vehicles_page
        ],
        "vehicles_pagination": vehicles_pagination,
        "credentials": [
            {
                "id": str(cred.id),
                "credential_type": cred.credential_type,
                "credential_type_display": cred.get_credential_type_display(),
                "credential_value": cred.credential_value,
                "expires_at": cred.expires_at.isoformat() if cred.expires_at else "",
                "is_temporary": bool(cred.is_temporary),
            }
            for cred in credentials_page
        ],
        "credentials_pagination": credentials_pagination,
        "permissions": [
            {
                "id": str(perm.id),
                "access_point_name": perm.access_point.name if perm.access_point else "",
                "schedule_rule_name": perm.schedule_rule.name if perm.schedule_rule else "Anytime",
                "valid_from": perm.valid_from.isoformat() if perm.valid_from else "",
                "valid_until": perm.valid_until.isoformat() if perm.valid_until else "",
            }
            for perm in permissions_page
        ],
        "permissions_pagination": permissions_pagination,
        "access_logs": [
            {
                "id": str(log.id),
                "timestamp": log.timestamp.isoformat(),
                "timestamp_display": log.timestamp.strftime("%Y-%m-%d %H:%M"),
                "access_point_name": log.access_point.name if log.access_point else "",
                "result": log.result,
                "result_display": log.get_result_display(),
                "detail_url": reverse("gatecore_access_log_detail", args=[log.id]),
            }
            for log in access_logs_page
        ],
        "access_logs_pagination": access_logs_pagination,
        "guest_registrations": [
            {
                "id": str(guest.id),
                "unit_code": guest.unit.unit_code if guest.unit else "",
                "host_name": guest.host.full_name if guest.host else "",
                "status": guest.status,
                "status_display": guest.get_status_display(),
                "face_enrollment_status": guest.guest.face_enrollment_status if guest.guest else "not_started",
                "face_enrollment_status_display": guest.guest.get_face_enrollment_status_display() if guest.guest and guest.guest.face_enrollment_status else "",
            }
            for guest in guest_registrations_page
        ],
        "guest_registrations_pagination": guest_registrations_pagination,
        "hosted_guests": [
            {
                "id": str(guest.id),
                "unit_code": guest.unit.unit_code if guest.unit else "",
                "guest_name": guest.guest.full_name if guest.guest else "",
                "status": guest.status,
                "status_display": guest.get_status_display(),
            }
            for guest in hosted_guests_page
        ],
        "hosted_guests_pagination": hosted_guests_pagination,
        "blacklist_entries": [
            {
                "id": str(entry.id),
                "reason": entry.reason,
                "reason_display": entry.get_reason_display(),
                "details": entry.details or "",
                "blacklisted_from": entry.blacklisted_from.isoformat() if entry.blacklisted_from else "",
                "blacklisted_until": entry.blacklisted_until.isoformat() if entry.blacklisted_until else "",
            }
            for entry in blacklist_entries_page
        ],
        "blacklist_entries_pagination": blacklist_entries_pagination,
        "audit_trails": [
            {
                "id": str(audit.id),
                "timestamp": audit.timestamp.isoformat(),
                "timestamp_display": audit.timestamp.strftime("%Y-%m-%d %H:%M"),
                "action": audit.action,
                "action_display": audit.get_action_display(),
                "unit_code": audit.unit.unit_code if audit.unit else "",
                "performed_by": audit.performed_by.username if audit.performed_by else "System",
                "details": audit.details or "",
            }
            for audit in audit_trails_page
        ],
        "audit_trails_pagination": audit_trails_pagination,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def site_detail(request, site_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    site = get_object_or_404(Site, id=site_id)
    properties = site.properties.order_by("name")
    return Response({
        "site": {
            "id": str(site.id),
            "name": site.name,
            "site_type": site.site_type,
            "site_type_display": site.get_site_type_display(),
            "location": site.location or "",
            "address": site.address or "",
            "description": site.description or "",
            "code": site.code or "",
        },
        "properties": [
            {
                "id": str(prop.id),
                "name": prop.name,
                "property_code": prop.property_code or "",
                "property_type": prop.property_type,
                "property_type_display": prop.get_property_type_display(),
                "address": prop.address or "",
                "location": prop.location or "",
                "total_units": prop.total_units,
                "total_floors": prop.total_floors,
            }
            for prop in properties
        ],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unit_detail(request, unit_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    unit = get_object_or_404(Unit.objects.select_related("property__site"), id=unit_id)
    occupancies = unit.occupancies.select_related("person").all()
    occupancies_page, occupancies_pagination = _paginate_queryset(occupancies, _get_page_number(request, "occupancies_page"))
    return Response({
        "unit": {
            "id": str(unit.id),
            "unit_code": unit.unit_code,
            "unit_type": unit.unit_type,
            "unit_type_display": unit.get_unit_type_display(),
            "floor": unit.floor if unit.floor is not None else "",
            "status": unit.status,
            "status_display": unit.get_status_display(),
            "area_sqft": str(unit.area_sqft) if unit.area_sqft is not None else "",
            "bedrooms": unit.bedrooms,
            "bathrooms": unit.bathrooms,
            "has_parking": bool(unit.has_parking),
            "property_name": unit.property.name if unit.property else "",
            "site_name": unit.property.site.name if unit.property and unit.property.site else "",
            "permissions": unit.permissions,
            "permissions_display": unit.get_permissions_display(),
        },
        "occupancies": [
            {
                "id": str(occ.id),
                "person_name": occ.person.full_name if occ.person else "",
                "role": occ.role,
                "role_display": occ.get_role_display(),
                "start_date": occ.start_date.isoformat() if occ.start_date else "",
                "end_date": occ.end_date.isoformat() if occ.end_date else "",
            }
            for occ in occupancies_page
        ],
        "occupancies_pagination": occupancies_pagination,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vehicle_detail(request, vehicle_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    vehicle = Vehicle.objects.select_related("person").get(id=vehicle_id)
    plate_candidates = {
        value.strip()
        for value in {vehicle.license_plate or "", vehicle.registration_number or ""}
        if value and value.strip()
    }
    log_filter = None
    for plate in plate_candidates:
        clause = (
            Q(person=vehicle.person)
            | Q(raw_scan_data__plate_number__iexact=plate)
            | Q(raw_scan_data__vehicle_register_number__iexact=plate)
        )
        log_filter = clause if log_filter is None else log_filter | clause

    access_logs = []
    if log_filter is not None:
        logs = AccessLog.objects.filter(log_filter).select_related("access_point").order_by("-timestamp")[:20]
        for log in logs:
            for row in _build_vehicle_log_rows(log):
                access_point = row.get("access_point")
                access_logs.append(
                    {
                        "log_id": row.get("log_id"),
                        "log_url": row.get("log_url"),
                        "timestamp": row.get("timestamp").isoformat() if row.get("timestamp") else "",
                        "timestamp_display": row.get("timestamp").strftime("%Y-%m-%d %H:%M:%S") if row.get("timestamp") else "",
                        "access_point": {
                            "id": str(access_point.id) if access_point else "",
                            "name": access_point.name if access_point else "",
                        },
                        "result": row.get("result") or "",
                        "plate_number": row.get("plate_number") or "",
                        "trailer_plate_number": row.get("trailer_plate_number") or "",
                        "make_model": row.get("make_model") or "",
                        "color": row.get("color") or "",
                        "expiry_date": row.get("expiry_date") or "",
                        "document_type": row.get("document_type") or "",
                        "raw_scan_data_clean": row.get("raw_scan_data_clean") or {},
                    }
                )

    return Response({
        "vehicle": {
            "id": str(vehicle.id),
            "license_plate": vehicle.license_plate,
            "vehicle_type": vehicle.vehicle_type,
            "vehicle_type_display": vehicle.get_vehicle_type_display(),
            "make": vehicle.make or "",
            "model": vehicle.model or "",
            "color": vehicle.color or "",
            "year": vehicle.year if vehicle.year is not None else "",
            "fuel_type": vehicle.fuel_type or "",
            "fuel_type_display": vehicle.get_fuel_type_display() if vehicle.fuel_type else "",
            "registration_number": vehicle.registration_number or "",
            "registration_expiry": vehicle.registration_expiry.isoformat() if vehicle.registration_expiry else "",
            "has_sticker": bool(vehicle.has_sticker),
            "sticker_number": vehicle.sticker_number or "",
            "person_id": str(vehicle.person.id) if vehicle.person else "",
            "person_name": vehicle.person.full_name if vehicle.person else "",
            "person_detail_url": reverse("gatecore_person_detail", args=[vehicle.person.id]) if vehicle.person else "",
        },
        "access_logs": access_logs,
    })
