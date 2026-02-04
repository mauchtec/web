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
from django.contrib import admin
from .models.people import Person

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "phone", "phone_device_type", "phone_otp", "facial_recognition_enabled", "email", "id_number", "is_active")
    search_fields = ("first_name", "last_name", "phone", "email", "id_number")
    list_filter = ("phone_device_type", "facial_recognition_enabled", "gender", "is_active")
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
