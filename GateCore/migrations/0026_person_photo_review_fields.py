from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GateCore", "0025_devicesyncjob_audit_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="face_reference_image_id",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="person",
            name="photo_review_status",
            field=models.CharField(
                choices=[
                    ("not_started", "Not Started"),
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="not_started",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="person",
            name="photo_similarity_score",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="person",
            name="photo_reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="person",
            name="photo_review_error",
            field=models.TextField(blank=True),
        ),
    ]
