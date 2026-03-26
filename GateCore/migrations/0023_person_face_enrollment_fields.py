from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GateCore", "0022_person_access_expires_on"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="face_provider",
            field=models.CharField(blank=True, default="compreface", max_length=30),
        ),
        migrations.AddField(
            model_name="person",
            name="face_subject_id",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="person",
            name="face_enrollment_status",
            field=models.CharField(choices=[("not_started", "Not Started"), ("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("synced", "Synced"), ("disabled", "Disabled")], default="not_started", max_length=20),
        ),
        migrations.AddField(
            model_name="person",
            name="face_enrollment_quality_score",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="person",
            name="face_enrolled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="person",
            name="face_last_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="person",
            name="face_enrollment_error",
            field=models.TextField(blank=True),
        ),
    ]
