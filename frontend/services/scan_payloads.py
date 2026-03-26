import json


DEFAULT_MERGE_KEYS = (
    "direction",
    "workflow_name",
    "workflow_id",
    "screen_id",
    "scan_type",
    "document_type",
    "vehicle_kind",
    "plate_number",
    "license_plate",
    "vehicle_register_number",
    "number_plate",
    "id_number",
    "license_number",
    "driver_license_id",
    "anti_passback_enabled",
    "antipassback_enabled",
    "anti_passback_window_hours",
    "anti_passback_override",
    "antipassback_override",
    "anti_passback_override_comment",
    "override_comment",
    "session_id",
    "pin_source",
    "voip_call_id",
)


def _coerce_dict(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if isinstance(value, dict):
        return value
    return {}


def normalize_request_data(payload, merge_root=True):
    if not isinstance(payload, dict):
        return _coerce_dict(payload)

    if "request_data" not in payload and "raw_scan_data" not in payload:
        return dict(payload)

    request_data = _coerce_dict(payload.get("request_data"))
    if not merge_root:
        return request_data

    merged = dict(request_data)
    for key in DEFAULT_MERGE_KEYS:
        if key not in merged and payload.get(key) is not None:
            merged[key] = payload.get(key)
    return merged


def extract_components(request_data):
    if not isinstance(request_data, dict):
        return []
    components = request_data.get("components")
    if isinstance(components, list):
        return [comp for comp in components if isinstance(comp, dict)]
    return []


def flatten_scan_payload(payload):
    data = normalize_request_data(payload)
    if not isinstance(data, dict):
        return {}

    def recurse(current):
        flat = {}
        for key, value in current.items():
            if isinstance(value, dict):
                flat.update(recurse(value))
            elif isinstance(value, list):
                flat[key] = value
            else:
                flat[key] = value
        return flat

    return recurse(data)


def extract_record(data, key):
    if not isinstance(data, dict):
        return {}
    value = data.get(key)
    if isinstance(value, dict):
        return value
    return {}


def _component_text(component):
    if not isinstance(component, dict):
        return ""
    parts = [
        component.get("type"),
        component.get("id"),
        component.get("label"),
        component.get("title"),
        component.get("vehicle_kind"),
    ]
    return " ".join(str(part or "").lower() for part in parts)


def _matches_component(component, types=None, labels=None, ids=None):
    if not isinstance(component, dict):
        return False
    text = _component_text(component)
    type_name = str(component.get("type") or "").strip().lower()
    comp_id = str(component.get("id") or "").strip().lower()
    label = str(component.get("label") or component.get("title") or "").strip().lower()

    if types:
        allowed_types = {str(item).strip().lower() for item in types if item}
        if type_name not in allowed_types:
            return False

    if ids:
        id_terms = [str(item).strip().lower() for item in ids if item]
        if id_terms and not any(term in comp_id or term in text for term in id_terms):
            return False

    if labels:
        label_terms = [str(item).strip().lower() for item in labels if item]
        if label_terms and not any(term in label or term in text for term in label_terms):
            return False

    return True


def _first_component_value(component, value_keys=None):
    if not isinstance(component, dict):
        return ""
    value_keys = value_keys or ("value",)
    for key in value_keys:
        value = component.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def extract_component_value(
    request_data,
    *,
    types=None,
    labels=None,
    ids=None,
    value_keys=None,
    field_labels=None,
):
    components = extract_components(request_data)
    field_labels = [str(item).strip().lower() for item in (field_labels or []) if item]
    for component in components:
        if not _matches_component(component, types=types, labels=labels, ids=ids):
            continue
        value = _first_component_value(component, value_keys=value_keys or ("value", "direction"))
        if value:
            return value
        fields = component.get("fields")
        if field_labels and isinstance(fields, list):
            for field in fields:
                if not isinstance(field, dict):
                    continue
                field_label = str(field.get("label") or field.get("name") or "").strip().lower()
                if any(term in field_label for term in field_labels):
                    field_value = field.get("value")
                    if field_value not in (None, ""):
                        return str(field_value).strip()
    return ""


def extract_component_direction(request_data):
    return extract_component_value(
        request_data,
        types=("direction_field",),
        labels=("direction",),
        ids=("direction",),
        value_keys=("direction", "value"),
    )


def _component_field_map(component):
    fields = component.get("fields")
    if not isinstance(fields, list):
        return {}
    mapping = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        label = str(field.get("label") or field.get("name") or "").strip().lower()
        value = field.get("value")
        if label and value not in (None, ""):
            mapping[label] = str(value).strip()
    return mapping


def extract_component_attributes(
    request_data,
    *,
    types=None,
    labels=None,
    ids=None,
):
    components = extract_components(request_data)
    for component in components:
        if not _matches_component(component, types=types, labels=labels, ids=ids):
            continue
        attrs = {}
        for key, value in component.items():
            if key == "fields":
                continue
            if value not in (None, ""):
                attrs[key] = value
        attrs.update(_component_field_map(component))
        return attrs
    return {}


def extract_vehicle_component_details(request_data):
    attrs = extract_component_attributes(
        request_data,
        types=("vehicle_disk",),
        labels=("vehicle",),
        ids=("vehicle",),
    )
    if attrs:
        return attrs
    attrs = extract_component_attributes(
        request_data,
        types=("card_with_image",),
        labels=("vehicle",),
        ids=("vehicle",),
    )
    return attrs


def extract_trailer_component_details(request_data):
    attrs = extract_component_attributes(
        request_data,
        types=("trailer_disk",),
        labels=("trailer",),
        ids=("trailer",),
    )
    if attrs:
        return attrs
    attrs = extract_component_attributes(
        request_data,
        types=("card_with_image",),
        labels=("trailer",),
        ids=("trailer",),
    )
    return attrs


def detect_scan_role(request_data, raw_data=None, component_values=None):
    request_data = request_data if isinstance(request_data, dict) else {}
    raw_data = raw_data if isinstance(raw_data, dict) else {}
    component_values = component_values if isinstance(component_values, dict) else {}
    source = {**raw_data, **request_data}

    vehicle_kind = str(
        source.get("vehicle_kind")
        or component_values.get("vehicle_kind")
        or ""
    ).strip().lower()
    if vehicle_kind == "trailer":
        return "trailer"

    scan_role = str(source.get("scan_role") or "").strip().lower()
    if scan_role == "trailer":
        return "trailer"

    document_type = str(source.get("document_type") or "").strip().lower()
    scan_type = str(source.get("scan_type") or "").strip().lower()
    if "trailer" in document_type or "trailer" in scan_type:
        return "trailer"

    components = extract_components(request_data)
    for component in components:
        text = _component_text(component)
        if "trailer" in text or str(component.get("vehicle_kind") or "").strip().lower() == "trailer":
            return "trailer"

    return "vehicle"


def build_driver_details(request_data, raw_data, component_values, extract_record=None, list_to_string=None):
    extract_record = extract_record or (lambda data, key: {})
    list_to_string = list_to_string or (lambda value: ", ".join(str(item) for item in value if item) if isinstance(value, list) else ("" if value is None else str(value)))
    raw_data = raw_data if isinstance(raw_data, dict) else {}
    request_data = request_data if isinstance(request_data, dict) else {}
    source = {**raw_data, **request_data}
    license_record = {
        **extract_record(raw_data, "license"),
        **extract_record(request_data, "license"),
    } or extract_record(source, "license") or source
    return {
        "full_name": component_values.get("full_name") or license_record.get("surname") or license_record.get("name") or "",
        "id_number": license_record.get("id_number") or component_values.get("id_number") or "",
        "license_number": license_record.get("license_number") or "",
        "gender": license_record.get("gender") or component_values.get("gender") or "",
        "birthdate": license_record.get("birthdate") or "",
        "issue_date": license_record.get("license_issue_date") or "",
        "expiry_date": license_record.get("license_expiry_date") or "",
        "prdp_code": license_record.get("prdp_code") or "",
        "prdp_expiry_date": license_record.get("prdp_expiry_date") or "",
        "status": "VALID" if license_record.get("license_expiry_date") else "",
        "vehicle_codes": list_to_string(license_record.get("vehicle_codes")),
        "driver_restrictions": license_record.get("driver_restriction_codes") or "",
        "residence_type": component_values.get("residence_type") or "",
        "phone_number": component_values.get("phone_number") or "",
        "company_selection": component_values.get("company_selection") or "",
    }


def build_vehicle_details(request_data, raw_data, component_values, extract_record=None):
    extract_record = extract_record or (lambda data, key: {})
    raw_data = raw_data if isinstance(raw_data, dict) else {}
    request_data = request_data if isinstance(request_data, dict) else {}
    source = {**raw_data, **request_data}
    component_attrs = extract_vehicle_component_details(request_data)
    vehicle_record = {
        **extract_record(raw_data, "vehicle"),
        **extract_record(request_data, "vehicle"),
    } or extract_record(source, "vehicle") or source
    component_plate = (
        component_attrs.get("number_plate")
        or component_attrs.get("plate_number")
        or component_attrs.get("plate")
        or component_attrs.get("vehicle_register_number")
        or ""
    )
    component_make = component_attrs.get("make") or ""
    component_model = component_attrs.get("model") or ""
    component_make_model = component_attrs.get("make_model") or component_attrs.get("make/model") or ""
    component_color = component_attrs.get("color") or component_attrs.get("colour") or ""
    component_expiry = component_attrs.get("expiry_date") or component_attrs.get("expiry") or ""
    if not component_make_model and (component_make or component_model):
        component_make_model = f"{component_make} {component_model}".strip()
    return {
        "plate_number": component_values.get("vehicle_plate") or component_plate or vehicle_record.get("plate_number") or vehicle_record.get("vehicle_register_number") or "",
        "make_model": component_values.get("vehicle_make_model") or component_make_model or f"{vehicle_record.get('make', '')} {vehicle_record.get('model', '')}".strip() or "",
        "color": component_values.get("vehicle_color") or component_color or vehicle_record.get("colour") or vehicle_record.get("color_english") or vehicle_record.get("color_afrikaans") or "",
        "vin": vehicle_record.get("vin") or "",
        "engine_number": vehicle_record.get("engine_number") or "",
        "expiry_date": component_expiry or vehicle_record.get("expiry_date") or "",
        "vehicle_type": vehicle_record.get("vehicle_type") or vehicle_record.get("document_type") or "",
        "vehicle_kind": vehicle_record.get("vehicle_kind") or "",
        "province": vehicle_record.get("province") or "",
        "status": vehicle_record.get("status") or vehicle_record.get("expiry_status") or "",
    }


def build_trailer_details(request_data, raw_data, component_values, extract_record=None):
    extract_record = extract_record or (lambda data, key: {})
    raw_data = raw_data if isinstance(raw_data, dict) else {}
    request_data = request_data if isinstance(request_data, dict) else {}
    source = {**raw_data, **request_data}
    component_attrs = extract_trailer_component_details(request_data)
    trailer_record = {
        **extract_record(raw_data, "trailer"),
        **extract_record(request_data, "trailer"),
    }
    if not trailer_record:
        trailer_record = {
            **extract_record(raw_data, "vehicle"),
            **extract_record(request_data, "vehicle"),
        } or source
    vehicle_kind = (trailer_record.get("vehicle_kind") or component_values.get("vehicle_kind") or "").strip().lower()
    document_type = str(trailer_record.get("document_type") or "").strip().lower()
    scan_type = str(trailer_record.get("scan_type") or "").strip().lower()
    trailer_hint = any([
        vehicle_kind == "trailer",
        "trailer" in document_type,
        "trailer" in scan_type,
        bool(component_attrs),
        bool(component_values.get("trailer_plate")),
        bool(component_values.get("trailer_make_model")),
        bool(component_values.get("trailer_color")),
        bool(component_values.get("trailer_expiry_date")),
        bool(extract_record(source, "trailer")),
    ])
    if not trailer_hint:
        return {}

    component_plate = (
        component_attrs.get("number_plate")
        or component_attrs.get("plate_number")
        or component_attrs.get("plate")
        or component_attrs.get("vehicle_register_number")
        or ""
    )
    component_make = component_attrs.get("make") or ""
    component_model = component_attrs.get("model") or ""
    component_make_model = component_attrs.get("make_model") or component_attrs.get("make/model") or ""
    component_color = component_attrs.get("color") or component_attrs.get("colour") or ""
    component_expiry = component_attrs.get("expiry_date") or component_attrs.get("expiry") or ""
    if not component_make_model and (component_make or component_model):
        component_make_model = f"{component_make} {component_model}".strip()

    trailer_plate = component_values.get("trailer_plate") or component_plate or trailer_record.get("plate_number") or trailer_record.get("vehicle_register_number") or ""
    trailer_make_model = component_values.get("trailer_make_model") or component_make_model or f"{trailer_record.get('make', '')} {trailer_record.get('model', '')}".strip()
    trailer_color = component_values.get("trailer_color") or component_color or trailer_record.get("colour") or trailer_record.get("color_english") or trailer_record.get("color_afrikaans") or ""
    trailer_expiry = component_values.get("trailer_expiry_date") or component_expiry or trailer_record.get("expiry_date") or ""
    if not trailer_plate:
        trailer_plate = (
            trailer_record.get("number_plate")
            or trailer_record.get("plate")
            or trailer_record.get("plate_number")
            or trailer_record.get("vehicle_register_number")
            or ""
        )
    if not trailer_make_model:
        trailer_make_model = (
            component_values.get("trailer_make_model")
            or component_values.get("vehicle_make_model")
            or component_make_model
            or f"{trailer_record.get('make', '')} {trailer_record.get('model', '')}".strip()
        )
    if not trailer_color:
        trailer_color = component_values.get("trailer_color") or component_values.get("vehicle_color") or component_color or ""
    if not trailer_expiry:
        trailer_expiry = component_expiry or trailer_record.get("expiry_date") or ""

    if not any([trailer_plate, trailer_make_model, trailer_color, trailer_expiry, trailer_record.get("vehicle_type"), vehicle_kind == "trailer"]):
        return {}

    return {
        "plate_number": trailer_plate,
        "make_model": trailer_make_model,
        "color": trailer_color,
        "expiry_date": trailer_expiry,
        "vehicle_type": trailer_record.get("vehicle_type") or trailer_record.get("document_type") or "",
        "vehicle_kind": trailer_record.get("vehicle_kind") or component_values.get("vehicle_kind") or "",
        "vin": trailer_record.get("vin") or "",
        "engine_number": trailer_record.get("engine_number") or "",
        "province": trailer_record.get("province") or "",
        "status": trailer_record.get("status") or trailer_record.get("expiry_status") or "",
    }
