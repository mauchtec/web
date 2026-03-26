from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("GateCore", "0029_rename_gatecore_devic_device_i_3dca81_idx_gatecore_de_device__8703c1_idx_and_more"),
        ("face_devices", "0006_alter_facedeviceaction_action"),
    ]

    operations = [
        migrations.CreateModel(
            name="FaceDeviceStrangerEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.IntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("event_time", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("status", models.CharField(choices=[("new", "New"), ("reviewed", "Reviewed"), ("dismissed", "Dismissed"), ("promoted", "Promoted To Person")], db_index=True, default="new", max_length=20)),
                ("device_identifier", models.CharField(db_index=True, max_length=200)),
                ("source_command", models.CharField(blank=True, db_index=True, max_length=120)),
                ("confidence", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("liveness_score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("credential_type", models.CharField(blank=True, db_index=True, max_length=40)),
                ("credential_value", models.CharField(blank=True, db_index=True, max_length=200)),
                ("face_group_name", models.CharField(blank=True, max_length=120)),
                ("snapshot_image", models.ImageField(blank=True, null=True, upload_to="face_devices/strangers/snapshots/")),
                ("panoramic_image", models.ImageField(blank=True, null=True, upload_to="face_devices/strangers/panoramic/")),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("remote_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_notes", models.TextField(blank=True)),
                ("access_log", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stranger_event", to="face_devices.facedeviceaccesslog")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="facedevicestrangerevent_created", to=settings.AUTH_USER_MODEL)),
                ("modified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="facedevicestrangerevent_modified", to=settings.AUTH_USER_MODEL)),
                ("promoted_person", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="promoted_face_device_stranger_events", to="GateCore.person")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_face_device_stranger_events", to=settings.AUTH_USER_MODEL)),
                ("terminal", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="face_device_stranger_events", to="GateCore.gateterminal")),
            ],
            options={
                "ordering": ["-event_time", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="facedevicestrangerevent",
            index=models.Index(fields=["device_identifier", "event_time"], name="face_device_device__stranger_evt_idx"),
        ),
        migrations.AddIndex(
            model_name="facedevicestrangerevent",
            index=models.Index(fields=["status", "event_time"], name="face_device_status__stranger_evt_idx"),
        ),
        migrations.AddIndex(
            model_name="facedevicestrangerevent",
            index=models.Index(fields=["credential_type", "credential_value"], name="face_device_credent_stranger_evt_idx"),
        ),
        migrations.AlterField(
            model_name="facedeviceaction",
            name="action",
            field=models.CharField(
                choices=[
                    ("ping", "Ping"),
                    ("pull_settings", "Pull Settings"),
                    ("pull_user_count", "Pull User Count"),
                    ("pull_user_ids", "Pull User IDs"),
                    ("pull_groups", "Pull Groups"),
                    ("pull_access_logs", "Pull Access Logs"),
                    ("sync_users", "Sync Users"),
                    ("add_user", "Add User"),
                    ("edit_user", "Edit User"),
                    ("create_group", "Create Group"),
                    ("delete_group", "Delete Group"),
                    ("delete_user", "Delete User"),
                    ("delete_all_users", "Delete All Users"),
                    ("reboot", "Reboot Device"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
    ]
