from django.contrib import admin
from .models import VoipCall


@admin.register(VoipCall)
class VoipCallAdmin(admin.ModelAdmin):
    list_display = ['id', 'account', 'destination', 'call_status', 'started_at', 'ended_at', 'created_at']
    list_filter = ['call_status']
    search_fields = ['destination', 'provider_call_id', 'resident_id']
    readonly_fields = ['id', 'provider_call_id', 'created_at', 'updated_at']
