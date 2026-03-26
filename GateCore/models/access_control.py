from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AccessRule(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    group = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=100)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    days_of_week = models.CharField(max_length=20, null=True, blank=True)  # e.g. 'Mon,Tue,Wed'
    is_active = models.BooleanField(default=True)
    temporary = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.user or self.group}) -> {self.location}"

class AccessEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=20)  # 'granted', 'denied', etc.
    method = models.CharField(max_length=50, null=True, blank=True)  # e.g. 'card', 'pin', 'remote'
    details = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.timestamp}: {self.user} at {self.location} - {self.result}"
