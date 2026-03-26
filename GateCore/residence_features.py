"""
Residence permission tiers for the resident app.

Residence Basic: generate 24h codes, invite delivery, invite contact, future booking, regulars.
Residence Advanced: everything in Basic + group booking.

Security / Amenities units use the operator app (workflows); residents use the resident app
and are gated by this feature matrix.
"""

# Feature keys the resident app can use to show/hide or enable/disable UI.
RESIDENCE_FEATURE_GENERATE_CODE_24H = "generate_code_24h"
RESIDENCE_FEATURE_INVITE_DELIVERY = "invite_delivery"
RESIDENCE_FEATURE_INVITE_CONTACT = "invite_contact"
RESIDENCE_FEATURE_FUTURE_BOOKING = "future_booking"
RESIDENCE_FEATURE_REGULARS = "regulars"
RESIDENCE_FEATURE_GROUP_BOOKING = "group_booking"

# Human-readable labels for app or admin.
RESIDENCE_FEATURE_LABELS = {
    RESIDENCE_FEATURE_GENERATE_CODE_24H: "Generate code (expires within 24h)",
    RESIDENCE_FEATURE_INVITE_DELIVERY: "Invite a delivery",
    RESIDENCE_FEATURE_INVITE_CONTACT: "Invite a contact",
    RESIDENCE_FEATURE_FUTURE_BOOKING: "Future booking",
    RESIDENCE_FEATURE_REGULARS: "Regulars",
    RESIDENCE_FEATURE_GROUP_BOOKING: "Group booking",
}

# Which permission level gets which features. Advanced includes all Basic.
RESIDENCE_BASIC_FEATURES = frozenset({
    RESIDENCE_FEATURE_GENERATE_CODE_24H,
    RESIDENCE_FEATURE_INVITE_DELIVERY,
    RESIDENCE_FEATURE_INVITE_CONTACT,
    RESIDENCE_FEATURE_FUTURE_BOOKING,
    RESIDENCE_FEATURE_REGULARS,
})

RESIDENCE_ADVANCED_EXTRA_FEATURES = frozenset({
    RESIDENCE_FEATURE_GROUP_BOOKING,
})

# Unit.permissions value -> allowed feature set (for residence app only; security/amenities use operator app).
PERMISSION_TO_FEATURES = {
    "residence_basic": RESIDENCE_BASIC_FEATURES,
    "residence_advanced": RESIDENCE_BASIC_FEATURES | RESIDENCE_ADVANCED_EXTRA_FEATURES,
    "security": frozenset(),   # Uses operator app / workflows, not resident features
    "amenities": frozenset(), # Same
}


def get_allowed_residence_features(unit_permissions: str):
    """
    Return the set of resident app feature keys allowed for the given unit permission level.

    Args:
        unit_permissions: Unit.permissions value, e.g. "residence_basic", "residence_advanced".

    Returns:
        Frozenset of feature keys (e.g. "generate_code_24h", "invite_delivery").
        Empty set for security/amenities (resident app should not expose these; they use operator app).
    """
    return PERMISSION_TO_FEATURES.get(
        (unit_permissions or "").strip() or "residence_basic",
        RESIDENCE_BASIC_FEATURES,
    )


def unit_can_use_feature(unit_permissions: str, feature_key: str) -> bool:
    """Return True if the given permission level allows the feature."""
    return feature_key in get_allowed_residence_features(unit_permissions)


def get_capabilities_for_resident_app(unit_permissions: str):
    """
    Return a dict suitable for the resident app: feature_key -> True for allowed features.

    Example: {"generate_code_24h": True, "invite_delivery": True, ...}
    """
    features = get_allowed_residence_features(unit_permissions)
    return {f: True for f in features}
