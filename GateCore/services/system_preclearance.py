import uuid
from django.utils import timezone

from typing import Dict, Any

from GateCore.models import SystemPreclearanceConfig
from GateCore.services.preclearance import build_preclearance_qr, generate_qr_base64

DEFAULT_SYSTEM_KEY = "system-preclearance"


def _create_trigger_payload(key: str) -> Dict[str, Any]:
    return {"trigger_key": key}


def refresh_system_preclearance_config(config: SystemPreclearanceConfig = None, rotate_key=False) -> SystemPreclearanceConfig:
    config = config or SystemPreclearanceConfig.objects.get_or_create(key=DEFAULT_SYSTEM_KEY)[0]
    if rotate_key or not config.key:
        config.key = str(uuid.uuid4())
    trigger_payload = _create_trigger_payload(config.key)
    config.trigger_payload = trigger_payload
    config.qr_base64 = generate_qr_base64(trigger_payload)
    config.last_rotated = timezone.now()
    config.save(update_fields=["key", "trigger_payload", "qr_base64", "last_rotated"])
    return config


def get_system_preclearance_config() -> SystemPreclearanceConfig:
    config, created = SystemPreclearanceConfig.objects.get_or_create(key=DEFAULT_SYSTEM_KEY)
    if created or not config.qr_base64 or not config.trigger_payload:
        config = refresh_system_preclearance_config(config)
    return config
