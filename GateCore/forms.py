from django import forms
from GateCore.models.access_control import AccessRule

class AccessRuleForm(forms.ModelForm):
    class Meta:
        model = AccessRule
        fields = [
            'name', 'user', 'group', 'location', 'start_time', 'end_time',
            'days_of_week', 'is_active', 'temporary', 'expires_at'
        ]
