# Generated migration for DashboardMetrics model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('customers', '0003_organization_role_client_keycloak_id_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardMetrics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_users', models.IntegerField(default=0)),
                ('todos_new', models.IntegerField(default=0)),
                ('todos_completed', models.IntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='metrics', to='customers.client')),
            ],
        ),
    ]
