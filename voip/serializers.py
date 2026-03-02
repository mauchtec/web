from rest_framework import serializers
from .models import VoipCall


class VoipCallSerializer(serializers.ModelSerializer):
    account = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = VoipCall
        fields = [
            'id',
            'account',
            'provider_call_id',
            'resident_id',
            'destination',
            'pin',
            'pin_source',
            'call_status',
            'started_at',
            'ended_at',
            'recording_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'provider_call_id',
            'call_status',
            'started_at',
            'ended_at',
            'recording_url',
            'created_at',
            'updated_at',
        ]
