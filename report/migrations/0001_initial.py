# Generated migration for DashboardMetrics model

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardMetrics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_users', models.IntegerField(default=0)),
                ('todos_new', models.IntegerField(default=0)),
                ('todos_completed', models.IntegerField(default=0)),
                ('todos_deleted', models.IntegerField(default=0)),
                ('total_todos', models.IntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'Dashboard Metrics',
            },
        ),
        migrations.CreateModel(
            name='OrchestrationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flow_name', models.CharField(choices=[('DASHBOARD_AGGREGATION', 'Dashboard Aggregation'), ('RECURRING_TODO', 'Recurring Todo Processing'), ('TENANT_REGISTRATION', 'Tenant Registration')], max_length=50)),
                ('status', models.CharField(choices=[('STARTED', 'Started'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')], max_length=20)),
                ('flow_run_id', models.CharField(blank=True, max_length=100, null=True)),
                ('triggered_by', models.CharField(blank=True, max_length=100, null=True)),
                ('details', models.JSONField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('started_at', models.DateTimeField()),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-started_at'],
            },
        ),
        migrations.AddIndex(
            model_name='orchestrationlog',
            index=models.Index(fields=['flow_name'], name='report_orch_flow_na_6ccc89_idx'),
        ),
        migrations.AddIndex(
            model_name='orchestrationlog',
            index=models.Index(fields=['started_at'], name='report_orch_started_88a845_idx'),
        ),
    ]
