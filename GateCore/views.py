from django.shortcuts import render
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework import viewsets
from .models import (
    Site, Property, Unit, Tenant,
    Person, Vehicle, DriverVehicleAssociation,
    RawScanArchive, DriverLicense, VehicleRegistration,
    Occupancy, GuestRegistration,
    AccessPoint, AccessDevice, AccessCredential,
    ScheduleRule, AccessPermission, AccessLog, Blacklist,
    BlockHistory
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

# New model serializers
class TenantSerializer(serializers.ModelSerializer):
    unit_details = UnitSerializer(source='unit', read_only=True)
    
    class Meta:
        model = Tenant
        fields = '__all__'
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class RawScanArchiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawScanArchive
        fields = '__all__'
        read_only_fields = ['sha256_hash', 'scan_time']

class DriverLicenseSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    scan_details = RawScanArchiveSerializer(source='raw_scan', read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = DriverLicense
        fields = '__all__'
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']
    
    def get_is_expired(self, obj):
        from django.utils import timezone
        return obj.expiry_date < timezone.now().date()

class VehicleRegistrationSerializer(serializers.ModelSerializer):
    vehicle_details = VehicleSerializer(source='vehicle', read_only=True)
    scan_details = RawScanArchiveSerializer(source='raw_scan', read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = VehicleRegistration
        fields = '__all__'
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']
    
    def get_is_expired(self, obj):
        from django.utils import timezone
        return obj.expiry_date < timezone.now().date()

class DriverVehicleAssociationSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.license_plate', read_only=True)
    
    class Meta:
        model = DriverVehicleAssociation
        fields = '__all__'
        read_only_fields = ['first_seen', 'last_seen', 'created_at', 'modified_at', 'created_by', 'modified_by']

class BlockHistorySerializer(serializers.ModelSerializer):
    actioned_by_username = serializers.CharField(source='actioned_by.username', read_only=True)
    
    class Meta:
        model = BlockHistory
        fields = '__all__'
        read_only_fields = ['actioned_at']

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
    filterset_fields = ['is_active', 'gender', 'is_blocked']
    search_fields = ['first_name', 'last_name', 'id_number', 'phone', 'email']
    ordering_fields = ['last_name', 'first_name']
    
    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        """Block a person"""
        person = self.get_object()
        person.is_blocked = True
        person.block_reason = request.data.get('reason', 'Blocked by admin')
        person.save()
        
        # Create block history
        BlockHistory.objects.create(
            entity_type='person',
            entity_id=person.id,
            action='blocked',
            reason=person.block_reason,
            actioned_by=request.user if request.user.is_authenticated else None
        )
        
        serializer = self.get_serializer(person)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        """Unblock a person"""
        person = self.get_object()
        person.is_blocked = False
        person.block_reason = ''
        person.save()
        
        # Create block history
        BlockHistory.objects.create(
            entity_type='person',
            entity_id=person.id,
            action='unblocked',
            reason=request.data.get('reason', 'Unblocked by admin'),
            actioned_by=request.user if request.user.is_authenticated else None
        )
        
        serializer = self.get_serializer(person)
        return Response(serializer.data)

class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['person', 'vehicle_type', 'is_active', 'is_blocked']
    search_fields = ['license_plate', 'model', 'make', 'vin', 'engine_number']
    ordering_fields = ['license_plate', 'vehicle_type']
    
    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        """Block a vehicle"""
        vehicle = self.get_object()
        vehicle.is_blocked = True
        vehicle.block_reason = request.data.get('reason', 'Blocked by admin')
        vehicle.save()
        
        # Create block history
        BlockHistory.objects.create(
            entity_type='vehicle',
            entity_id=vehicle.id,
            action='blocked',
            reason=vehicle.block_reason,
            actioned_by=request.user if request.user.is_authenticated else None
        )
        
        serializer = self.get_serializer(vehicle)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        """Unblock a vehicle"""
        vehicle = self.get_object()
        vehicle.is_blocked = False
        vehicle.block_reason = ''
        vehicle.save()
        
        # Create block history
        BlockHistory.objects.create(
            entity_type='vehicle',
            entity_id=vehicle.id,
            action='unblocked',
            reason=request.data.get('reason', 'Unblocked by admin'),
            actioned_by=request.user if request.user.is_authenticated else None
        )
        
        serializer = self.get_serializer(vehicle)
        return Response(serializer.data)

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
    filterset_fields = ['person', 'access_point', 'result', 'vehicle', 'access_method', 'visiting_tenant']
    search_fields = ['reason', 'credential_value_used', 'visit_purpose', 'visiting_freeform']
    ordering_fields = ['timestamp', 'result', 'entry_time', 'exit_time']

class BlacklistViewSet(viewsets.ModelViewSet):
    queryset = Blacklist.objects.all()
    serializer_class = BlacklistSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['target_type', 'reason', 'is_active']
    search_fields = ['details']
    ordering_fields = ['blacklisted_from', 'blacklisted_until']

# New model viewsets
class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['unit', 'is_active']
    search_fields = ['name', 'company', 'phone', 'email']
    ordering_fields = ['name', 'company']

class RawScanArchiveViewSet(viewsets.ModelViewSet):
    queryset = RawScanArchive.objects.all()
    serializer_class = RawScanArchiveSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['document_type', 'processed', 'source_device']
    search_fields = ['sha256_hash', 'source_device']
    ordering_fields = ['scan_time', 'document_type']

class DriverLicenseViewSet(viewsets.ModelViewSet):
    queryset = DriverLicense.objects.all()
    serializer_class = DriverLicenseSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['person', 'status', 'is_active']
    search_fields = ['license_number', 'driver_restriction_codes']
    ordering_fields = ['issue_date', 'expiry_date', 'status']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by expiry status
        expired = self.request.query_params.get('expired', None)
        if expired is not None:
            from django.utils import timezone
            today = timezone.now().date()
            if expired.lower() == 'true':
                queryset = queryset.filter(expiry_date__lt=today)
            elif expired.lower() == 'false':
                queryset = queryset.filter(expiry_date__gte=today)
        return queryset
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get licenses expiring within next 30 days"""
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        thirty_days = today + timedelta(days=30)
        expiring = self.queryset.filter(
            expiry_date__gte=today,
            expiry_date__lte=thirty_days,
            status='valid'
        )
        serializer = self.get_serializer(expiring, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        """Block a driver license"""
        license = self.get_object()
        license.status = 'blocked'
        license.save()
        
        # Create block history
        BlockHistory.objects.create(
            entity_type='person',
            entity_id=license.person.id,
            action='blocked',
            reason=request.data.get('reason', 'License blocked'),
            actioned_by=request.user if request.user.is_authenticated else None
        )
        
        serializer = self.get_serializer(license)
        return Response(serializer.data)

class VehicleRegistrationViewSet(viewsets.ModelViewSet):
    queryset = VehicleRegistration.objects.all()
    serializer_class = VehicleRegistrationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vehicle', 'status', 'is_active']
    search_fields = ['plate_number', 'disk_number', 'vehicle_register_number']
    ordering_fields = ['expiry_date', 'status']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by expiry status
        expired = self.request.query_params.get('expired', None)
        if expired is not None:
            from django.utils import timezone
            today = timezone.now().date()
            if expired.lower() == 'true':
                queryset = queryset.filter(expiry_date__lt=today)
            elif expired.lower() == 'false':
                queryset = queryset.filter(expiry_date__gte=today)
        return queryset
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get vehicle registrations expiring within next 30 days"""
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        thirty_days = today + timedelta(days=30)
        expiring = self.queryset.filter(
            expiry_date__gte=today,
            expiry_date__lte=thirty_days,
            status='valid'
        )
        serializer = self.get_serializer(expiring, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_plate(self, request):
        """Lookup vehicle registration by plate number"""
        plate = request.query_params.get('plate', None)
        if not plate:
            return Response({'error': 'plate parameter required'}, status=400)
        
        registrations = self.queryset.filter(plate_number__icontains=plate)
        serializer = self.get_serializer(registrations, many=True)
        return Response(serializer.data)

class DriverVehicleAssociationViewSet(viewsets.ModelViewSet):
    queryset = DriverVehicleAssociation.objects.all()
    serializer_class = DriverVehicleAssociationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['person', 'vehicle', 'is_primary_driver', 'is_active']
    search_fields = []
    ordering_fields = ['total_visits', 'last_seen', 'first_seen']

class BlockHistoryViewSet(viewsets.ModelViewSet):
    queryset = BlockHistory.objects.all()
    serializer_class = BlockHistorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['entity_type', 'action', 'actioned_by']
    search_fields = ['reason', 'entity_id']
    ordering_fields = ['actioned_at', 'action']

# Health Check
@api_view(['GET'])
def health_check(request):
    return Response({'status': 'ok'})
