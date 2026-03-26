from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GateCore", "0014_person_device_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="accesslog",
            name="driver_photo",
            field=models.FileField(blank=True, null=True, upload_to="access_logs/driver/"),
        ),
        migrations.AddField(
            model_name="accesslog",
            name="vehicle_photo",
            field=models.FileField(blank=True, null=True, upload_to="access_logs/vehicle/"),
        ),
    ]

