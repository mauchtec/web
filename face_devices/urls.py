from django.urls import path

from .views import (
    face_device_actions,
    face_device_access_logs,
    face_device_access_logs_export_csv,
    face_device_access_logs_import_csv,
    face_device_app_overview,
    face_device_detail,
    face_device_events,
    face_device_list,
    face_device_stranger_event_detail,
    face_device_stranger_events,
    face_device_sync_status,
)


urlpatterns = [
    path("", face_device_app_overview, name="face_device_app_overview"),
    path("access-logs/", face_device_access_logs, name="face_device_access_logs_global"),
    path("access-logs/export/", face_device_access_logs_export_csv, name="face_device_access_logs_export_global"),
    path("access-logs/import-csv/", face_device_access_logs_import_csv, name="face_device_access_logs_import_csv"),
    path("strangers/", face_device_stranger_events, name="face_device_stranger_events_global"),
    path("strangers/<uuid:stranger_event_id>/", face_device_stranger_event_detail, name="face_device_stranger_event_detail"),
    path("devices/", face_device_list, name="face_device_list"),
    path("devices/<uuid:terminal_id>/", face_device_detail, name="face_device_detail"),
    path("devices/<uuid:terminal_id>/sync/", face_device_sync_status, name="face_device_sync_status"),
    path("devices/<uuid:terminal_id>/events/", face_device_events, name="face_device_events"),
    path("devices/<uuid:terminal_id>/access-logs/", face_device_access_logs, name="face_device_access_logs"),
    path("devices/<uuid:terminal_id>/access-logs/export/", face_device_access_logs_export_csv, name="face_device_access_logs_export"),
    path("devices/<uuid:terminal_id>/strangers/", face_device_stranger_events, name="face_device_stranger_events"),
    path("devices/<uuid:terminal_id>/actions/", face_device_actions, name="face_device_actions"),
]
