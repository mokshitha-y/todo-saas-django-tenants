# Data migration: ensure every Client has an Organization so they show in Organisation admin

from django.db import migrations


def backfill_organization(apps, schema_editor):
    Client = apps.get_model("customers", "Client")
    Organization = apps.get_model("customers", "Organization")
    for client in Client.objects.filter(organization_id__isnull=True):
        org = Organization.objects.create(
            name=client.name or client.schema_name or "Unnamed",
            description=f"Backfill for tenant {client.schema_name}",
        )
        client.organization_id = org.id
        client.save(update_fields=["organization_id"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0007_add_email_configuration"),
    ]

    operations = [
        migrations.RunPython(backfill_organization, noop),
    ]
