from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SiteViewSet, PropertyViewSet, UnitViewSet, PersonViewSet, VehicleViewSet, OccupancyViewSet,
    GuestRegistrationViewSet, AccessPointViewSet, AccessDeviceViewSet, AccessCredentialViewSet,
    ScheduleRuleViewSet, AccessPermissionViewSet, AccessLogViewSet, BlacklistViewSet,
    GroupViewSet, UnitGroupMembershipViewSet, AndroidAppViewSet, GroupAccessPermissionViewSet,
    health_check, batch_sync_transactions, generate_preclearance_qr, system_preclearance_use,
    android_active_pins,
)
from GateCore.runtime_settings_views import runtime_settings_page, runtime_settings_api
from GateCore.api_views.access_api import AccessRequestView
from GateCore.api_views.dashboard import dashboard_summary
from GateCore.api_views.details import person_detail, site_detail, unit_detail, vehicle_detail
from GateCore.api_views.admin_lists import (
    sms_logs_overview,
    access_credentials_overview,
    access_permissions_overview,
    guest_registrations_overview,
    blacklist_overview,
)
from GateCore.api_views.admin_details import (
    access_credential_detail,
    access_permission_detail,
    guest_registration_detail,
    blacklist_detail,
)
from GateCore.api_views.accessrules import accessrules_collection, accessrule_detail
from GateCore.api_views.mutations import (
    add_person,
    add_unit,
    import_units_excel,
    link_person_to_unit,
    reallocate_person,
    update_person,
    update_unit,
)
from GateCore.api_views.system_preclearance import system_preclearance_api
from GateCore.api_views.logs import access_logs_overview, access_log_detail, report_list_overview
from GateCore.api_views.licenses import driver_licenses_overview
from GateCore.api_views.lists import people_overview, units_overview, vehicles_overview
from GateCore.api_views.sites import site_overview
from GateCore.api_views.mobile_auth import MobileOtpRequestView, MobileOtpVerifyView
from GateCore.api_views.mobile_remotes import (
    mobile_issue_platform_visitor_qr,
    mobile_issue_resident_qr,
    mobile_remote_challenge_screen,
    mobile_scan_remote_qr,
)
from GateCore.api_views.profile import MobileProfilePhotoUploadView
from GateCore.api_views.face_enrollment import enroll_person_face
from GateCore.api_views.photo_quality import assess_person_photo_quality
from GateCore.api_views.gate_terminals import GateTerminalListView, GateTerminalDetailView, gate_terminal_bootstrap, gate_terminal_sync_preview
from GateCore.api_views.device_sync import device_changes, device_sync_ack
from GateCore.api_views.residence_bookings import bookings_overview, booking_detail
from GateCore.api_views.residence_bookings import create_booking, cancel_booking, revoke_booking_pin
from GateCore.api_views.face_update import (
    mobile_face_update,
    mobile_face_confirm_update,
    admin_face_review_queue,
    admin_face_review_resolve,
)
from GateCore.api_views.visitor_face_grants import (
    visitor_face_grants_overview,
    visitor_face_grant_detail,
    visitor_face_grant_revoke,
)
from GateCore.api_views.public_visitor_face_invites import (
    public_visitor_face_invite_detail,
    public_visitor_face_invite_enroll,
)
router = DefaultRouter()
router.register(r'sites', SiteViewSet)
router.register(r'properties', PropertyViewSet)
router.register(r'units', UnitViewSet)
router.register(r'persons', PersonViewSet)
router.register(r'vehicles', VehicleViewSet)
router.register(r'occupancies', OccupancyViewSet)
router.register(r'guests', GuestRegistrationViewSet)
router.register(r'access-points', AccessPointViewSet)
router.register(r'access-devices', AccessDeviceViewSet)
router.register(r'access-credentials', AccessCredentialViewSet)
router.register(r'schedule-rules', ScheduleRuleViewSet)
router.register(r'access-permissions', AccessPermissionViewSet)
router.register(r'access-logs', AccessLogViewSet)
router.register(r'blacklists', BlacklistViewSet)
router.register(r'groups', GroupViewSet)
router.register(r'unit-group-memberships', UnitGroupMembershipViewSet)
router.register(r'android-apps', AndroidAppViewSet)
router.register(r'group-access-permissions', GroupAccessPermissionViewSet)

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('transactions/batch-sync/', batch_sync_transactions, name='batch_sync_transactions'),
    path('preclearance/qr/', generate_preclearance_qr, name='generate_preclearance_qr'),
    path('system-preclearance/use/', system_preclearance_use, name='system_preclearance_use'),
    path('api/access-request/', AccessRequestView.as_view(), name='access-request'),
    path('dashboard/summary/', dashboard_summary, name='dashboard_summary'),
    path('sites/overview/', site_overview, name='site_overview'),
    path('people/overview/', people_overview, name='people_overview'),
    path('units/overview/', units_overview, name='units_overview'),
    path('vehicles/overview/', vehicles_overview, name='vehicles_overview'),
    path('access-logs/overview/', access_logs_overview, name='access_logs_overview_api'),
    path('access-logs/<uuid:log_id>/detail/', access_log_detail, name='access_log_detail_api'),
    path('reports/overview/', report_list_overview, name='report_list_overview_api'),
    path('driver-licenses/overview/', driver_licenses_overview, name='driver_licenses_overview_api'),
    path('bookings/overview/', bookings_overview, name='bookings_overview_api'),
    path('bookings/create/', create_booking, name='residence_booking_create_api'),
    path('bookings/<uuid:booking_id>/detail/', booking_detail, name='residence_booking_detail_api'),
    path('bookings/<uuid:booking_id>/cancel/', cancel_booking, name='residence_booking_cancel_api'),
    path('bookings/<uuid:booking_id>/revoke-pin/', revoke_booking_pin, name='residence_booking_revoke_pin_api'),
    path('sms-logs/overview/', sms_logs_overview, name='sms_logs_overview_api'),
    path('access-credentials/overview/', access_credentials_overview, name='access_credentials_overview_api'),
    path('access-permissions/overview/', access_permissions_overview, name='access_permissions_overview_api'),
    path('guest-registrations/overview/', guest_registrations_overview, name='guest_registrations_overview_api'),
    path('visitor-face-grants/overview/', visitor_face_grants_overview, name='visitor_face_grants_overview_api'),
    path('blacklist/overview/', blacklist_overview, name='blacklist_overview_api'),
    path('accessrules/', accessrules_collection, name='accessrules_collection_api'),
    path('accessrules/<int:pk>/', accessrule_detail, name='accessrule_detail_api'),
    path('system-preclearance/', system_preclearance_api, name='system_preclearance_api'),
    path('mutations/add-unit/', add_unit, name='add_unit_api'),
    path('mutations/import-units-excel/', import_units_excel, name='import_units_excel_api'),
    path('mutations/update-unit/<uuid:unit_id>/', update_unit, name='update_unit_api'),
    path('mutations/add-person/', add_person, name='add_person_api'),
    path('mutations/update-person/<uuid:person_id>/', update_person, name='update_person_api'),
    path('mutations/assess-person-photo-quality/', assess_person_photo_quality, name='assess_person_photo_quality_api'),
    path('mutations/enroll-person-face/<uuid:person_id>/', enroll_person_face, name='enroll_person_face_api'),
    path('gate-terminals/', GateTerminalListView.as_view(), name='gate_terminal_list_api'),
    path('gate-terminals/<uuid:terminal_id>/', GateTerminalDetailView.as_view(), name='gate_terminal_detail_api'),
    path('gate-terminals/<uuid:terminal_id>/preview-sync/', gate_terminal_sync_preview, name='gate_terminal_sync_preview_api'),
    path('gate-terminals/bootstrap/', gate_terminal_bootstrap, name='gate_terminal_bootstrap_api'),
    path('mutations/link-person-to-unit/', link_person_to_unit, name='link_person_to_unit_api'),
    path('mutations/reallocate-person/', reallocate_person, name='reallocate_person_api'),
    path('device/changes/', device_changes, name='device_changes_api'),
    path('device/sync-ack/', device_sync_ack, name='device_sync_ack_api'),
    path('details/access-credentials/<uuid:credential_id>/', access_credential_detail, name='access_credential_detail_api'),
    path('details/access-permissions/<uuid:perm_id>/', access_permission_detail, name='access_permission_detail_api'),
    path('details/guest-registrations/<uuid:guest_id>/', guest_registration_detail, name='guest_registration_detail_api'),
    path('details/visitor-face-grants/<uuid:grant_id>/', visitor_face_grant_detail, name='visitor_face_grant_detail_api'),
    path('details/visitor-face-grants/<uuid:grant_id>/revoke/', visitor_face_grant_revoke, name='visitor_face_grant_revoke_api'),
    path('details/blacklist/<uuid:entry_id>/', blacklist_detail, name='blacklist_detail_api'),
    path('details/people/<uuid:person_id>/', person_detail, name='person_detail_api'),
    path('details/sites/<uuid:site_id>/', site_detail, name='site_detail_api'),
    path('details/units/<uuid:unit_id>/', unit_detail, name='unit_detail_api'),
    path('details/vehicles/<uuid:vehicle_id>/', vehicle_detail, name='vehicle_detail_api'),
    path('mobile/login/request-otp/', MobileOtpRequestView.as_view(), name='mobile_login_request_otp'),
    path('mobile/login/verify-otp/', MobileOtpVerifyView.as_view(), name='mobile_login_verify_otp'),
    path('mobile/remotes/challenge-screen/', mobile_remote_challenge_screen, name='mobile_remote_challenge_screen'),
    path('mobile/remotes/issue-phone-qr/', mobile_issue_resident_qr, name='mobile_issue_resident_qr'),
    path('mobile/remotes/platform-visitor-qr/', mobile_issue_platform_visitor_qr, name='mobile_issue_platform_visitor_qr'),
    path('mobile/remotes/scan-qr/', mobile_scan_remote_qr, name='mobile_scan_remote_qr'),
    path('mobile/profile/photo/', MobileProfilePhotoUploadView.as_view(), name='mobile_profile_photo_upload'),
    path('mobile/face/update/', mobile_face_update, name='mobile_face_update'),
    path('mobile/face/confirm-update/', mobile_face_confirm_update, name='mobile_face_confirm_update'),
    path('admin/face/review-queue/', admin_face_review_queue, name='admin_face_review_queue'),
    path('admin/face/review/<uuid:face_reference_id>/resolve/', admin_face_review_resolve, name='admin_face_review_resolve'),
    path('public/visitor-face-invite/', public_visitor_face_invite_detail, name='public_visitor_face_invite_detail_api'),
    path('public/visitor-face-invite/enroll/', public_visitor_face_invite_enroll, name='public_visitor_face_invite_enroll_api'),
    path('android-active-pins/', android_active_pins, name='gatecore_android_active_pins'),
    path('settings/', runtime_settings_page, name='gatecore_runtime_settings'),
    path('settings/api/', runtime_settings_api, name='gatecore_runtime_settings_api'),
    path('', include(router.urls)),
]
