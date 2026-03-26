from io import BytesIO
import base64
import json
from typing import Dict, Any
import qrcode
from django.utils import timezone

from GateCore.models import ScheduleRule


def generate_qr_base64(payload: Dict[str, Any]) -> str:
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(json.dumps(payload))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def build_preclearance_qr(data: Dict[str, Any], user) -> Dict[str, Any]:
    rule = ScheduleRule(
        name=data.get('name') or f"Preclearance {timezone.now().isoformat()}",
        unit=data.get('unit'),
        visitor_full_name=data.get('visitor_full_name') or '',
        visitor_mobile=data.get('visitor_mobile') or '',
        visitor_email=data.get('visitor_email') or '',
        schedule_kind='preclearance',
        is_active=True,
        created_by=user if user and user.is_authenticated else None,
        modified_by=user if user and user.is_authenticated else None,
        valid_from=timezone.now().date(),
    )
    rule.save()

    payload = {
        "pin": rule.pin,
        "pin_type": "preclearance",
        "unit_code": rule.unit.unit_code if rule.unit else None,
        "visitor_full_name": rule.visitor_full_name,
        "visitor_mobile": rule.visitor_mobile,
        "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
        "valid_until": rule.valid_until.isoformat() if rule.valid_until else None,
    }

    qr_base64 = generate_qr_base64(payload)

    return {
        "rule": rule,
        "payload": payload,
        "qr_base64": qr_base64,
    }
