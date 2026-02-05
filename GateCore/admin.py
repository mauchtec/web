from django.contrib import admin
from .models import (
    Site, Property, Unit, Tenant,
    Person, Vehicle, DriverVehicleAssociation,
    RawScanArchive, DriverLicense, VehicleRegistration,
    Occupancy, GuestRegistration,
    AccessPoint, AccessDevice, AccessCredential,
    ScheduleRule, AccessPermission, AccessLog, Blacklist,
    BlockHistory
)

admin.site.register(Site)
admin.site.register(Property)
admin.site.register(Unit)

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "phone", "phone_device_type", "phone_otp", "facial_recognition_enabled", "email", "id_number", "is_active", "is_blocked")
    search_fields = ("first_name", "last_name", "phone", "email", "id_number")
    list_filter = ("phone_device_type", "facial_recognition_enabled", "gender", "is_active", "is_blocked")
    readonly_fields = ("created_at", "modified_at")

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

# New model admins
@admin.register(RawScanArchive)
class RawScanArchiveAdmin(admin.ModelAdmin):
    list_display = ['document_type', 'scan_time', 'sha256_hash', 'processed', 'source_device']
    list_filter = ['document_type', 'processed', 'scan_time']
    readonly_fields = ['raw_json', 'sha256_hash', 'scan_time']
    search_fields = ['sha256_hash', 'source_device']

@admin.register(DriverLicense)
class DriverLicenseAdmin(admin.ModelAdmin):
    list_display = ['license_number', 'person', 'issue_date', 'expiry_date', 'status', 'is_active']
    list_filter = ['status', 'expiry_date', 'is_active']
    search_fields = ['license_number', 'person__first_name', 'person__last_name']
    readonly_fields = ['created_at', 'modified_at']
    date_hierarchy = 'expiry_date'

@admin.register(VehicleRegistration)
class VehicleRegistrationAdmin(admin.ModelAdmin):
    list_display = ['plate_number', 'disk_number', 'vehicle', 'expiry_date', 'status', 'is_active']
    list_filter = ['status', 'expiry_date', 'is_active']
    search_fields = ['plate_number', 'disk_number', 'vehicle__vin', 'vehicle__license_plate']
    readonly_fields = ['created_at', 'modified_at']
    date_hierarchy = 'expiry_date'

@admin.register(DriverVehicleAssociation)
class DriverVehicleAssociationAdmin(admin.ModelAdmin):
    list_display = ['person', 'vehicle', 'total_visits', 'last_seen', 'is_primary_driver', 'is_active']
    list_filter = ['is_primary_driver', 'is_active']
    search_fields = ['person__first_name', 'person__last_name', 'vehicle__license_plate', 'vehicle__vin']
    readonly_fields = ['first_seen', 'last_seen', 'created_at', 'modified_at']
    date_hierarchy = 'last_seen'

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'unit', 'phone', 'email', 'is_active']
    search_fields = ['name', 'company', 'phone', 'email']
    list_filter = ['is_active', 'unit']
    readonly_fields = ['created_at', 'modified_at']

@admin.register(BlockHistory)
class BlockHistoryAdmin(admin.ModelAdmin):
    list_display = ['entity_type', 'entity_id', 'action', 'actioned_by', 'actioned_at']
    list_filter = ['entity_type', 'action', 'actioned_at']
    readonly_fields = ['actioned_at']
    search_fields = ['entity_id', 'reason']
    date_hierarchy = 'actioned_at'
