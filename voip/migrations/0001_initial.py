import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VoipCall',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider_call_id', models.CharField(blank=True, max_length=255)),
                ('resident_id', models.UUIDField(blank=True, null=True)),
                ('destination', models.CharField(blank=True, max_length=50)),
                ('pin', models.CharField(blank=True, max_length=20)),
                ('pin_source', models.CharField(blank=True, max_length=50)),
                ('call_status', models.CharField(
                    blank=True,
                    choices=[
                        ('', 'Pending'),
                        ('initiated', 'Initiated'),
                        ('ringing', 'Ringing'),
                        ('answered', 'Answered'),
                        ('completed', 'Completed'),
                        ('failed', 'Failed'),
                        ('busy', 'Busy'),
                        ('no-answer', 'No Answer'),
                        ('cancelled', 'Cancelled'),
                    ],
                    max_length=30,
                )),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('recording_url', models.URLField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='voip_calls',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
