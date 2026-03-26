import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("face_devices", "0008_alter_facedeviceaction_action"),
        ("GateCore", "0032_visitorfaceaccessgrant"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FaceDeviceRemoteChallenge",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.IntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("nonce", models.CharField(max_length=120, unique=True)),
                ("device_identifier", models.CharField(db_index=True, max_length=200)),
                ("status", models.CharField(choices=[("active", "Active"), ("consumed", "Consumed"), ("expired", "Expired"), ("revoked", "Revoked")], db_index=True, default="active", max_length=20)),
                ("estate_id", models.CharField(blank=True, max_length=40)),
                ("platform_id", models.CharField(blank=True, max_length=40)),
                ("estate_name", models.CharField(blank=True, max_length=255)),
                ("challenge_payload", models.JSONField(blank=True, default=dict)),
                ("issued_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="facedeviceremotechallenge_created", to=settings.AUTH_USER_MODEL)),
                ("modified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="facedeviceremotechallenge_modified", to=settings.AUTH_USER_MODEL)),
                ("consumed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="face_device_remote_challenges_consumed", to=settings.AUTH_USER_MODEL)),
                ("terminal", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="face_device_remote_challenges", to="GateCore.gateterminal")),
            ],
            options={
                "ordering": ["-issued_at", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="facedeviceremotechallenge",
            index=models.Index(fields=["device_identifier", "status"], name="face_device_device__9689e1_idx"),
        ),
        migrations.AddIndex(
            model_name="facedeviceremotechallenge",
            index=models.Index(fields=["status", "expires_at"], name="face_device_status_e6d080_idx"),
        ),
    ]
