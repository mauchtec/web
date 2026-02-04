from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import viewsets
from .models import (
    Site, Property, Unit,
    Person, Vehicle,
    Occupancy, GuestRegistration,
    AccessPoint, AccessDevice, AccessCredential,
    ScheduleRule, AccessPermission, AccessLog, Blacklist
)
from .models import BaseModel
from rest_framework import serializers
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

# Serializers
class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = '__all__'

class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = '__all__'

class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = '__all__'

class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = '__all__'

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'

class OccupancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Occupancy
        fields = '__all__'

class GuestRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestRegistration
        fields = '__all__'

class AccessPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessPoint
        fields = '__all__'

class AccessDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessDevice
        fields = '__all__'

class AccessCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessCredential
        fields = '__all__'

class ScheduleRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleRule
        fields = '__all__'

class AccessPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessPermission
        fields = '__all__'

class AccessLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessLog
        fields = '__all__'

class BlacklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blacklist
        fields = '__all__'

# ViewSets
class SiteViewSet(viewsets.ModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['site_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'site_type']

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.all()
    serializer_class = PropertySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['site', 'property_type', 'is_active']
    search_fields = ['name', 'address']
    ordering_fields = ['name', 'property_type']

class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['property', 'unit_type', 'status', 'is_active']
    search_fields = ['unit_code']
    ordering_fields = ['unit_code', 'floor', 'status']

class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'gender']
    search_fields = ['first_name', 'last_name', 'id_number', 'phone', 'email']
    ordering_fields = ['last_name', 'first_name']

class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['person', 'vehicle_type', 'is_active']
    search_fields = ['license_plate', 'model', 'make']
    ordering_fields = ['license_plate', 'vehicle_type']

class OccupancyViewSet(viewsets.ModelViewSet):
    queryset = Occupancy.objects.all()
    serializer_class = OccupancySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['person', 'unit', 'role', 'is_active']
    search_fields = ['contract_number']
    ordering_fields = ['start_date', 'end_date']

class GuestRegistrationViewSet(viewsets.ModelViewSet):
    queryset = GuestRegistration.objects.all()
    serializer_class = GuestRegistrationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['host', 'guest', 'unit', 'status', 'is_active']
    search_fields = ['purpose', 'notes']
    ordering_fields = ['expected_arrival', 'status']

class AccessPointViewSet(viewsets.ModelViewSet):
    queryset = AccessPoint.objects.all()
    serializer_class = AccessPointSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['property', 'point_type', 'is_active']
    search_fields = ['name', 'location_description']
    ordering_fields = ['name', 'point_type']

class AccessDeviceViewSet(viewsets.ModelViewSet):
    queryset = AccessDevice.objects.all()
    serializer_class = AccessDeviceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['access_point', 'device_type', 'is_active']
    search_fields = ['serial_number', 'name']
    ordering_fields = ['device_type', 'serial_number']

class AccessCredentialViewSet(viewsets.ModelViewSet):
    queryset = AccessCredential.objects.all()
    serializer_class = AccessCredentialSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['person', 'credential_type', 'is_active']
    search_fields = ['credential_value', 'notes']
    ordering_fields = ['issued_at', 'expires_at']

class ScheduleRuleViewSet(viewsets.ModelViewSet):
    queryset = ScheduleRule.objects.all()
    serializer_class = ScheduleRuleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['schedule_type', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'schedule_type']

class AccessPermissionViewSet(viewsets.ModelViewSet):
    queryset = AccessPermission.objects.all()
    serializer_class = AccessPermissionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['person', 'access_point', 'is_active']
    search_fields = []
    ordering_fields = ['priority', 'valid_from', 'valid_until']

class AccessLogViewSet(viewsets.ModelViewSet):
    queryset = AccessLog.objects.all()
    serializer_class = AccessLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['person', 'access_point', 'result']
    search_fields = ['reason', 'credential_value_used']
    ordering_fields = ['timestamp', 'result']

class BlacklistViewSet(viewsets.ModelViewSet):
    queryset = Blacklist.objects.all()
    serializer_class = BlacklistSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['target_type', 'reason', 'is_active']
    search_fields = ['details']
    ordering_fields = ['blacklisted_from', 'blacklisted_until']

# Health Check
@api_view(['GET'])
def health_check(request):
    return Response({'status': 'ok'})
