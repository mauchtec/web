from django.contrib import admin
from .models import (
    Site, Property, Unit,
    Person, Vehicle,
    Occupancy, GuestRegistration,
    AccessPoint, AccessDevice, AccessCredential,
    ScheduleRule, AccessPermission, AccessLog, Blacklist
)

admin.site.register(Site)
admin.site.register(Property)
admin.site.register(Unit)
admin.site.register(Person)
admin.site.register(Vehicle)
admin.site.register(Occupancy)
admin.site.register(GuestRegistration)
admin.site.register(AccessPoint)
admin.site.register(AccessDevice)
admin.site.register(AccessCredential)
admin.site.register(ScheduleRule)
admin.site.register(AccessPermission)
admin.site.register(AccessLog)
admin.site.register(Blacklist)
