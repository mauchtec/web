from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import VoipCallViewSet, ami_event_webhook

router = DefaultRouter()
router.register(r'calls', VoipCallViewSet, basename='voip-call')

urlpatterns = [
    path('', include(router.urls)),
    path('ami-event/', ami_event_webhook, name='voip-ami-event'),
]
