from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime, parse_time
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from GateCore.models.access_control import AccessRule


def _serialize_access_rule(rule):
    return {
        "id": rule.id,
        "name": rule.name,
        "group": rule.group or "",
        "location": rule.location,
        "start_time": rule.start_time.isoformat() if rule.start_time else "",
        "end_time": rule.end_time.isoformat() if rule.end_time else "",
        "days_of_week": rule.days_of_week or "",
        "is_active": bool(rule.is_active),
        "temporary": bool(rule.temporary),
        "expires_at": rule.expires_at.isoformat() if rule.expires_at else "",
        "expires_at_display": rule.expires_at.strftime("%Y-%m-%d %H:%M") if rule.expires_at else "",
    }


def _parse_bool(value, default=False):
    if value in (True, "true", "True", "1", 1, "on"):
        return True
    if value in (False, "false", "False", "0", 0, "off"):
        return False
    return default


def _parse_time(value):
    if not value:
        return None
    return parse_time(value) or value


def _parse_datetime(value):
    if not value:
        return None
    return parse_datetime(value) or value


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def accessrules_collection(request):
    if request.method == "GET":
        rules = AccessRule.objects.filter(user=request.user).order_by("name")
        rows = [_serialize_access_rule(rule) for rule in rules]
        return Response({"results": rows, "rows": rows})

    name = (request.data.get("name") or "").strip()
    location = (request.data.get("location") or "").strip()
    if not name or not location:
        return Response({"detail": "Name and location are required."}, status=status.HTTP_400_BAD_REQUEST)

    rule = AccessRule.objects.create(
        user=request.user,
        name=name,
        group=(request.data.get("group") or "").strip() or None,
        location=location,
        start_time=_parse_time(request.data.get("start_time")),
        end_time=_parse_time(request.data.get("end_time")),
        days_of_week=(request.data.get("days_of_week") or "").strip() or None,
        is_active=_parse_bool(request.data.get("is_active", True), default=True),
        temporary=_parse_bool(request.data.get("temporary", False), default=False),
        expires_at=_parse_datetime(request.data.get("expires_at")),
    )
    return Response(_serialize_access_rule(rule), status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def accessrule_detail(request, pk):
    rule = get_object_or_404(AccessRule, pk=pk, user=request.user)

    if request.method == "GET":
        return Response(_serialize_access_rule(rule))

    if request.method == "DELETE":
        rule.delete()
        return Response({"message": "Access Rule deleted."})

    name = (request.data.get("name") or "").strip()
    location = (request.data.get("location") or "").strip()
    if not name or not location:
        return Response({"detail": "Name and location are required."}, status=status.HTTP_400_BAD_REQUEST)

    rule.name = name
    rule.group = (request.data.get("group") or "").strip() or None
    rule.location = location
    rule.start_time = _parse_time(request.data.get("start_time"))
    rule.end_time = _parse_time(request.data.get("end_time"))
    rule.days_of_week = (request.data.get("days_of_week") or "").strip() or None
    rule.is_active = _parse_bool(request.data.get("is_active", False), default=False)
    rule.temporary = _parse_bool(request.data.get("temporary", False), default=False)
    rule.expires_at = _parse_datetime(request.data.get("expires_at"))
    rule.save()
    return Response(_serialize_access_rule(rule))
