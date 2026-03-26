from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GateCore", "0007_accesslog_barcode_hex_accesslog_raw_scan_data_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="schedulerule",
            name="preclearance_entry_used",
            field=models.BooleanField(default=False),
        ),
    ]
