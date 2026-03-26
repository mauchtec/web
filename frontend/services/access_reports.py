from .scan_payloads import (
    extract_component_direction,
    extract_components,
    normalize_request_data,
)


def get_direction_value(components):
    payload = {"components": components}
    return extract_component_direction(payload) or None


def _normalize_component_label(component):
    label = component.get("label") or component.get("title") or component.get("id")
    return label.strip() if isinstance(label, str) else component.get("id")


def _ensure_dynamic_column(display_label, column_defs, dynamic_map):
    if display_label in dynamic_map:
        return dynamic_map[display_label]
    key = f"component_{len(dynamic_map) + 1}"
    dynamic_map[display_label] = key
    column_defs.append({"key": key, "label": display_label, "visible": False})
    return key


def flatten_components_into_row(request_data, column_defs, dynamic_map, row):
    components = extract_components(request_data)
    for comp in components:
        label = _normalize_component_label(comp) or "Component"
        if comp.get("fields"):
            for field in comp["fields"]:
                if not isinstance(field, dict):
                    continue
                field_label = field.get("label") or "Field"
                display_label = f"{label} – {field_label}"
                value = field.get("value")
                key = _ensure_dynamic_column(display_label, column_defs, dynamic_map)
                row[key] = value
        elif "value" in comp and comp.get("value") not in (None, ""):
            display_label = label
            value = comp.get("value")
            key = _ensure_dynamic_column(display_label, column_defs, dynamic_map)
            row[key] = value
        elif comp.get("direction") is not None:
            display_label = f"{label} Direction"
            key = _ensure_dynamic_column(display_label, column_defs, dynamic_map)
            row[key] = comp.get("direction")
        elif comp.get("text") is not None:
            display_label = f"{label} Text"
            key = _ensure_dynamic_column(display_label, column_defs, dynamic_map)
            row[key] = comp.get("text")
