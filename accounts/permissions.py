from rest_framework.permissions import BasePermission, SAFE_METHODS


class WorkflowRolePermission(BasePermission):
    READ_GROUPS = {"Operator", "SecurityManager", "Admin", "Auditor", "Device"}
    WRITE_GROUPS = {"SecurityManager", "Admin", "Device"}
    ADDITIONAL_WRITE_GROUPS = {"Operator", "Auditor"}  # Add more groups for POST access

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        group_names = set(user.groups.values_list("name", flat=True))
        if request.method in SAFE_METHODS:
            return not group_names.isdisjoint(self.READ_GROUPS)
        # Allow write access for additional groups
        return not group_names.isdisjoint(self.WRITE_GROUPS | self.ADDITIONAL_WRITE_GROUPS)
