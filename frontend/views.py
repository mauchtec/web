# List all workflows (draft and created)
from workflows.models import Workflow
from django.utils import timezone

def workflow_list(request):
	workflows = Workflow.objects.all().order_by('-created_at')
	return render(request, "frontend/workflow_list.html", {"workflows": workflows, "now": timezone.now()})
from django.shortcuts import render


from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def frontend_index(request):
	"""Serve the main frontend builder page."""
	return render(request, "frontend/builder.html")
