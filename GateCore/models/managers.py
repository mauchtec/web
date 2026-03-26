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
        """
        Check if a person can access an access point.
        First checks direct permissions, then checks group-based permissions.
        """
        from django.utils import timezone

        if getattr(person, "access_expires_on", None):
            if timezone.now().date() > person.access_expires_on:
                return False, None

        # Check direct person permissions first
        permissions = self.valid_permissions(person=person, access_point=access_point)
        for permission in permissions:
            if permission.can_access():
                return True, permission
        
        # Check group-based permissions
        from .groups import GroupAccessPermission, UnitGroupMembership
        
        # Get all units where this person is an active occupant
        from .occupancy import Occupancy
        now = timezone.now()
        occupancies = Occupancy.objects.filter(
            person=person,
            is_active=True,
            is_deleted=False,
            start_date__lte=now.date(),
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now.date())
        ).select_related('unit')
        
        # Get all groups that these units belong to
        unit_ids = [occ.unit_id for occ in occupancies if occ.unit]
        if unit_ids:
            group_memberships = UnitGroupMembership.objects.filter(
                unit_id__in=unit_ids,
                is_active=True,
                is_deleted=False
            ).select_related('group')
            
            group_ids = [gm.group_id for gm in group_memberships]
            if group_ids:
                # Check if any of these groups have permissions for this access point
                group_permissions = GroupAccessPermission.objects.filter(
                    group_id__in=group_ids,
                    access_point=access_point,
                    is_active=True,
                    is_deleted=False,
                    valid_from__lte=now
                ).filter(
                    models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
                ).select_related('group', 'schedule_rule')
                
                for group_perm in group_permissions:
                    if group_perm.can_access():
                        # Return True with the group permission
                        # Note: We return the group permission, but the caller should handle
                        # daily use limits per person if needed
                        return True, group_perm
        
        return False, None
