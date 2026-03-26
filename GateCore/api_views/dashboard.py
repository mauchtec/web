from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from GateCore.models import AccessPoint, Person, Property, Site, Unit, Vehicle


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    cards = [
        {
            "key": "sites",
            "label": "Sites",
            "count": Site.objects.count(),
            "description": "Total managed sites/estates",
            "icon": "building",
            "href": "/gatecore/sites/",
        },
        {
            "key": "properties",
            "label": "Properties",
            "count": Property.objects.count(),
            "description": "Properties across all sites",
            "icon": "city",
            "href": "/gatecore/properties/",
        },
        {
            "key": "units",
            "label": "Units",
            "count": Unit.objects.count(),
            "description": "Units (apartments, offices, etc.)",
            "icon": "door-open",
            "href": "/gatecore/units/",
        },
        {
            "key": "people",
            "label": "People",
            "count": Person.objects.count(),
            "description": "Registered residents, staff, guests",
            "icon": "users",
            "href": "/gatecore/people/",
        },
        {
            "key": "vehicles",
            "label": "Vehicles",
            "count": Vehicle.objects.count(),
            "description": "Registered vehicles",
            "icon": "car",
            "href": "/gatecore/vehicles/",
        },
        {
            "key": "access",
            "label": "Access",
            "count": AccessPoint.objects.count(),
            "description": "Access points/devices",
            "icon": "key",
            "href": "/gatecore/access-points/",
        },
    ]

    return Response(
        {
            "generated_at": None,
            "cards": cards,
            "totals": {
                "sites": cards[0]["count"],
                "properties": cards[1]["count"],
                "units": cards[2]["count"],
                "people": cards[3]["count"],
                "vehicles": cards[4]["count"],
                "access_points": cards[5]["count"],
            },
        }
    )
