from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from GateCore.models import AccessLog
from frontend.views import (
    _apply_latest_license_entry,
    _build_license_entry,
    _flatten_scan_payload,
    _merge_license_fields,
    _normalize_license_key,
    _parse_date_string,
    normalize_request_data,
)


def _require_staff(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def driver_licenses_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    license_filter = (
        Q(raw_scan_data__license__isnull=False)
        | Q(request_data__license__isnull=False)
        | Q(raw_scan_data__driver_license_id__isnull=False)
        | Q(request_data__driver_license_id__isnull=False)
        | Q(raw_scan_data__id_number__isnull=False)
        | Q(request_data__id_number__isnull=False)
        | Q(raw_scan_data__license_number__isnull=False)
        | Q(request_data__license_number__isnull=False)
        | Q(raw_scan_data__license__driver_license_id__isnull=False)
        | Q(request_data__license__driver_license_id__isnull=False)
        | Q(raw_scan_data__license__id_number__isnull=False)
        | Q(request_data__license__id_number__isnull=False)
        | Q(raw_scan_data__license__license_number__isnull=False)
        | Q(request_data__license__license_number__isnull=False)
        | Q(raw_scan_data__scan_type__iexact="license")
        | Q(request_data__scan_type__iexact="license")
        | Q(raw_scan_data__document_type__iexact="driving_license")
        | Q(request_data__document_type__iexact="driving_license")
    )
    logs = (
        AccessLog.objects
        .filter(license_filter)
        .order_by("-timestamp")[:500]
    )
    license_map = {}
    now_date = timezone.now().date()
    for log in logs:
        raw_data = normalize_request_data(log.raw_scan_data)
        request_data = normalize_request_data(log.request_data)
        flat_raw = _flatten_scan_payload(raw_data)
        flat_request = _flatten_scan_payload(request_data)
        combined = {**flat_request, **flat_raw}
        license_key = _normalize_license_key(combined)
        if not license_key:
            continue
        expiry_str = combined.get("license_expiry_date") or combined.get("expiry_date")
        expiry_date = _parse_date_string(expiry_str)
        if expiry_date:
            status_value = "VALID" if expiry_date >= now_date else "EXPIRED"
        else:
            status_value = "UNKNOWN"
        new_entry = _build_license_entry(
            log,
            combined,
            status_value,
            raw_payload=raw_data or request_data,
        )
        existing = license_map.get(license_key)
        if existing is None:
            license_map[license_key] = new_entry
        else:
            _merge_license_fields(existing, new_entry)
            _apply_latest_license_entry(existing, new_entry)

    entries = sorted(license_map.values(), key=lambda entry: entry.get("_timestamp"), reverse=True)
    for entry in entries:
        entry.pop("_timestamp", None)

    column_defs = [
        {"key": "id_number", "label": "ID Number", "visible": True, "type": "link"},
        {"key": "license_number", "label": "License Number", "visible": True},
        {"key": "driver_license_id", "label": "Driver License ID", "visible": True},
        {"key": "surname", "label": "Surname", "visible": True},
        {"key": "initials", "label": "Initials", "visible": True},
        {"key": "birthdate", "label": "Birthdate", "visible": True},
        {"key": "gender", "label": "Gender", "visible": True},
        {"key": "license_issue_date", "label": "License Issue Date", "visible": True},
        {"key": "license_expiry_date", "label": "License Expiry Date", "visible": True},
        {"key": "status", "label": "Status", "visible": True, "type": "status"},
        {"key": "vehicle_codes", "label": "Vehicle Codes", "visible": True},
        {"key": "vehicle_restrictions", "label": "Vehicle Restrictions", "visible": True},
        {"key": "license_code_issue_dates", "label": "License Code Issue Dates", "visible": True},
        {"key": "driver_restriction_codes", "label": "Driver Restriction Codes", "visible": True},
        {"key": "prdp_code", "label": "PRDP Code", "visible": True},
        {"key": "prdp_expiry_date", "label": "PRDP Expiry Date", "visible": True},
        {"key": "id_country_of_issue", "label": "ID Country", "visible": True},
        {"key": "license_country_of_issue", "label": "License Country", "visible": False},
        {"key": "license_issue_number", "label": "License Issue #", "visible": False},
        {"key": "id_number_type", "label": "ID Number Type", "visible": False},
        {"key": "scan_type", "label": "Scan Type", "visible": False},
        {"key": "barcode_type", "label": "Barcode Type", "visible": False},
        {"key": "hex_length", "label": "Hex Length", "visible": False},
        {"key": "timestamp", "label": "Logged At", "visible": True},
        {"key": "document_type", "label": "Document Type", "visible": False},
    ]
    return Response({"rows": entries, "column_defs": column_defs})
