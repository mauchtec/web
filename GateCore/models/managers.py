from django.db import models
from django.utils import timezone

class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            is_active=True,
            is_deleted=False
        )

class OccupancyManager(models.Manager):
    def current_occupants(self, unit=None):
        queryset = self.get_queryset().filter(
            is_active=True,
            is_deleted=False
        )
        if unit:
            queryset = queryset.filter(unit=unit)
        today = timezone.now().date()
        return queryset.filter(
            start_date__lte=today,
            end_date__gte=today
        )
    def get_primary_occupant(self, unit):
        try:
            return self.current_occupants(unit).filter(is_primary=True).first()
        except self.model.DoesNotExist:
            return None

class AccessPermissionManager(models.Manager):
    def valid_permissions(self, person=None, access_point=None):
        queryset = self.get_queryset().filter(
            is_active=True,
            is_deleted=False
        )
        if person:
            queryset = queryset.filter(person=person)
        if access_point:
            queryset = queryset.filter(access_point=access_point)
        now = timezone.now()
        queryset = queryset.filter(
            valid_from__lte=now
        ).filter(
            models.Q(valid_until__isnull=True) | 
            models.Q(valid_until__gte=now)
        )
        return queryset
    def can_access_now(self, person, access_point):
        permissions = self.valid_permissions(person=person, access_point=access_point)
        for permission in permissions:
            if permission.can_access():
                return True, permission
        return False, None
