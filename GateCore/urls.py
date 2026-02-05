from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'sites', views.SiteViewSet)
router.register(r'properties', views.PropertyViewSet)
router.register(r'units', views.UnitViewSet)
router.register(r'tenants', views.TenantViewSet)
router.register(r'persons', views.PersonViewSet)
router.register(r'vehicles', views.VehicleViewSet)
router.register(r'driver-vehicle-associations', views.DriverVehicleAssociationViewSet)
router.register(r'raw-scan-archives', views.RawScanArchiveViewSet)
router.register(r'driver-licenses', views.DriverLicenseViewSet)
router.register(r'vehicle-registrations', views.VehicleRegistrationViewSet)
router.register(r'occupancies', views.OccupancyViewSet)
router.register(r'guests', views.GuestRegistrationViewSet)
router.register(r'access-points', views.AccessPointViewSet)
router.register(r'access-devices', views.AccessDeviceViewSet)
router.register(r'access-credentials', views.AccessCredentialViewSet)
router.register(r'schedule-rules', views.ScheduleRuleViewSet)
router.register(r'access-permissions', views.AccessPermissionViewSet)
router.register(r'access-logs', views.AccessLogViewSet)
router.register(r'blacklists', views.BlacklistViewSet)
router.register(r'block-history', views.BlockHistoryViewSet)

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('', include(router.urls)),
]
