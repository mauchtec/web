from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from GateCore.models import Group, GroupAccessPermission

# Function to copy permissions from one group to another
def copy_permissions(source_group_id, target_group_id):
    source_group = get_object_or_404(Group, id=source_group_id)
    target_group = get_object_or_404(Group, id=target_group_id)

    permissions = GroupAccessPermission.objects.filter(group=source_group)
    for permission in permissions:
        GroupAccessPermission.objects.create(
            group=target_group,
            access_point=permission.access_point,
            valid_from=permission.valid_from,
            valid_until=permission.valid_until,
            max_daily_uses=permission.max_daily_uses
        )
    return f"Permissions copied from {source_group.name} to {target_group.name}."

def config_view(request):
    return JsonResponse({"message": "Config endpoint is working"})


def residence_app_openapi_yaml(request):
    schema_path = Path(settings.BASE_DIR) / "docs" / "RESIDENCE_APP_API_OPENAPI.yaml"
    if not schema_path.exists():
        return HttpResponse("Residence app schema not found.", status=404, content_type="text/plain")
    return HttpResponse(schema_path.read_text(encoding="utf-8"), content_type="application/x-yaml")


def residence_app_swagger_ui(request):
    yaml_url = "/swagger/residence-app.yaml"
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Residence App API</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  <style>
    body {{ margin: 0; background: #0f172a; }}
    .topbar {{ display: none; }}
    #swagger-ui {{ background: #fff; min-height: 100vh; }}
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({{
      url: "{yaml_url}",
      dom_id: "#swagger-ui",
      deepLinking: true,
      presets: [SwaggerUIBundle.presets.apis],
      layout: "BaseLayout"
    }});
  </script>
</body>
</html>"""
    return HttpResponse(html, content_type="text/html")
