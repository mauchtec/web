import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GateCore", "0023_person_face_enrollment_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeviceSyncJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.IntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("device_identifier", models.CharField(max_length=200, unique=True)),
                ("device_name", models.CharField(blank=True, max_length=200)),
                ("cursor_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failure", "Failure")], default="pending", max_length=20)),
                ("last_error", models.TextField(blank=True)),
                ("last_payload", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["-last_synced_at", "device_identifier"],
            },
        ),
        migrations.AddIndex(
            model_name="devicesyncjob",
            index=models.Index(fields=["device_identifier"], name="GateCore_devic_device_i_3dca81_idx"),
        ),
        migrations.AddIndex(
            model_name="devicesyncjob",
            index=models.Index(fields=["last_status", "last_synced_at"], name="GateCore_devic_last_st_6c5bd2_idx"),
        ),
    ]
