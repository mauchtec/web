from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.urls import reverse

from GateCore.models import AccessLog, Person, Unit
from GateCore.services.mobile_auth import build_photo_display_url
from frontend.views import (
    _build_vehicle_entry,
    _apply_latest_entry,
    _extract_component_values,
    _extract_plate,
    _flatten_scan_payload,
    detect_scan_role,
    normalize_request_data,
    shared_extract_record,
)


DEFAULT_PAGE_SIZE = 5


def _get_page_number(request, default=1):
    raw_value = request.query_params.get("page", default)
    try:
        page = int(raw_value)
    except (TypeError, ValueError):
        return 1
    return max(page, 1)


def _get_page_size(request):
    raw_value = request.query_params.get("page_size", DEFAULT_PAGE_SIZE)
    try:
        page_size = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    return max(1, min(page_size, 100))


def _paginate_queryset(queryset, request):
    page = _get_page_number(request)
    page_size = _get_page_size(request)
    paginator = Paginator(queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return page_obj.object_list, {
        "page": page_obj.number,
        "page_size": page_size,
        "total_items": paginator.count,
        "total_pages": paginator.num_pages,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def people_overview(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    rows = []
    queryset = Person.objects.prefetch_related("occupancies__unit__property__site").order_by("last_name", "first_name")
    search = (request.query_params.get("q") or "").strip()
    min_residences = request.query_params.get("min_residences")

    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(middle_name__icontains=search)
            | Q(id_number__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
        )

    if min_residences:
        try:
            min_residences_value = int(min_residences)
        except (TypeError, ValueError):
            min_residences_value = 0
        if min_residences_value > 0:
            queryset = queryset.annotate(
                residence_count=Count(
                    "occupancies",
                    filter=Q(occupancies__is_active=True, occupancies__is_deleted=False),
                    distinct=True,
                )
            ).filter(residence_count__gte=min_residences_value)

    paginated = any([
        request.query_params.get("page"),
        request.query_params.get("page_size"),
        search,
        min_residences,
    ])
    if paginated:
        people, pagination = _paginate_queryset(queryset, request)
    else:
        people = queryset
        pagination = None

    for person in people:
        residences = []
        for occ in person.occupancies.all():
            unit = occ.unit
            if not unit or not getattr(unit, "property", None) or not getattr(unit.property, "site", None):
                continue
            residences.append(f"{unit.property.site.name} - {unit.property.name} - {unit.unit_code}")
        rows.append(
            {
                "id": str(person.id),
                "full_name": person.full_name,
                "first_name": person.first_name,
                "last_name": person.last_name,
                "middle_name": person.middle_name or "",
                "id_number": person.id_number or "",
                "phone": person.phone or "",
                "email": person.email or "",
                "gender": person.gender or "",
                "gender_display": person.get_gender_display() if person.gender else "",
                "date_of_birth": person.date_of_birth.isoformat() if person.date_of_birth else "",
                "access_expires_on": person.access_expires_on.isoformat() if person.access_expires_on else "",
                "emergency_contact_name": person.emergency_contact_name or "",
                "emergency_contact_phone": person.emergency_contact_phone or "",
                "notes": person.notes or "",
                "residences": " | ".join(residences),
                "photo_url": build_photo_display_url(person.photo),
                "photo_review_attempt_url": build_photo_display_url(person.photo_review_attempt),
                "tags": person.tags or [],
                "phone_device_type": person.phone_device_type or "",
                "phone_device_type_display": person.get_phone_device_type_display() if person.phone_device_type else "",
                "device_name": person.device_name or "",
                "device_model": person.device_model or "",
                "facial_recognition_enabled": bool(person.facial_recognition_enabled),
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
                "photo_review_status": person.photo_review_status or "not_started",
                "photo_review_status_display": person.get_photo_review_status_display() if person.photo_review_status else "",
                "photo_similarity_score": str(person.photo_similarity_score) if person.photo_similarity_score is not None else "",
                "photo_reviewed_at": person.photo_reviewed_at.isoformat() if person.photo_reviewed_at else "",
                "photo_review_error": person.photo_review_error or "",
                "last_seen": person.last_seen.isoformat() if person.last_seen else "",
                "unit_ids": [str(occ.unit_id) for occ in person.occupancies.filter(is_active=True, is_deleted=False) if occ.unit_id],
                "occupancy_count": person.occupancies.filter(is_active=True, is_deleted=False).count(),
                "vehicle_count": person.vehicles.count(),
                "credential_count": person.credentials.count(),
                "permission_count": person.permissions.count(),
                "access_log_count": person.access_logs.count(),
                "created_at": person.created_at.isoformat() if getattr(person, "created_at", None) else "",
                "modified_at": person.modified_at.isoformat() if getattr(person, "modified_at", None) else "",
                "detail_url": reverse("gatecore_person_detail", args=[person.id]),
            }
        )
    payload = {"people": rows, "rows": rows}
    if pagination:
        payload["pagination"] = pagination
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def units_overview(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    rows = []
    units = Unit.objects.select_related("property__site").annotate(
        resident_count=Count("occupancies", filter=Q(occupancies__is_active=True, occupancies__is_deleted=False), distinct=True),
    ).order_by("property__site__name", "property__name", "unit_code")
    for unit in units:
        property_obj = unit.property
        site = property_obj.site if property_obj else None
        rows.append(
            {
                "id": str(unit.id),
                "unit_code": unit.unit_code,
                "unit_type": unit.unit_type,
                "unit_type_display": unit.get_unit_type_display(),
                "property_id": str(property_obj.id) if property_obj else "",
                "property_name": property_obj.name if property_obj else "",
                "site_name": site.name if site else "",
                "floor": unit.floor if unit.floor is not None else "",
                "status": unit.status,
                "status_display": unit.get_status_display(),
                "area_sqft": str(unit.area_sqft) if unit.area_sqft is not None else "",
                "resident_count": getattr(unit, "resident_count", 0),
                "parking_spots": unit.parking_spots,
                "permissions": unit.permissions,
                "permissions_display": unit.get_permissions_display(),
                "access_code_present": bool(unit.access_code),
                "detail_url": reverse("gatecore_unit_detail", args=[unit.id]),
            }
        )
    return Response({"units": rows, "rows": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vehicles_overview(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    logs = AccessLog.objects.select_related("access_point").order_by("-timestamp")[:500]
    plate_map = {}
    for log in logs:
        raw_data = normalize_request_data(log.raw_scan_data)
        request_data = normalize_request_data(log.request_data)
        component_values = _extract_component_values(request_data)
        record_kind = detect_scan_role(request_data, raw_data, component_values)
        record_source = shared_extract_record(raw_data, record_kind)
        if not record_source:
            record_source = raw_data if isinstance(raw_data, dict) else {}
        if not record_source:
            record_source = shared_extract_record(request_data, record_kind)
        if not record_source:
            record_source = request_data if isinstance(request_data, dict) else {}
        if not record_source:
            continue
        plate = (
            record_source.get("plate_number")
            or record_source.get("vehicle_register_number")
            or component_values.get("vehicle_plate")
        )
        if not plate:
            plate = _extract_plate(record_source)
        if not plate:
            continue
        flat_raw = _flatten_scan_payload(record_source)
        combined_source = {**flat_raw}
        status_value = (
            record_source.get("expiry_status")
            or record_source.get("status")
            or combined_source.get("expiry_status")
            or combined_source.get("status")
        )
        if not status_value:
            days_remaining = record_source.get("days_remaining")
            if isinstance(days_remaining, (int, float)):
                status_value = "VALID" if days_remaining >= 0 else "EXPIRED"
            else:
                status_value = "UNKNOWN"
        new_entry = _build_vehicle_entry(
            log,
            plate,
            combined_source,
            status_value,
            raw_payload=record_source,
        )
        new_entry["record_type"] = "Trailer" if record_kind == "trailer" else "Vehicle"
        plate_key = f"{str(plate).strip().upper()}:{record_kind}"
        existing = plate_map.get(plate_key)
        if existing is None:
            plate_map[plate_key] = new_entry
        else:
            _apply_latest_entry(existing, new_entry)

    entries = sorted(plate_map.values(), key=lambda entry: entry.get("_timestamp"), reverse=True)
    for entry in entries:
        entry.pop("_timestamp", None)

    column_defs = [
        {"key": "plate_number", "label": "Plate Number", "visible": True, "type": "link"},
        {"key": "record_type", "label": "Type", "visible": True},
        {"key": "register_number", "label": "Register Number", "visible": True},
        {"key": "disk_number", "label": "Disk Number", "visible": True},
        {"key": "expiry_date", "label": "Expiry Date", "visible": True},
        {"key": "vehicle_type", "label": "Vehicle Type", "visible": True},
        {"key": "make", "label": "Make", "visible": True},
        {"key": "model", "label": "Model", "visible": True},
        {"key": "colour", "label": "Colour", "visible": True},
        {"key": "color_english", "label": "Color (English)", "visible": False},
        {"key": "color_afrikaans", "label": "Color (Afrikaans)", "visible": False},
        {"key": "vin", "label": "VIN", "visible": True},
        {"key": "engine_number", "label": "Engine Number", "visible": True},
        {"key": "body_type_en", "label": "Body Type (EN)", "visible": True},
        {"key": "body_type_af", "label": "Body Type (AF)", "visible": True},
        {"key": "document_type", "label": "Document Type", "visible": False},
        {"key": "days_remaining", "label": "Days Remaining", "visible": True},
        {"key": "status", "label": "Status", "visible": True, "type": "status"},
        {"key": "is_expired", "label": "Expired Flag", "visible": False, "type": "boolean"},
        {"key": "province", "label": "Province", "visible": True},
        {"key": "scan_type", "label": "Scan Type", "visible": False},
        {"key": "barcode_type", "label": "Barcode Type", "visible": False},
        {"key": "hex_length", "label": "Hex Length", "visible": False},
    ]
    return Response({"vehicle_logs": entries, "rows": entries, "column_defs": column_defs})
