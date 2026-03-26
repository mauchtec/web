from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GateCore", "0026_person_photo_review_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="photo_review_attempt",
            field=models.ImageField(blank=True, null=True, upload_to="people/photo_reviews/"),
        ),
    ]
