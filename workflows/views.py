from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from .components import get_all_html_component_templates, generate_workflow_preview, HTML_EXAMPLE_WORKFLOWS

from .models import Workflow, WorkflowSubmission
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

@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def submit_workflow_data(request, workflow_id):
	"""Submit workflow execution data (user-entered form data)."""
	try:
		workflow = Workflow.objects.get(id=workflow_id)
	except Workflow.DoesNotExist:
		return Response({"error": "Workflow not found."}, status=404)
	
	submission_data = request.data.get("data")
	if not submission_data or not isinstance(submission_data, dict):
		return Response({"error": "Missing or invalid submission data."}, status=400)
	
	# Create submission record
	submission = WorkflowSubmission.objects.create(
		workflow=workflow,
		submission_data=submission_data,
		submitted_by=request.data.get("submitted_by", ""),
		session_id=request.data.get("session_id", "")
	)
	
	return Response({
		"id": str(submission.id),
		"workflow_id": str(workflow.id),
		"message": "Workflow data submitted successfully.",
		"submitted_at": submission.submitted_at
	}, status=201)

@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def list_workflow_submissions(request, workflow_id):
	"""List all submissions for a specific workflow."""
	try:
		workflow = Workflow.objects.get(id=workflow_id)
	except Workflow.DoesNotExist:
		return Response({"error": "Workflow not found."}, status=404)
	
	submissions = WorkflowSubmission.objects.filter(workflow=workflow)
	
	# Pagination with validation
	try:
		page = int(request.GET.get('page', 1))
		per_page = int(request.GET.get('per_page', 20))
	except (ValueError, TypeError):
		return Response({"error": "Invalid pagination parameters. 'page' and 'per_page' must be integers."}, status=400)
	
	# Validate pagination bounds
	if page < 1:
		return Response({"error": "Page number must be >= 1."}, status=400)
	if per_page < 1 or per_page > 100:
		return Response({"error": "Per page must be between 1 and 100."}, status=400)
	
	start_idx = (page - 1) * per_page
	end_idx = start_idx + per_page
	
	total_count = submissions.count()
	submissions_page = submissions[start_idx:end_idx]
	
	results = [{
		"id": str(sub.id),
		"submission_data": sub.submission_data,
		"submitted_at": sub.submitted_at,
		"submitted_by": sub.submitted_by,
		"session_id": sub.session_id
	} for sub in submissions_page]
	
	return Response({
		"workflow_id": str(workflow.id),
		"workflow_name": workflow.name,
		"total_count": total_count,
		"page": page,
		"per_page": per_page,
		"results": results
	})
