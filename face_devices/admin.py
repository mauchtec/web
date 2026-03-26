from django.contrib import admin

from .models import FaceDeviceAccessLog, FaceDeviceAction, FaceDeviceEvent, FaceDeviceStrangerEvent, FaceDeviceUserState


@admin.register(FaceDeviceEvent)
class FaceDeviceEventAdmin(admin.ModelAdmin):
    list_display = ("event_time", "device_identifier", "direction", "command", "status", "remote_ip")
    list_filter = ("direction", "status", "command")
    search_fields = ("device_identifier", "command", "remote_ip")
    ordering = ("-event_time",)


@admin.register(FaceDeviceAction)
class FaceDeviceActionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "device_identifier", "action", "status", "requested_by", "started_at", "completed_at")
    list_filter = ("action", "status")
    search_fields = ("device_identifier", "error")
    ordering = ("-created_at",)


@admin.register(FaceDeviceAccessLog)
class FaceDeviceAccessLogAdmin(admin.ModelAdmin):
    list_display = ("event_time", "device_identifier", "result", "person", "confidence", "source_command")
    list_filter = ("result", "source_command")
    search_fields = ("device_identifier", "person__first_name", "person__last_name", "person__id_number")
    ordering = ("-event_time",)


@admin.register(FaceDeviceUserState)
class FaceDeviceUserStateAdmin(admin.ModelAdmin):
    list_display = ("device_identifier", "user_identifier", "state", "person", "last_seen_on_device_at")
    list_filter = ("state",)
    search_fields = ("device_identifier", "user_identifier", "person__first_name", "person__last_name", "person__id_number")
    ordering = ("device_identifier", "user_identifier")


@admin.register(FaceDeviceStrangerEvent)
class FaceDeviceStrangerEventAdmin(admin.ModelAdmin):
    list_display = ("event_time", "device_identifier", "status", "credential_type", "credential_value", "confidence", "source_command")
    list_filter = ("status", "credential_type", "source_command")
    search_fields = ("device_identifier", "credential_value", "review_notes", "remote_ip")
    ordering = ("-event_time",)
