import json

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from GateCore.models import AccessLog
from frontend.views import (
    _build_driver_details,
    _build_entry_summary,
    _build_exit_summary,
    _build_trailer_details,
    _build_vehicle_details,
    _extract_component_values,
    _extract_direction_value,
    _extract_components,
    _find_exit_log_with_pin,
    _normalize_request_data,
    detect_scan_role,
    shared_extract_record,
)


def _require_staff(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    return None


def _serialize_components(request_data):
    components = []
    component_keys = set()
    if isinstance(request_data, dict):
        for comp in request_data.get("components") or []:
            if not isinstance(comp, dict):
                continue
            comp_id = str(comp.get("id") or "").strip()
            if comp_id:
                component_keys.add(comp_id)
            fields = comp.get("fields") or []
            value = comp.get("value")
            if not value and fields:
                value = ", ".join(str(field.get("value") or "").strip() for field in fields if isinstance(field, dict) and field.get("value"))
            components.append({
                "id": comp_id,
                "type": str(comp.get("type") or ""),
                "label": str(comp.get("label") or comp.get("title") or comp_id),
                "value": value or "",
            })
    return components, sorted(component_keys)


def _build_access_log_row(log):
    request_data = _normalize_request_data(log.request_data or {})
    raw_data = _normalize_request_data(log.raw_scan_data or {})
    component_values = _extract_component_values(request_data)
    components, component_keys = _serialize_components(request_data)
    scan_role = str(request_data.get("scan_role") or raw_data.get("scan_role") or "").strip().lower()
    driver_details = _build_driver_details(request_data, raw_data, component_values)
    vehicle_details = {} if scan_role == "trailer" else _build_vehicle_details(request_data, raw_data, component_values)
    trailer_details = _build_trailer_details(request_data, raw_data, component_values)
    combined = shared_extract_record({**raw_data, **request_data}, "license")
    pin_code = component_values.get("pin_code") or request_data.get("pin_code") or raw_data.get("pin_code") or ""
    exit_log = _find_exit_log_with_pin(pin_code, log)
    entry_summary = _build_entry_summary(log, request_data, pin_code)
    exit_summary = _build_exit_summary(exit_log) if exit_log else None
    return {
        "id": str(log.id),
        "timestamp": log.timestamp.isoformat(),
        "timestamp_display": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "access_point": {
            "id": str(log.access_point.id) if log.access_point else "",
            "name": log.access_point.name if log.access_point else "",
        },
        "person": {
            "id": str(log.person.id) if log.person else "",
            "full_name": log.person.full_name if log.person else "",
        },
        "credential": {
            "id": str(log.credential.id) if log.credential else "",
            "value": log.credential.credential_value if log.credential else "",
        },
        "result": log.result,
        "result_display": log.get_result_display(),
        "reason": log.reason or "",
        "credential_value_used": log.credential_value_used or "",
        "latitude": str(log.latitude) if log.latitude is not None else "",
        "longitude": str(log.longitude) if log.longitude is not None else "",
        "session_id": log.session_id or "",
        "detail_url": reverse("gatecore_access_log_detail", args=[log.id]),
        "report_url": reverse("gatecore_access_log_report", args=[log.id]),
        "pdf_url": reverse("gatecore_access_log_pdf", args=[log.id]),
        "components": {item["id"]: item["value"] for item in components},
        "component_items": components,
        "component_keys": component_keys,
        "request_data": request_data,
        "raw_data": raw_data,
        "driver_details": driver_details,
        "vehicle_details": vehicle_details,
        "trailer_details": trailer_details,
        "license_details": combined,
        "component_values": component_values,
        "entry_summary": entry_summary,
        "exit_summary": exit_summary,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def access_logs_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    logs = AccessLog.objects.select_related("access_point", "person", "credential").order_by("-timestamp")[:200]
    rows = []
    component_keys = set()
    for log in logs:
        row = _build_access_log_row(log)
        rows.append(row)
        component_keys.update(row["component_keys"])
    return Response({"logs": rows, "rows": rows, "component_keys": sorted(component_keys)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def access_log_detail(request, log_id):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    log = get_object_or_404(AccessLog.objects.select_related("access_point", "person", "credential"), id=log_id)
    return Response(_build_access_log_row(log))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def report_list_overview(request):
    forbidden = _require_staff(request)
    if forbidden:
        return forbidden

    logs = AccessLog.objects.select_related("access_point", "person", "credential").order_by("-timestamp")[:500]
    rows = []
    for log in logs:
        row = _build_access_log_row(log)
        rows.append({
            "id": row["id"],
            "timestamp": row["timestamp_display"],
            "workflow_name": row["request_data"].get("workflow_name") or "",
            "direction": _extract_direction_value(row["request_data"], row["raw_data"], row["component_values"]) or row["request_data"].get("direction") or "",
            "access_point": row["access_point"]["name"],
            "result": row["result_display"],
            "pin_code": row["component_values"].get("pin_code") or "",
            "pin_source": row["request_data"].get("pin_source") or "",
            "recording_url": row["request_data"].get("recording_url") or "",
            "id_number": row["driver_details"].get("id_number") or "",
            "gender": row["driver_details"].get("gender") or "",
            "full_name": row["driver_details"].get("full_name") or "",
            "visitor_phone_number": row["component_values"].get("phone_number") or "",
            "destination_residence": row["driver_details"].get("residence_type") or "",
            "vehicle_plate": row["vehicle_details"].get("plate_number") or "",
            "trailer": row["trailer_details"].get("plate_number") or "",
            "vehicle_make_model": row["vehicle_details"].get("make_model") or "",
            "vehicle_color": row["vehicle_details"].get("color") or "",
            "company_selection": row["driver_details"].get("company_selection") or "",
            "workflow_id": row["request_data"].get("workflow_id") or "",
            "workflow_version": row["request_data"].get("workflow_version") or "",
            "scan_type": row["request_data"].get("scan_type") or "",
            "person_name": row["person"]["full_name"],
            "credential": row["credential"]["value"],
            "log_url": row["detail_url"],
        })
    column_defs = [
        {"key": "timestamp", "label": "Timestamp", "visible": True, "type": "link"},
        {"key": "workflow_name", "label": "Workflow", "visible": True},
        {"key": "direction", "label": "Direction", "visible": True},
        {"key": "access_point", "label": "Access Point", "visible": True},
        {"key": "result", "label": "Result", "visible": True, "type": "status"},
        {"key": "pin_code", "label": "PIN", "visible": True},
        {"key": "pin_source", "label": "PIN source", "visible": True},
        {"key": "recording_url", "label": "Recording", "visible": True, "type": "external_link"},
        {"key": "id_number", "label": "ID Number", "visible": True},
        {"key": "gender", "label": "Gender", "visible": True},
        {"key": "full_name", "label": "Full Name", "visible": True},
        {"key": "visitor_phone_number", "label": "Phone Number", "visible": True},
        {"key": "destination_residence", "label": "Residence", "visible": True},
        {"key": "vehicle_plate", "label": "Vehicle Plate", "visible": True},
        {"key": "trailer", "label": "Trailer", "visible": True, "type": "link"},
        {"key": "vehicle_make_model", "label": "Vehicle Make / Model", "visible": True},
        {"key": "vehicle_color", "label": "Vehicle Color", "visible": True},
        {"key": "company_selection", "label": "Company Selection", "visible": True},
        {"key": "workflow_id", "label": "Workflow ID", "visible": False},
        {"key": "workflow_version", "label": "Workflow Version", "visible": False},
        {"key": "scan_type", "label": "Scan Type", "visible": False},
        {"key": "person_name", "label": "Person", "visible": False},
        {"key": "credential", "label": "Credential", "visible": False},
    ]
    return Response({"rows": rows, "logs": rows, "column_defs": column_defs})
