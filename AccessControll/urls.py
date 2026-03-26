"""
URL configuration for AccessControll project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from . import views  # Import views to reference config_view
from workflows import views as workflow_views

schema_view = get_schema_view(
    openapi.Info(
        title="GateCore API",
        default_version='v1',
        description="API documentation for GateCore access control system",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # API routes first so /api/v1/voip/calls/ etc. are not swallowed by frontend
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('api/v1/', include('workflows.urls')),
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/voip/', include('voip.urls')),
    path('api/v1/face-devices/', include('face_devices.urls')),
    # Face-device HTTP upload compatibility routes (some firmware posts without /api/v1 prefix)
    re_path(r'^record/face/?$', workflow_views.face_record_event, name='compat_record_face'),
    re_path(r'^FaceRecord/?$', workflow_views.face_record_event_legacy, name='compat_face_record_legacy'),
    re_path(r'^recordvisit/?$', workflow_views.record_visit_event, name='compat_record_visit'),
    re_path(r'^client_write_record/?$', workflow_views.client_write_record_event, name='compat_client_write_record'),
    re_path(r'^web_qrcode_url/?$', workflow_views.client_write_record_event, name='compat_web_qrcode_url'),
    re_path(r'^visitor/application-entry/?$', workflow_views.visitor_application_entry_page, name='compat_visitor_application_entry'),
    re_path(r'^upload_logs/?$', workflow_views.upload_logs_event, name='compat_upload_logs'),
    re_path(r'^stranger/?$', workflow_views.stranger_event, name='compat_stranger_event'),
    path('api/v1/config/', views.config_view, name='config'),
    path('api/gatecore/', include('GateCore.urls')),
    # Frontend VoIP UI (top-level) -> maps /voip/accounts/
    path('voip/', include('frontend.voip.urls')),
    path('workflows/', include('frontend.urls_workflows')),
    # Frontend (builder, gatecore UI) last so it does not catch API paths
    path('', include('frontend.urls')),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('swagger/residence-app.yaml', views.residence_app_openapi_yaml, name='residence_app_openapi_yaml'),
    path('swagger/residence-app/', views.residence_app_swagger_ui, name='residence_app_swagger_ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
