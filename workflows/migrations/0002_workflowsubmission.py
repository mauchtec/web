# Generated migration for WorkflowSubmission model

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('workflows', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkflowSubmission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('submission_data', models.JSONField(help_text='User-entered data from workflow execution')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('submitted_by', models.CharField(blank=True, help_text='Optional user identifier', max_length=255)),
                ('session_id', models.CharField(blank=True, help_text='Optional session tracking', max_length=100)),
                ('workflow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='workflows.workflow')),
            ],
            options={
                'ordering': ['-submitted_at'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowsubmission',
            index=models.Index(fields=['workflow', '-submitted_at'], name='workflows_w_workflo_4e0a54_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowsubmission',
            index=models.Index(fields=['submitted_at'], name='workflows_w_submitt_d8c6d5_idx'),
        ),
    ]
