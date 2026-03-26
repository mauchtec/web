from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from GateCore.models import Site


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def site_overview(request):
    if not request.user.is_staff:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    sites = Site.objects.all().order_by("name")
    site_types = [{"value": value, "label": label} for value, label in Site.SITE_TYPES]
    data = []
    for site in sites:
        data.append(
            {
                "id": str(site.id),
                "name": site.name,
                "site_type": site.site_type,
                "type_display": site.get_site_type_display(),
                "location": site.location or "",
                "code": site.code or "",
                "description": site.description or "",
                "is_active": site.is_active,
            }
        )
    return Response({"sites": data, "rows": data, "site_type_options": site_types})
