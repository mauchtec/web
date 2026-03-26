"""
Add Operator group to existing mobile users whose person is in a unit that has workflow access (Security group).
Run after adding units to Security so existing users get workflow access without re-login.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group as AuthGroup

from GateCore.models.groups import Group as GateCoreGroup
from GateCore.models import UnitGroupMembership, Occupancy

User = get_user_model()


class Command(BaseCommand):
    help = "Add Operator to existing users whose person is in a Security (workflow-access) unit."

    def handle(self, *args, **options):
        workflow_groups = GateCoreGroup.objects.filter(
            grants_workflow_access=True, is_active=True, is_deleted=False
        )
        if not workflow_groups.exists():
            self.stdout.write(self.style.WARNING("No group with grants_workflow_access=True. Nothing to do."))
            return
        unit_ids = set(
            UnitGroupMembership.objects.filter(
                group__in=workflow_groups, is_active=True, is_deleted=False
            ).values_list("unit_id", flat=True).distinct()
        )
        if not unit_ids:
            self.stdout.write(self.style.WARNING("No units in workflow-access groups. Nothing to do."))
            return
        operator_group, _ = AuthGroup.objects.get_or_create(name="Operator")
        updated = 0
        from GateCore.models import Person
        for person in Person.objects.filter(user__isnull=False).select_related("user"):
            if not Occupancy.objects.filter(
                person=person,
                unit_id__in=unit_ids,
                is_active=True,
                is_deleted=False,
            ).exists():
                continue
            user = person.user
            if not user.groups.filter(name="Operator").exists():
                user.groups.add(operator_group)
                updated += 1
                self.stdout.write(self.style.SUCCESS("  Added Operator to user for %s (%s)" % (person.full_name, person.phone)))
        self.stdout.write(self.style.SUCCESS("Done: %s user(s) granted Operator." % updated))
