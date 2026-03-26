from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GateCore", "0013_person_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="device_identifier",
            field=models.CharField(blank=True, max_length=200, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="person",
            name="device_name",
            field=models.CharField(blank=True, max_length=200, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="person",
            name="device_model",
            field=models.CharField(blank=True, max_length=200, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="person",
            name="device_serial_number",
            field=models.CharField(blank=True, max_length=200, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="person",
            name="device_os",
            field=models.CharField(blank=True, max_length=50, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="person",
            name="device_app_version",
            field=models.CharField(blank=True, max_length=50, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="person",
            name="device_info",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
