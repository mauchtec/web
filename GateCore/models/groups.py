from django.db import models
from django.utils import timezone
from .base import BaseModel


class Group(BaseModel):
    """
    Groups allow units and Android apps to be organized together.
    People in units that belong to a group automatically get permissions
    based on the group's access permissions.
    If grants_workflow_access is True, people in units in this group get
    Django workflow roles (e.g. Operator) on mobile login so they can see workflows.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    grants_workflow_access = models.BooleanField(
        default=False,
        help_text="If True, people in units in this group get Operator (workflow) role on mobile login.",
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name', 'is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = "Group"
        verbose_name_plural = "Groups"
    
    def __str__(self):
        return self.name


class UnitGroupMembership(BaseModel):
    """
    Many-to-many relationship between Units and Groups.
    A unit can belong to multiple groups.
    """
    unit = models.ForeignKey(
        "Unit",
        on_delete=models.CASCADE,
        related_name="group_memberships"
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="unit_memberships"
    )
    joined_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['group', 'unit']
        unique_together = ["unit", "group"]
        indexes = [
            models.Index(fields=['unit', 'is_active']),
            models.Index(fields=['group', 'is_active']),
        ]
        verbose_name = "Unit Group Membership"
        verbose_name_plural = "Unit Group Memberships"
    
    def __str__(self):
        return f"{self.unit.unit_code} → {self.group.name}"


class AndroidApp(BaseModel):
    """
    Represents an Android app installation that can be assigned to a group.
    This allows the app to grant permissions to people in units that belong to the same group.
    """
    name = models.CharField(max_length=100)
    device_identifier = models.CharField(max_length=200, unique=True, blank=True, null=True)
    device_token = models.CharField(max_length=255, unique=True, blank=True, null=True)
    app_version = models.CharField(max_length=50, blank=True)
    device_model = models.CharField(max_length=200, blank=True)
    device_os = models.CharField(max_length=50, blank=True)
    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="android_apps"
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name', '-last_seen']
        indexes = [
            models.Index(fields=['device_identifier']),
            models.Index(fields=['device_token']),
            models.Index(fields=['group', 'is_active']),
        ]
        verbose_name = "Android App"
        verbose_name_plural = "Android Apps"
    
    def __str__(self):
        return f"{self.name} ({self.device_identifier or 'No ID'})"


class GroupAccessPermission(BaseModel):
    """
    Defines access permissions for a group to an access point.
    All people in units that belong to this group will have access
    to the specified access point based on these permissions.
    """
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="access_permissions"
    )
    access_point = models.ForeignKey(
        "AccessPoint",
        on_delete=models.CASCADE,
        related_name="group_permissions"
    )
    schedule_rule = models.ForeignKey(
        "ScheduleRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_permissions"
    )
    schedule_override = models.JSONField(default=dict, blank=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_daily_uses = models.IntegerField(default=0)  # 0 means unlimited
    priority = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['-priority', 'group']
        unique_together = ["group", "access_point"]
        indexes = [
            models.Index(fields=['group', 'is_active']),
            models.Index(fields=['access_point', 'valid_until']),
            models.Index(fields=['valid_until', 'is_active']),
        ]
        verbose_name = "Group Access Permission"
        verbose_name_plural = "Group Access Permissions"
    
    def __str__(self):
        return f"{self.group.name} → {self.access_point.name}"
    
    @property
    def is_valid_now(self):
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.schedule_rule:
            return self.schedule_rule.is_allowed_now()
        return True
    
    def can_access(self):
        """
        Check if this group permission is currently valid.
        Note: Daily use limits are tracked per person, not per group.
        """
        return self.is_valid_now
