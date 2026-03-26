from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("face_devices", "0007_facedevicestrangerevent_and_more"),
    ]

    operations = [
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
                    ("open_door", "Open Door"),
                    ("reboot", "Reboot Device"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
    ]
