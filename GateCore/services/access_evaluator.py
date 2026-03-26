from django.db import models
from datetime import datetime
from django.utils import timezone
from GateCore.models import AccessRule, AccessEvent
from django.contrib.auth import get_user_model

User = get_user_model()

def evaluate_access(user, location, method=None):
    now = timezone.now()
    current_time = now.time()
    current_day = now.strftime('%a')  # e.g. 'Mon'

    # Find all active rules for this user or their group
    rules = AccessRule.objects.filter(
        is_active=True,
        location=location
    ).filter(
        models.Q(user=user) | models.Q(group__in=[g.name for g in user.groups.all()])
    )

    granted = False
    reason = "No matching rule found."
    for rule in rules:
        # Check time window
        if rule.start_time and rule.end_time:
            if not (rule.start_time <= current_time <= rule.end_time):
                reason = f"Outside allowed time window ({rule.start_time}-{rule.end_time})"
                continue
        # Check day of week
        if rule.days_of_week:
            allowed_days = [d.strip() for d in rule.days_of_week.split(',')]
            if current_day not in allowed_days:
                reason = f"Not allowed on {current_day}"
                continue
        # Check temporary/expiry
        if rule.temporary and rule.expires_at:
            if now > rule.expires_at:
                reason = "Temporary access expired."
                continue
        granted = True
        reason = "Access granted by rule: " + rule.name
        break

    # Log the event
    AccessEvent.objects.create(
        user=user,
        location=location,
        result='granted' if granted else 'denied',
        method=method,
        details=reason
    )
    return granted, reason
