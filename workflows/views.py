from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from .components import get_all_html_component_templates, generate_workflow_preview, HTML_EXAMPLE_WORKFLOWS

from .models import Workflow
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
import json
from django.views.decorators.csrf import csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def save_workflow(request):
	"""Save a workflow definition (JSON) to the database."""
	data = request.data
	name = data.get("name")
	description = data.get("description", "")
	version = data.get("version", "1.0.0")
	status_val = data.get("status", "draft")
	definition = data.get("definition")
	if not name or not isinstance(definition, dict):
		return Response({"error": "Missing name or invalid definition."}, status=400)
	workflow = Workflow.objects.create(
		name=name,
		description=description,
		version=version,
		status=status_val,
		definition=definition
	)
	return Response({"id": str(workflow.id), "message": "Workflow saved."})

@api_view(["GET", "PUT", "DELETE", "POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def get_workflow(request, workflow_id):
	"""Retrieve, update, delete, or publish a workflow by ID."""
	try:
		workflow = Workflow.objects.get(id=workflow_id)
	except Workflow.DoesNotExist:
		return Response({"error": "Workflow not found."}, status=404)

	if request.method == "GET":
		return Response({
			"id": str(workflow.id),
			"name": workflow.name,
			"description": workflow.description,
			"version": workflow.version,
			"status": workflow.status,
			"definition": workflow.definition,
			"created_at": workflow.created_at,
			"updated_at": workflow.updated_at
		})
	elif request.method == "PUT":
		data = request.data
		workflow.name = data.get("name", workflow.name)
		workflow.description = data.get("description", workflow.description)
		workflow.version = data.get("version", workflow.version)
		workflow.status = data.get("status", workflow.status)
		if "definition" in data:
			workflow.definition = data["definition"]
		workflow.save()
		return Response({"id": str(workflow.id), "message": "Workflow updated."})
	elif request.method == "DELETE":
		workflow.delete()
		return Response({"message": "Workflow deleted."})
	elif request.method == "POST":
		# Publish action
		action = request.data.get("action")
		if action == "publish":
			workflow.status = "published"
			workflow.save()
			return Response({"id": str(workflow.id), "message": "Workflow published."})
		return Response({"error": "Unknown action."}, status=400)

@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def list_components(request):
	"""List all available HTML workflow components."""
	return JsonResponse({"components": get_all_html_component_templates()})

@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def preview_workflow(request):
	"""Generate HTML preview for a workflow from posted components."""
	components = request.data.get("components")
	if not isinstance(components, list):
		return JsonResponse({
			"html": "<div style='color:#b91c1c;padding:24px;text-align:center;'>No valid workflow components found.<br>\nPlease ensure your workflow definition contains a <b>components</b> list.</div>"
		})
	html = generate_workflow_preview(components)
	return JsonResponse({"html": html})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def example_workflow(request, key):
	"""Return an example workflow JSON by key."""
	wf = HTML_EXAMPLE_WORKFLOWS.get(key)
	if not wf:
		return HttpResponseBadRequest("No such example workflow.")
	return JsonResponse(wf)
