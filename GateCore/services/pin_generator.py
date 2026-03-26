"""
Central PIN generation for access control.

All PIN-issuing flows use this module so the same 5-digit PIN is never issued twice.
PIN sources and their labels:
  - voice clearance (press 9 on call): label "voiceclearance", attach resident who approved
  - system preclearance (QR): label "system"
  - residence app (future): label "AppPin"
OTP/codes for auth remain separate and are not managed here.
"""
import secrets

from GateCore.services.runtime_settings import get_pin_length


def is_pin_used(pin: str) -> bool:
    """Return True if this PIN already exists in any stored source (ScheduleRule, VoipCall, etc.)."""
    pin = (pin or "").strip()
    pin_length = get_pin_length()
    if not pin or len(pin) != pin_length or not pin.isdigit():
        return True  # treat invalid as "used" so we don't assign it
    from GateCore.models import ScheduleRule
    if ScheduleRule.objects.filter(pin=pin).exists():
        return True
    try:
        from voip.models import VoipCall
        if VoipCall.objects.filter(pin=pin).exists():
            return True
    except Exception:
        pass  # voip app not installed or not migrated
    return False


def generate_unique_pin(max_attempts: int = 20) -> str:
    """
    Generate a 5-digit PIN that is not currently used in ScheduleRule or VoipCall.
    Uses secrets for cryptographically safe randomness.
    Raises RuntimeError if no unique PIN could be generated after max_attempts.
    """
    pin_length = get_pin_length()
    pin_min = 10 ** (pin_length - 1)
    pin_max = (10 ** pin_length) - 1
    for _ in range(max_attempts):
        candidate = f"{secrets.randbelow(pin_max - pin_min + 1) + pin_min:0{pin_length}d}"
        if not is_pin_used(candidate):
            return candidate
    raise RuntimeError("Could not generate a unique PIN after %d attempts" % max_attempts)
