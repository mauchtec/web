from django.contrib import admin
from .models import Workflow, WorkflowSubmission

@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')

@admin.register(WorkflowSubmission)
class WorkflowSubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'workflow', 'submitted_at', 'submitted_by')
    list_filter = ('submitted_at', 'workflow')
    search_fields = ('submitted_by', 'session_id')
    readonly_fields = ('id', 'submitted_at')
    raw_id_fields = ('workflow',)
