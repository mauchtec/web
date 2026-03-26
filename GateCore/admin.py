from django.contrib import admin
from .models import (
    Site, Property, Unit,
    Person, Vehicle,
    Occupancy, GuestRegistration,
    AccessPoint, AccessDevice, AccessCredential,
    ScheduleRule, AccessPermission, AccessLog, Blacklist, SMSDeliveryLog, DeviceSyncJob, GateTerminal,
    Group, UnitGroupMembership, AndroidApp, GroupAccessPermission,
    RuntimeSettings,
)
from GateCore.models.access_control import AccessRule, AccessEvent

admin.site.register(Site)
admin.site.register(Property)
admin.site.register(Unit)
from django.contrib import admin
from .models.people import Person

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "phone",
        "card_number",
        "phone_device_type",
        "face_enrollment_status",
        "facial_recognition_enabled",
        "email",
        "id_number",
        "is_active",
    )
    search_fields = ("first_name", "last_name", "phone", "email", "id_number", "card_number", "face_subject_id")
    list_filter = ("phone_device_type", "face_enrollment_status", "facial_recognition_enabled", "gender", "is_active")
admin.site.register(Vehicle)
admin.site.register(Occupancy)
admin.site.register(GuestRegistration)
admin.site.register(AccessPoint)
admin.site.register(AccessDevice)
admin.site.register(AccessCredential)
@admin.register(GateTerminal)
class GateTerminalAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "serial_number",
        "site",
        "direction",
        "docking_mode",
        "approval_status",
        "last_seen_at",
    )
    search_fields = ("display_name", "serial_number", "manufacturer", "model_name", "site__name")
    list_filter = ("direction", "docking_mode", "approval_status", "site")

admin.site.register(ScheduleRule)
admin.site.register(AccessPermission)
admin.site.register(AccessLog)
admin.site.register(Blacklist)
admin.site.register(DeviceSyncJob)
admin.site.register(AccessRule)
admin.site.register(AccessEvent)
admin.site.register(Group)
admin.site.register(UnitGroupMembership)
admin.site.register(AndroidApp)
admin.site.register(GroupAccessPermission)
admin.site.register(RuntimeSettings)


@admin.register(SMSDeliveryLog)
class SMSDeliveryLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "status",
        "provider",
        "trigger",
        "recipient_phone",
        "person",
        "unit",
        "visitor_name",
        "provider_message_id",
    )
    list_filter = ("status", "provider", "trigger", "created_at")
    search_fields = (
        "recipient_phone",
        "message",
        "provider_message_id",
        "error_message",
        "visitor_name",
        "visitor_phone",
        "person__first_name",
        "person__last_name",
        "unit__unit_code",
    )
