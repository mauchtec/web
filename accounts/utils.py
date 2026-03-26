from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from workflows.models import Workflow


ROLE_PERMISSIONS = {
    "Operator": ["view_workflow"],
    "Auditor": ["view_workflow"],
    "SecurityManager": ["view_workflow", "change_workflow"],
    "Admin": ["view_workflow", "change_workflow", "add_workflow", "delete_workflow"],
}


def ensure_workflow_role_groups(verbosity=1, stdout=None):
    workflow_ct = ContentType.objects.get_for_model(Workflow)
    for role_name, perm_codes in ROLE_PERMISSIONS.items():
        group, created = Group.objects.get_or_create(name=role_name)
        if created and verbosity:
            if stdout:
                stdout.write(f"Created group {role_name}")
            else:
                print(f"Created group {role_name}")
        for codename in perm_codes:
            perm, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=workflow_ct,
                defaults={"name": f"Can {codename.replace('_', ' ')} workflow"},
            )
            group.permissions.add(perm)
