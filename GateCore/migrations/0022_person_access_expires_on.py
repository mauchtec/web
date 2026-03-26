from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GateCore", "0021_runtimesettings_anti_passback_allow_manual_override_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="access_expires_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]
