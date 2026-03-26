from django.conf import settings
import logging
from django.db.models import Q
from django.shortcuts import render
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework import viewsets
from .models import (
    Site, Property, Unit,
    Person, Vehicle,
    Occupancy, GuestRegistration,
    AccessPoint, AccessDevice, AccessCredential,
    ScheduleRule, AccessPermission, AccessLog, Blacklist, SMSDeliveryLog,
    Group, UnitGroupMembership, AndroidApp, GroupAccessPermission,
    validate_schedule_pin
)
from .models import BaseModel
from rest_framework import serializers
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser, BaseParser
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.core.files.base import ContentFile
import json
import base64
import binascii
import uuid
from datetime import timedelta
from rest_framework import status
from GateCore.services.preclearance import build_preclearance_qr
from GateCore.api_views.device_sync import mark_device_sync_pending
from GateCore.services.mobile_auth import send_sms, normalize_phone
from frontend.services.scan_payloads import (
    extract_components as shared_extract_components,
    normalize_request_data as shared_normalize_request_data,
)
from GateCore.services.system_preclearance import (
    get_system_preclearance_config,
    refresh_system_preclearance_config,
)
from GateCore.services.runtime_settings import get_antipassback_config, should_send_visitor_sms

logger = logging.getLogger(__name__)


class IsAuthorizedPreclearanceDevice(BasePermission):
    def has_permission(self, request, view):
        tokens = getattr(settings, "PRECLEARANCE_DEVICE_TOKENS", [])
        if tokens:
            token = request.headers.get("X-Device-Token")
            if token and token in tokens:
                return True
            return bool(request.user and request.user.is_authenticated and request.user.is_staff)
        return request.user.is_staff

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
    person_full_name = serializers.CharField(source="person.full_name", read_only=True)
    person_phone = serializers.CharField(source="person.phone", read_only=True)

    class Meta:
        model = Occupancy
        fields = [
            "id",
            "version",
            "created_by",
            "modified_by",
            "created_at",
            "modified_at",
            "is_active",
            "is_deleted",
            "deleted_at",
            "person",
            "unit",
            "role",
            "start_date",
            "end_date",
            "contract_number",
            "contract_document",
            "monthly_rent",
            "security_deposit",
            "is_primary",
            "person_full_name",
            "person_phone",
        ]

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

class NullableDateField(serializers.DateField):
    def to_internal_value(self, data):
        if data in ("", None):
            return None
        return super().to_internal_value(data)


class ScheduleRuleSerializer(serializers.ModelSerializer):
    pin = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    recur_until = NullableDateField(required=False, allow_null=True)
    preclearance_entry_used = serializers.BooleanField(read_only=True)

    class Meta:
        model = ScheduleRule
        fields = '__all__'

    def validate_pin(self, value):
        if value is None or value == "":
            return value
        try:
            validate_schedule_pin(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value.strip()


class TextJSONParser(BaseParser):
    media_type = "text/plain"

    def parse(self, stream, media_type=None, parser_context=None):
        raw = stream.read().decode("utf-8")
        if not raw.strip():
            return {}
        return json.loads(raw)


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

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'

class UnitGroupMembershipSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source='unit.unit_code', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    class Meta:
        model = UnitGroupMembership
        fields = '__all__'

class AndroidAppSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    class Meta:
        model = AndroidApp
        fields = '__all__'

class GroupAccessPermissionSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    access_point_name = serializers.CharField(source='access_point.name', read_only=True)
    
    class Meta:
        model = GroupAccessPermission
        fields = '__all__'


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAuthorizedPreclearanceDevice])
def generate_preclearance_qr(request):
    serializer = PreclearanceQrRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    result = build_preclearance_qr(data, request.user)
    payload = result["payload"]

    return Response({
        "pin": payload["pin"],
        "pin_type": payload["pin_type"],
        "qr_base64": result["qr_base64"],
        "valid_from": payload["valid_from"],
        "valid_until": payload["valid_until"],
        "unit_code": payload["unit_code"],
        "visitor_full_name": payload["visitor_full_name"],
        "visitor_mobile": payload["visitor_mobile"],
    })


@api_view(['POST'])
@permission_classes([IsAuthorizedPreclearanceDevice])
def system_preclearance_use(request):
    config = get_system_preclearance_config()
    token = request.data.get("trigger_key") or request.data.get("token")
    if token != config.key:
        return Response({"detail": "Invalid trigger token"}, status=status.HTTP_403_FORBIDDEN)

    result = build_preclearance_qr({'name': 'system'}, request.user)
    config.payload = result["payload"]
    config.save(update_fields=["payload"])

    payload = result["payload"]
    response = {
        "rule_id": str(result["rule"].id),
        "pin": payload["pin"],
        "pin_type": payload["pin_type"],
        "valid_from": payload["valid_from"],
        "valid_until": payload["valid_until"],
        "unit_code": payload["unit_code"],
        "visitor_full_name": payload["visitor_full_name"],
        "visitor_mobile": payload["visitor_mobile"],
        "qr_base64": config.qr_base64,
    }
    return Response(response)

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

    def get_authenticators(self):
        if self.request and self.request.method in ("GET", "HEAD", "OPTIONS"):
            return []
        return super().get_authenticators()

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

    def perform_create(self, serializer):
        instance = serializer.save()
        mark_device_sync_pending("Access credential created")
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        mark_device_sync_pending("Access credential updated")
        return instance

    def perform_destroy(self, instance):
        instance.delete()
        mark_device_sync_pending("Access credential deleted")

class ScheduleRuleViewSet(viewsets.ModelViewSet):
    queryset = ScheduleRule.objects.all()
    serializer_class = ScheduleRuleSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser, TextJSONParser]
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

    def perform_create(self, serializer):
        instance = serializer.save()
        mark_device_sync_pending("Access permission created")
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        mark_device_sync_pending("Access permission updated")
        return instance

    def perform_destroy(self, instance):
        instance.delete()
        mark_device_sync_pending("Access permission deleted")

class AccessLogViewSet(viewsets.ModelViewSet):
    queryset = AccessLog.objects.all()
    serializer_class = AccessLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['person', 'access_point', 'result']
    search_fields = ['reason', 'credential_value_used']
    ordering_fields = ['timestamp', 'result']

    def create(self, request, *args, **kwargs):
        _validate_preclearance_pin_usage(request.data)
        self._anti_passback_context = _validate_anti_passback(request.data)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        extra = _prepare_access_log_extra(self.request.data)
        instance = serializer.save(**extra)
        _process_anti_passback_post_save(instance, getattr(self, "_anti_passback_context", None))
        _process_preclearance_pin_use(self.request.data, instance)


def _prepare_access_log_extra(payload):
    raw_scan_data = payload.get("raw_scan_data")
    barcode_hex = payload.get("barcode_hex")
    scan_timestamp = payload.get("scan_timestamp")
    request_data = _normalize_request_data(payload)

    if raw_scan_data is None:
        if isinstance(request_data, dict):
            raw_scan_data = request_data.get("raw_scan_data")

    if isinstance(raw_scan_data, str) and raw_scan_data.strip():
        try:
            raw_scan_data = json.loads(raw_scan_data)
        except json.JSONDecodeError:
            raw_scan_data = {"raw": raw_scan_data}

    extra = {}
    if raw_scan_data is not None:
        extra["raw_scan_data"] = raw_scan_data
    if barcode_hex is not None:
        extra["barcode_hex"] = barcode_hex
    if scan_timestamp is None and (raw_scan_data is not None or barcode_hex):
        extra["scan_timestamp"] = timezone.now()

    if isinstance(request_data, dict):
        driver_photo = _decode_component_photo(request_data, {"drivers_license"})
        vehicle_photo = _decode_component_photo(request_data, {"vehicle_disk", "trailer_disk"})
        if driver_photo is None:
            driver_photo = _decode_card_with_image_photo(request_data, target="driver")
        if vehicle_photo is None:
            vehicle_photo = _decode_card_with_image_photo(request_data, target="vehicle")
        if vehicle_photo is None:
            vehicle_photo = _decode_card_with_image_photo(request_data, target="trailer")
        if driver_photo is not None:
            extra["driver_photo"] = driver_photo
        if vehicle_photo is not None:
            extra["vehicle_photo"] = vehicle_photo
        cleaned = _strip_component_photo_payloads(request_data)
        # Flatten vehicle plate from components to top level so antipassback query can find entry logs by request_data.license_plate/plate_number
        plate = _plate_from_components(cleaned.get("components"))
        if plate and not cleaned.get("license_plate") and not cleaned.get("plate_number"):
            cleaned = dict(cleaned)
            cleaned["license_plate"] = plate
            cleaned["plate_number"] = plate
        # Flatten driver license id so antipassback can match entry logs by vehicle_plate or driver_license
        driver_id = (
            cleaned.get("driver_license_id")
            or cleaned.get("id_number")
            or cleaned.get("license_number")
            or _driver_license_id_from_components(cleaned.get("components"))
        )
        if not driver_id and raw_scan_data is not None and isinstance(raw_scan_data, dict):
            driver_id = _driver_license_id_from_raw_scan_data(raw_scan_data)
        if driver_id and not cleaned.get("driver_license_id"):
            cleaned = dict(cleaned)
            cleaned["driver_license_id"] = driver_id
            if not cleaned.get("id_number"):
                cleaned["id_number"] = driver_id
        # Resolve recording_url from voip_call_id when PIN came from voice clearance
        voip_call_id = cleaned.get("voip_call_id")
        if voip_call_id:
            try:
                from voip.models import VoipCall
                call = VoipCall.objects.filter(id=voip_call_id).first()
                if call and getattr(call, "recording_url", None):
                    cleaned = dict(cleaned)
                    cleaned["recording_url"] = call.recording_url
            except Exception:
                pass
        extra["request_data"] = cleaned

    return extra


def _component_text(component):
    if not isinstance(component, dict):
        return ""
    parts = [
        component.get("type"),
        component.get("id"),
        component.get("label"),
        component.get("title"),
        component.get("vehicle_kind"),
    ]
    return " ".join(str(part or "").lower() for part in parts)


def _decode_component_photo(request_data, component_types):
    if not isinstance(request_data, dict):
        return None
    for comp in _extract_components(request_data):
        comp_type = str(comp.get("type") or "").lower()
        if comp_type not in component_types:
            continue
        photo_base64 = comp.get("photo_base64") or comp.get("photoBase64")
        if not photo_base64:
            continue
        decoded = _decode_base64_content(photo_base64)
        if decoded is None:
            continue
        raw_bytes, ext = decoded
        filename = f"{comp_type}_{uuid.uuid4().hex}.{ext}"
        return ContentFile(raw_bytes, name=filename)
    return None


def _decode_card_with_image_photo(request_data, target):
    if not isinstance(request_data, dict):
        return None
    for comp in _extract_components(request_data):
        comp_type = str(comp.get("type") or "").lower()
        if comp_type != "card_with_image":
            continue
        if not _card_with_image_matches_target(comp, target):
            continue
        photo_base64 = comp.get("photo_base64") or comp.get("photoBase64")
        if not photo_base64:
            continue
        decoded = _decode_base64_content(photo_base64)
        if decoded is None:
            continue
        raw_bytes, ext = decoded
        filename = f"card_with_image_{target}_{uuid.uuid4().hex}.{ext}"
        return ContentFile(raw_bytes, name=filename)
    return None


def _card_with_image_matches_target(component, target):
    title = str(component.get("title") or "").lower()
    comp_id = str(component.get("id") or "").lower()
    fields = component.get("fields") or []
    labels = " ".join(
        str(f.get("label") or "").lower()
        for f in fields
        if isinstance(f, dict)
    )
    text = f"{title} {comp_id} {labels}"
    if target == "vehicle":
        return any(key in text for key in ["vehicle", "plate", "make/model", "vin", "engine"])
    if target == "trailer":
        return any(key in text for key in ["trailer", "plate", "make/model", "vin", "engine"])
    if target == "driver":
        return any(key in text for key in ["driver", "personal", "identification", "license", "id", "gender", "name"])
    return False


def _decode_base64_content(value):
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    ext = "jpg"
    if "," in candidate:
        header, data = candidate.split(",", 1)
        lower_header = header.lower()
        if "image/png" in lower_header:
            ext = "png"
        elif "image/webp" in lower_header:
            ext = "webp"
        elif "image/jpeg" in lower_header or "image/jpg" in lower_header:
            ext = "jpg"
        candidate = data
    try:
        raw = base64.b64decode(candidate, validate=False)
    except (binascii.Error, ValueError, TypeError):
        return None
    if not raw:
        return None
    return raw, ext


def _strip_component_photo_payloads(request_data):
    if not isinstance(request_data, dict):
        return request_data
    cleaned = dict(request_data)
    components = cleaned.get("components")
    if isinstance(components, list):
        cleaned_components = []
        for comp in components:
            if not isinstance(comp, dict):
                cleaned_components.append(comp)
                continue
            comp_clean = dict(comp)
            comp_clean.pop("photo_base64", None)
            comp_clean.pop("photoBase64", None)
            cleaned_components.append(comp_clean)
        cleaned["components"] = cleaned_components
    return cleaned

def _normalize_request_data(payload):
    return shared_normalize_request_data(payload)

def _extract_components(request_data):
    return shared_extract_components(request_data)

def _is_exit_event(request_data, components):
    workflow_name = str(request_data.get("workflow_name") or "").lower()
    workflow_id = str(request_data.get("workflow_id") or "").lower()
    if "exit" in workflow_name or "exit" in workflow_id:
        return True
    for comp in components:
        value = str(comp.get("value") or comp.get("direction") or "").lower()
        label = str(comp.get("label") or "").lower()
        comp_id = str(comp.get("id") or "").lower()
        comp_type = str(comp.get("type") or "").lower()
        if "exit" in value:
            return True
        if "direction" in label and "exit" in value:
            return True
        if "direction" in comp_id and "exit" in value:
            return True
        if "direction" in comp_type and "exit" in value:
            return True
    return False

def _extract_pin_value(components):
    for comp in components:
        comp_type = str(comp.get("type") or "").lower()
        label = str(comp.get("label") or "").lower()
        comp_id = str(comp.get("id") or "").lower()
        matches_pin = "pin" in comp_type or "pin" in label or comp_id.startswith("pin")
        if not matches_pin:
            continue
        value = comp.get("value")
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None



def _get_direction_value(components):
    for comp in components:
        label = str(comp.get("label") or "").lower()
        comp_id = str(comp.get("id") or "").lower()
        comp_type = str(comp.get("type") or "").lower()
        if "direction" not in label and "direction" not in comp_id and "direction" not in comp_type:
            continue
        value = comp.get("value") or comp.get("direction")
        if value is None:
            continue
        text_dir = str(value).strip()
        if text_dir:
            return text_dir.lower()
    return None


def _is_truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_component_props(component):
    props = component.get("props")
    if isinstance(props, dict):
        return props
    return {}


def _extract_anti_passback_settings(payload):
    request_data = _normalize_request_data(payload)
    components = _extract_components(request_data)
    settings = get_antipassback_config()
    settings.update(
        {
            "request_data": request_data,
            "components": components,
        }
    )

    explicit_enabled = request_data.get("anti_passback_enabled") if "anti_passback_enabled" in request_data else request_data.get("antipassback_enabled") if "antipassback_enabled" in request_data else None
    if explicit_enabled is not None:
        settings["enabled"] = _is_truthy(explicit_enabled)
    if request_data.get("anti_passback_window_hours") not in (None, ""):
        settings["window_hours"] = int(request_data.get("anti_passback_window_hours") or settings["window_hours"])
    if "enforce_no_reentry_without_exit" in request_data:
        settings["enforce_no_reentry_without_exit"] = _is_truthy(request_data.get("enforce_no_reentry_without_exit", settings["enforce_no_reentry_without_exit"]))
    if "allow_manual_override" in request_data:
        settings["allow_manual_override"] = _is_truthy(request_data.get("allow_manual_override", settings["allow_manual_override"]))
    if "override_comment_required" in request_data:
        settings["override_comment_required"] = _is_truthy(request_data.get("override_comment_required", settings["override_comment_required"]))
    warning = request_data.get("warning_message")
    if warning:
        settings["warning_message"] = str(warning).strip()

    for comp in components:
        comp_type = str(comp.get("type") or "").lower()
        if comp_type not in {"anti_passback_guard", "antipassback_guard", "anti_passback"}:
            continue
        props = _get_component_props(comp)
        settings["enabled"] = _is_truthy(
            props.get("enabled", comp.get("enabled", True))
        )
        settings["window_hours"] = int(
            props.get("window_hours", comp.get("window_hours", settings["window_hours"])) or 24
        )
        settings["enforce_no_reentry_without_exit"] = _is_truthy(
            props.get(
                "enforce_no_reentry_without_exit",
                comp.get("enforce_no_reentry_without_exit", True),
            )
        )
        settings["allow_manual_override"] = _is_truthy(
            props.get("allow_manual_override", comp.get("allow_manual_override", True))
        )
        settings["override_comment_required"] = _is_truthy(
            props.get("override_comment_required", comp.get("override_comment_required", True))
        )
        warning = props.get("warning_message") or comp.get("warning_message")
        if warning:
            settings["warning_message"] = str(warning).strip()
        break

    settings["window_hours"] = max(1, min(settings["window_hours"], 72))
    return settings


def _get_event_direction(request_data, components):
    direction = (request_data.get("direction") or "").strip().lower()
    if direction in {"entry", "exit"}:
        return direction
    component_direction = _get_direction_value(components)
    if component_direction in {"entry", "exit"}:
        return component_direction
    if _is_exit_event(request_data, components):
        return "exit"
    workflow_name = str(request_data.get("workflow_name") or "").lower()
    workflow_id = str(request_data.get("workflow_id") or "").lower()
    if "entry" in workflow_name or "entry" in workflow_id or "enter" in workflow_name or "enter" in workflow_id:
        return "entry"
    return ""


def _plate_from_components(components):
    """Extract vehicle plate from workflow components (vehicle_disk sends number_plate; vehicle_card sends fields with label 'Plate')."""
    for comp in components or []:
        if not isinstance(comp, dict):
            continue
        for key in ("number_plate", "plate_number", "vehicle_register_number", "license_plate"):
            val = comp.get(key)
            if val and str(val).strip():
                return str(val).strip().upper()
        # vehicle_card (CardWithImage) sends "fields": [ {"label": "Plate", "value": "NZK612GP"}, ... ]
        for field in comp.get("fields") or []:
            if not isinstance(field, dict):
                continue
            label = str(field.get("label") or "").lower()
            if "plate" in label or "registration" in label or "number" in label:
                val = field.get("value")
                if val and str(val).strip() and not str(val).strip().lower().startswith("enter"):
                    return str(val).strip().upper()
    return None


def _driver_license_id_from_components(components):
    """Extract driver/license identifier from components (id_card, drivers_license; fields with id_number / license)."""
    for comp in components or []:
        if not isinstance(comp, dict):
            continue
        comp_type = str(comp.get("type") or "").lower()
        if "id" not in comp_type and "license" not in comp_type and "driver" not in comp_type:
            continue
        for key in ("id_number", "license_number", "id_number_used"):
            val = comp.get(key)
            if val and str(val).strip():
                return str(val).strip()
        for field in comp.get("fields") or []:
            if not isinstance(field, dict):
                continue
            label = str(field.get("label") or "").lower()
            val = field.get("value")
            if not val or not str(val).strip():
                continue
            if "id" in label and "number" in label:
                return str(val).strip()
            if "license" in label and "number" in label:
                return str(val).strip()
        props = comp.get("props") or {}
        for key in ("id_number", "license_number"):
            val = props.get(key) if isinstance(props, dict) else None
            if val and str(val).strip():
                return str(val).strip()
    return None


def _driver_license_id_from_raw_scan_data(raw_scan_data):
    """Extract driver license id from raw_scan_data (top-level or nested under 'license')."""
    if not isinstance(raw_scan_data, dict):
        return None
    for key in ("id_number", "license_number"):
        val = raw_scan_data.get(key)
        if val and str(val).strip():
            return str(val).strip()
    license_node = raw_scan_data.get("license")
    if isinstance(license_node, dict):
        for key in ("id_number", "license_number"):
            val = license_node.get(key)
            if val and str(val).strip():
                return str(val).strip()
    return None


def _resolve_anti_passback_identity(payload, request_data):
    credential_id = payload.get("credential") or payload.get("credential_id")
    if credential_id:
        return "credential", str(credential_id)
    person_id = payload.get("person") or payload.get("person_id")
    if person_id:
        return "person", str(person_id)
    credential_value = payload.get("credential_value_used") or request_data.get("credential_value_used")
    if credential_value:
        return "credential_value", str(credential_value).strip()
    for key in ("plate_number", "vehicle_register_number", "license_plate"):
        candidate = request_data.get(key)
        if candidate:
            return "vehicle_plate", str(candidate).strip().upper()
    plate = _plate_from_components(request_data.get("components"))
    if plate:
        return "vehicle_plate", plate
    for key in ("id_number", "license_number", "driver_license_id"):
        candidate = request_data.get(key)
        if candidate and str(candidate).strip():
            return "driver_license", str(candidate).strip()
    driver_id = _driver_license_id_from_components(request_data.get("components"))
    if driver_id:
        return "driver_license", driver_id
    raw_scan_data = payload.get("raw_scan_data") or request_data.get("raw_scan_data")
    if isinstance(raw_scan_data, str) and raw_scan_data.strip():
        try:
            raw_scan_data = json.loads(raw_scan_data)
        except json.JSONDecodeError:
            raw_scan_data = {}
    driver_id = _driver_license_id_from_raw_scan_data(raw_scan_data) if isinstance(raw_scan_data, dict) else None
    if driver_id:
        return "driver_license", driver_id
    return "", ""


def _is_log_entry_direction(log):
    request_data = _normalize_request_data({"request_data": log.request_data})
    components = _extract_components(request_data)
    return _get_event_direction(request_data, components) == "entry"


def _entry_is_open_for_antipassback(log):
    request_data = _normalize_request_data({"request_data": log.request_data})
    if request_data.get("anti_passback_closed_by_exit_id"):
        return False
    return True


def _build_antipassback_query(identity_type, identity_value, lower_bound):
    query = AccessLog.objects.filter(result="granted", timestamp__gte=lower_bound).order_by("timestamp")
    if identity_type == "credential":
        return query.filter(credential_id=identity_value)
    if identity_type == "person":
        return query.filter(person_id=identity_value)
    if identity_type == "credential_value":
        return query.filter(credential_value_used=identity_value)
    if identity_type == "vehicle_plate":
        # Match entry logs whether plate was stored in raw_scan_data or request_data (app may send number_plate in components, we flatten to license_plate/plate_number on save).
        return query.filter(
            Q(raw_scan_data__license_plate__iexact=identity_value)
            | Q(request_data__license_plate__iexact=identity_value)
            | Q(request_data__plate_number__iexact=identity_value)
            | Q(request_data__number_plate__iexact=identity_value)
        )
    if identity_type == "driver_license":
        # Match entry logs by driver id_number or license_number (request_data flattened on save; raw_scan_data top-level or nested under "license").
        return query.filter(
            Q(request_data__driver_license_id__iexact=identity_value)
            | Q(request_data__id_number__iexact=identity_value)
            | Q(request_data__license_number__iexact=identity_value)
            | Q(raw_scan_data__id_number__iexact=identity_value)
            | Q(raw_scan_data__license_number__iexact=identity_value)
            | Q(raw_scan_data__license__id_number__iexact=identity_value)
            | Q(raw_scan_data__license__license_number__iexact=identity_value)
        )
    return AccessLog.objects.none()


def _find_open_antipassback_entries(identity_type, identity_value, window_hours):
    lower_bound = timezone.now() - timedelta(hours=window_hours)
    candidates = _build_antipassback_query(identity_type, identity_value, lower_bound)
    open_entries = []
    for log in candidates:
        if not _is_log_entry_direction(log):
            continue
        if not _entry_is_open_for_antipassback(log):
            continue
        open_entries.append(log)
    return open_entries


def _extract_anti_passback_override(payload, request_data):
    override = _is_truthy(
        payload.get("anti_passback_override")
        or request_data.get("anti_passback_override")
        or request_data.get("antipassback_override")
    )
    comment = (
        payload.get("anti_passback_override_comment")
        or request_data.get("anti_passback_override_comment")
        or request_data.get("override_comment")
        or ""
    )
    return override, str(comment).strip()


def _validate_anti_passback(payload):
    settings = _extract_anti_passback_settings(payload)
    if not settings["enabled"]:
        return {}

    request_data = settings["request_data"]
    components = settings["components"]
    direction = _get_event_direction(request_data, components)
    if direction not in {"entry", "exit"}:
        return {}

    identity_type, identity_value = _resolve_anti_passback_identity(payload, request_data)
    if not identity_type or not identity_value:
        return {}

    open_entries = _find_open_antipassback_entries(
        identity_type=identity_type,
        identity_value=identity_value,
        window_hours=settings["window_hours"],
    )

    if direction == "exit":
        if open_entries:
            return {
                "direction": "exit",
                "identity_type": identity_type,
                "identity_value": identity_value,
                "open_entry_ids": [str(entry.id) for entry in open_entries],
            }
        override, comment = _extract_anti_passback_override(payload, request_data)
        if override and settings["allow_manual_override"]:
            if settings["override_comment_required"] and not comment:
                raise serializers.ValidationError({
                    "code": "ANTI_PASSBACK_OVERRIDE_COMMENT_REQUIRED",
                    "message": "Manual override comment is required for anti-passback.",
                })
            return {
                "direction": "exit",
                "identity_type": identity_type,
                "identity_value": identity_value,
                "manual_override": True,
                "override_comment": comment,
            }
        raise serializers.ValidationError({
            "code": "ANTI_PASSBACK",
            "message": settings["warning_message"],
        })

    if direction == "entry" and settings["enforce_no_reentry_without_exit"] and open_entries:
        raise serializers.ValidationError({
            "code": "ANTI_PASSBACK_ALREADY_INSIDE",
            "message": "Anti-passback: entry denied because an open entry already exists.",
        })

    return {
        "direction": "entry",
        "identity_type": identity_type,
        "identity_value": identity_value,
    }


def _update_log_request_data(log, additions):
    request_data = _normalize_request_data({"request_data": log.request_data})
    if not isinstance(request_data, dict):
        request_data = {}
    request_data.update(additions)
    log.request_data = request_data
    log.save(update_fields=["request_data"])


def _process_anti_passback_post_save(log, anti_passback_context):
    if log.result != "granted":
        return
    if not isinstance(anti_passback_context, dict) or not anti_passback_context:
        return

    if anti_passback_context.get("manual_override"):
        _update_log_request_data(
            log,
            {
                "anti_passback_status": "OVERRIDE_ALLOWED",
                "anti_passback_overridden_at": timezone.now().isoformat(),
                "anti_passback_override_comment": anti_passback_context.get("override_comment", ""),
                "anti_passback_identity_type": anti_passback_context.get("identity_type", ""),
                "anti_passback_identity_value": anti_passback_context.get("identity_value", ""),
            },
        )
        return

    if anti_passback_context.get("direction") != "exit":
        return

    open_entry_ids = anti_passback_context.get("open_entry_ids") or []
    if not open_entry_ids:
        return

    now_iso = timezone.now().isoformat()
    entries_to_close = AccessLog.objects.filter(id__in=open_entry_ids)
    for entry in entries_to_close:
        _update_log_request_data(
            entry,
            {
                "anti_passback_status": "CLOSED_BY_EXIT",
                "anti_passback_closed_by_exit_id": str(log.id),
                "anti_passback_closed_at": now_iso,
            },
        )

    _update_log_request_data(
        log,
        {
            "anti_passback_status": "EXIT_ALLOWED",
            "anti_passback_closed_entry_ids": [str(entry.id) for entry in entries_to_close],
            "anti_passback_identity_type": anti_passback_context.get("identity_type", ""),
            "anti_passback_identity_value": anti_passback_context.get("identity_value", ""),
        },
    )


def _get_preclearance_rule(pin_value, active_only=True):
    if not pin_value:
        return None
    qs = ScheduleRule.objects.filter(pin=pin_value, schedule_kind="preclearance")
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.order_by("-valid_from").first()


def _mark_preclearance_entry_used(pin_value):
    rule = _get_preclearance_rule(pin_value)
    if not rule or rule.preclearance_entry_used:
        return
    rule.preclearance_entry_used = True
    rule.save(update_fields=["preclearance_entry_used"])


def _send_preclearance_pin_sms(rule):
    if not should_send_visitor_sms("preclearance_entry_pin"):
        return

    phone = normalize_phone(rule.visitor_mobile)
    if not phone:
        logger.info("Skipping PIN SMS for preclearance rule %s: visitor mobile missing", rule.id)
        return

    site_name = ""
    if rule.unit and getattr(rule.unit, "property", None) and getattr(rule.unit.property, "site", None):
        site_name = rule.unit.property.site.name or ""
    if not site_name:
        site_name = "this site"
    expiry_date = rule.valid_until.isoformat() if rule.valid_until else "N/A"
    message = (
        f"Temporary pin {rule.pin} valid for 1 Entry and Exit to visit "
        f"{site_name} valid until {expiry_date}."
    )
    try:
        send_sms(
            phone,
            message,
            context={
                "trigger": "preclearance_entry_pin",
                "unit": rule.unit,
                "person": rule.visitor,
                "visitor_name": rule.visitor_full_name,
                "visitor_phone": rule.visitor_mobile,
                "recipient_name": rule.visitor_full_name,
                "schedule_rule": rule,
                "context_data": {
                    "schedule_rule_id": str(rule.id),
                    "schedule_kind": rule.schedule_kind,
                    "pin": rule.pin,
                },
            },
        )
    except Exception as exc:
        logger.warning("Failed to send PIN SMS for preclearance rule %s: %s", rule.id, exc)


def _extract_phone_value(request_data, components):
    if isinstance(request_data, dict):
        for key in ("phone", "mobile", "phone_number", "visitor_mobile"):
            value = request_data.get(key)
            if value:
                text = str(value).strip()
                if text:
                    return text
    for comp in components:
        comp_type = str(comp.get("type") or "").lower()
        label = str(comp.get("label") or comp.get("title") or "").lower()
        comp_id = str(comp.get("id") or "").lower()
        if not any(token in f"{comp_type} {label} {comp_id}" for token in ("phone", "mobile")):
            continue
        value = comp.get("value")
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _extract_visitor_name(request_data, components):
    if isinstance(request_data, dict):
        for key in ("full_name", "visitor_full_name", "name"):
            value = request_data.get(key)
            if value:
                text = str(value).strip()
                if text:
                    return text
    for comp in components:
        comp_type = str(comp.get("type") or "").lower()
        label = str(comp.get("label") or comp.get("title") or "").lower()
        comp_id = str(comp.get("id") or "").lower()
        if not any(token in f"{comp_type} {label} {comp_id}" for token in ("name", "full_name")):
            continue
        value = comp.get("value")
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _extract_country_hint(request_data, components):
    if isinstance(request_data, dict):
        for key in ("country_iso", "country_code", "country_dial_code"):
            value = request_data.get(key)
            if value:
                text = str(value).strip()
                if text:
                    return text
        device_info = request_data.get("device_info")
        if isinstance(device_info, dict):
            for key in ("country_iso", "country_code", "country_dial_code", "locale_country", "network_country_iso", "sim_country_iso"):
                value = device_info.get(key)
                if value:
                    text = str(value).strip()
                    if text:
                        return text
    for comp in components:
        payload = f"{str(comp.get('type') or '').lower()} {str(comp.get('label') or '').lower()} {str(comp.get('id') or '').lower()}"
        if "country" not in payload:
            continue
        value = comp.get("value")
        if value:
            text = str(value).strip()
            if text:
                return text
    return ""


def _resolve_site_name(access_log_instance, rule=None):
    if rule and rule.unit and getattr(rule.unit, "property", None) and getattr(rule.unit.property, "site", None):
        name = rule.unit.property.site.name or ""
        if name:
            return name
    point = getattr(access_log_instance, "access_point", None)
    if point and getattr(point, "property", None) and getattr(point.property, "site", None):
        name = point.property.site.name or ""
        if name:
            return name
    return "this site"


def _send_entry_workflow_sms(payload, access_log_instance, pin_value, rule=None):
    if not should_send_visitor_sms("entry_workflow_sms"):
        return
    if access_log_instance.result != "granted":
        return

    request_data = _normalize_request_data(payload)
    components = _extract_components(request_data)
    direction = _get_direction_value(components)
    is_exit = (direction == "exit") or (direction is None and _is_exit_event(request_data, components))
    if is_exit:
        return

    country_hint = _extract_country_hint(request_data, components)
    phone_raw = _extract_phone_value(request_data, components) or (rule.visitor_mobile if rule else "")
    phone = normalize_phone(phone_raw, country_hint=country_hint)
    if not phone:
        logger.info("Skipping entry SMS for log %s: visitor phone missing", access_log_instance.id)
        return

    sms_pin = str(pin_value or (rule.pin if rule else "")).strip()
    if not sms_pin:
        logger.info("Skipping entry SMS for log %s: PIN missing", access_log_instance.id)
        return

    access_log_id = str(getattr(access_log_instance, "id", "") or "").strip()
    if access_log_id and SMSDeliveryLog.objects.filter(
        trigger="entry_workflow_sms",
        context_data__access_log_id=access_log_id,
    ).exists():
        logger.info("Skipping duplicate entry SMS for access_log_id %s", access_log_id)
        return

    visitor_name = _extract_visitor_name(request_data, components) or (rule.visitor_full_name if rule else "")
    site_name = _resolve_site_name(access_log_instance, rule=rule)
    expiry_date = (
        rule.valid_until.isoformat()
        if rule and rule.valid_until
        else timezone.now().date().isoformat()
    )
    message = (
        f"Temporary pin {sms_pin} valid for 1 Entry and Exit to visit "
        f"{site_name} valid until {expiry_date}."
    )

    try:
        point = getattr(access_log_instance, "access_point", None)
        send_sms(
            phone,
            message,
            context={
                "trigger": "entry_workflow_sms",
                "unit": (rule.unit if rule and rule.unit else (point.unit if point else None)),
                "person": (rule.visitor if rule and rule.visitor else access_log_instance.person),
                "visitor_name": visitor_name,
                "visitor_phone": phone_raw,
                "recipient_name": visitor_name,
                "schedule_rule": rule,
                "context_data": {
                    "access_log_id": str(access_log_instance.id),
                    "session_id": str(getattr(access_log_instance, "session_id", "") or ""),
                    "schedule_rule_id": str(rule.id) if rule else "",
                    "pin": sms_pin,
                    "direction": "entry",
                },
            },
        )
    except Exception as exc:
        logger.warning("Failed to send entry workflow SMS for log %s: %s", access_log_instance.id, exc)


def _validate_preclearance_pin_usage(payload):
    request_data = _normalize_request_data(payload)
    components = _extract_components(request_data)
    pin_value = _extract_pin_value(components)
    if not pin_value:
        return
    rule = _get_preclearance_rule(pin_value)
    if not rule:
        return
    direction = _get_direction_value(components)
    is_exit = (direction == "exit") or (direction is None and _is_exit_event(request_data, components))
    if is_exit:
        return
    if rule.preclearance_entry_used:
        raise serializers.ValidationError({"pin": ["Preclearance PIN already used for entry"]})

def _expire_preclearance_pin(pin_value):
    trimmed = (pin_value or "").strip()
    if not trimmed:
        return
    rule = _get_preclearance_rule(trimmed)
    if not rule:
        return
    now_date = timezone.now().date()
    rule.is_active = False
    rule.valid_until = now_date
    rule.preclearance_entry_used = True
    rule.save(update_fields=["is_active", "valid_until", "preclearance_entry_used"])

def _process_preclearance_pin_use(payload, access_log_instance):
    if access_log_instance.result != "granted":
        return
    request_data = _normalize_request_data(payload)
    components = _extract_components(request_data)
    if not components:
        return
    direction = _get_direction_value(components)
    is_exit = (direction == "exit") or (direction is None and _is_exit_event(request_data, components))
    pin_value = _extract_pin_value(components)
    rule = _get_preclearance_rule(pin_value) if pin_value else None
    _send_entry_workflow_sms(payload, access_log_instance, pin_value, rule=rule)
    if pin_value and rule:
        if is_exit:
            if should_send_visitor_sms("visitor_exitcode"):
                try:
                    phone_raw = _extract_phone_value(request_data, components) or rule.visitor_mobile
                    phone = normalize_phone(phone_raw, country_hint=_extract_country_hint(request_data, components))
                    if phone:
                        site_name = _resolve_site_name(access_log_instance, rule=rule)
                        message = (
                            f"Exit code {pin_value} used at {site_name}. "
                            f"If this was not you, please contact security."
                        )
                        send_sms(
                            phone,
                            message,
                            context={
                                "trigger": "visitor_exitcode",
                                "unit": rule.unit,
                                "person": rule.visitor,
                                "visitor_name": rule.visitor_full_name,
                                "visitor_phone": phone_raw,
                                "recipient_name": rule.visitor_full_name,
                                "schedule_rule": rule,
                                "context_data": {
                                    "access_log_id": str(access_log_instance.id),
                                    "schedule_rule_id": str(rule.id),
                                    "pin": pin_value,
                                    "direction": "exit",
                                },
                            },
                        )
                except Exception as exc:
                    logger.warning("Failed to send exit SMS for preclearance rule %s: %s", rule.id, exc)
            _expire_preclearance_pin(pin_value)
        else:
            _mark_preclearance_entry_used(pin_value)




@api_view(["POST"])
def batch_sync_transactions(request):
    def _flatten_error_message(value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return json.dumps(value, default=str)
        if isinstance(value, list):
            return json.dumps(value, default=str)
        return str(value)

    def _extract_error_code(value):
        # Best-effort: preserve meaningful codes like ANTI_PASSBACK for the Android client.
        try:
            from rest_framework.exceptions import ErrorDetail
        except Exception:
            ErrorDetail = None

        if ErrorDetail is not None and isinstance(value, ErrorDetail):
            try:
                return str(value.code).upper()
            except Exception:
                return None
        if isinstance(value, dict):
            if "code" in value and value.get("code"):
                return str(value.get("code")).upper()
            for v in value.values():
                code = _extract_error_code(v)
                if code:
                    return code
            return None
        if isinstance(value, list):
            for v in value:
                code = _extract_error_code(v)
                if code:
                    return code
            return None
        return None

    def normalize_batch_sync_error(error_value, default_code="SYNC_ERROR"):
        if isinstance(error_value, dict):
            code = error_value.get("code") or _extract_error_code(error_value) or default_code
            message = error_value.get("message") or _flatten_error_message(error_value)
            return {"code": str(code), "message": str(message)}
        if isinstance(error_value, list):
            return {
                "code": default_code,
                "message": _flatten_error_message(error_value),
            }
        return {
            "code": default_code,
            "message": _flatten_error_message(error_value) or "Unknown error",
        }

    payload = request.data
    if isinstance(payload, dict):
        items = payload.get("transactions")
    else:
        items = payload

    if not isinstance(items, list):
        return Response({"error": "Invalid payload format"}, status=400)

    processed = []
    failed = []
    for item in items:
        if not isinstance(item, dict):
            failed.append(
                {
                    "client_id": None,
                    "status": "error",
                    "error": normalize_batch_sync_error("Invalid item", "INVALID_ITEM"),
                }
            )
            continue

        client_id = item.get("client_id") or item.get("clientId")
        data = item.get("payload") or item.get("data") or {}

        if not isinstance(data, dict):
            failed.append(
                {
                    "client_id": client_id,
                    "status": "error",
                    "error": normalize_batch_sync_error("Invalid payload", "INVALID_PAYLOAD"),
                }
            )
            continue

        if client_id:
            client_id_text = str(client_id).strip()
            if client_id_text:
                data = dict(data)
                # Treat client_id as unique transaction id for idempotent sync.
                data["session_id"] = client_id_text
        else:
            client_id_text = ""
        primary_session_id = str(data.get("session_id") or "").strip()
        if primary_session_id and AccessLog.objects.filter(session_id=primary_session_id).exists():
            processed.append(client_id_text or primary_session_id)
            continue

        try:
            _validate_preclearance_pin_usage(data)
            anti_passback_context = _validate_anti_passback(data)
        except serializers.ValidationError as exc:
            # Preserve specific codes (e.g. ANTI_PASSBACK) when DRF provides them.
            code = None
            try:
                codes = exc.get_codes()
                code = _extract_error_code(codes)
            except Exception:
                code = None
            failed.append(
                {
                    "client_id": client_id,
                    "status": "error",
                    "error": normalize_batch_sync_error(exc.detail, code or "VALIDATION_ERROR"),
                }
            )
            continue

        serializer = AccessLogSerializer(data=data)
        if serializer.is_valid():
            extra = _prepare_access_log_extra(data)
            extra["session_id"] = primary_session_id or extra.get("session_id") or str(uuid.uuid4())
            instance = serializer.save(**extra)
            _process_anti_passback_post_save(instance, anti_passback_context)
            _process_preclearance_pin_use(data, instance)
            processed.append(client_id_text or str(instance.id))
        else:
            failed.append(
                {
                    "client_id": client_id,
                    "status": "error",
                    "error": normalize_batch_sync_error(serializer.errors, "SERIALIZER_ERROR"),
                }
            )

    return Response({"processed": processed, "failed": failed})

class BlacklistViewSet(viewsets.ModelViewSet):
    queryset = Blacklist.objects.all()
    serializer_class = BlacklistSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['target_type', 'reason', 'is_active']
    search_fields = ['details']
    ordering_fields = ['blacklisted_from', 'blacklisted_until']

    def perform_create(self, serializer):
        instance = serializer.save()
        mark_device_sync_pending("Blacklist created")
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        mark_device_sync_pending("Blacklist updated")
        return instance

    def perform_destroy(self, instance):
        instance.delete()
        mark_device_sync_pending("Blacklist deleted")

class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description', 'code']
    ordering_fields = ['name', 'created_at']

class UnitGroupMembershipViewSet(viewsets.ModelViewSet):
    queryset = UnitGroupMembership.objects.all()
    serializer_class = UnitGroupMembershipSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['unit', 'group', 'is_active']
    search_fields = ['unit__unit_code', 'group__name']
    ordering_fields = ['joined_at', 'group__name']

class AndroidAppViewSet(viewsets.ModelViewSet):
    queryset = AndroidApp.objects.all()
    serializer_class = AndroidAppSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['group', 'is_active']
    search_fields = ['name', 'device_identifier', 'device_token', 'device_model']
    ordering_fields = ['name', 'last_seen', 'created_at']

class GroupAccessPermissionViewSet(viewsets.ModelViewSet):
    queryset = GroupAccessPermission.objects.all()
    serializer_class = GroupAccessPermissionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['group', 'access_point', 'is_active']
    search_fields = ['group__name', 'access_point__name']
    ordering_fields = ['priority', 'valid_from', 'valid_until']


# API endpoint for Android devices to fetch active schedule rules with PINs
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny

@api_view(['GET'])
@authentication_classes([])  # Skip auth so invalid/stale token does not cause 403
@permission_classes([AllowAny])
def android_active_pins(request):
    pins = []
    # Schedule rules with PIN (preclearance etc.) — system preclearance labeled "system"
    rules = ScheduleRule.objects.filter(is_active=True).exclude(pin="").select_related()
    for rule in rules:
        d = {
            'id': rule.id,
            'name': rule.name,
            'pin': str(rule.pin or '').strip(),
            'valid_from': rule.valid_from.isoformat() if rule.valid_from else None,
            'valid_until': rule.valid_until.isoformat() if rule.valid_until else None,
            'valid_to': rule.valid_until.isoformat() if rule.valid_until else None,
            'visitor_full_name': rule.visitor_full_name,
            'visitor_mobile': rule.visitor_mobile,
            'schedule_kind': getattr(rule, 'schedule_kind', None) or 'schedule',
        }
        pins.append(d)
    # VoIP (voice clearance) pins: label "voiceclearance" and attach resident who approved
    try:
        from voip.models import VoipCall
        from datetime import timedelta
        from GateCore.models import Person
        since = timezone.now() - timedelta(hours=24)
        voip_calls = VoipCall.objects.exclude(pin="").filter(
            created_at__gte=since
        ).order_by('-created_at')[:100]
        for call in voip_calls:
            if not call.pin or not call.pin.strip():
                continue
            created = call.created_at or timezone.now()
            valid_from = created.date().isoformat()
            valid_to = (created + timedelta(hours=24)).date().isoformat()
            resident_name = None
            try:
                person = Person.objects.filter(id=call.resident_id).first()
                if person:
                    resident_name = getattr(person, 'full_name', None) or str(person)
            except Exception:
                pass
            pins.append({
                'id': str(call.id),
                'name': 'voiceclearance',
                'pin': str(call.pin or '').strip(),
                'valid_from': valid_from,
                'valid_until': valid_to,
                'valid_to': valid_to,
                'visitor_full_name': None,
                'visitor_mobile': None,
                'schedule_kind': 'voice_clearance',
                'resident': (call.resident_id or '').strip() or None,
                'resident_name': resident_name,
            })
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("android_active_pins: include VoIP pins failed: %s", e)
    return Response({'pins': pins})

# Health Check
@api_view(['GET'])
def health_check(request):
    return Response({'status': 'ok'})
class PreclearanceQrRequestSerializer(serializers.Serializer):
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all(), required=False, allow_null=True)
    visitor_full_name = serializers.CharField(required=False, allow_blank=True)
    visitor_mobile = serializers.CharField(required=False, allow_blank=True)
    visitor_email = serializers.EmailField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
