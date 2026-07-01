from django.db import migrations

def seed_youth_harvest_fundraiser(apps, schema_editor):
    InflowCategory = apps.get_model("contributions", "InflowCategory")
    InflowCategory.objects.get_or_create(
        name="Youth Harvest Fundraiser",
        defaults={
            "description": "Contributions specifically tagged to the CYON Youth Harvest Fundraiser.",
            "is_active": True,
            "api_key_name": None,
        },
    )

def reverse_seed(apps, schema_editor):
    InflowCategory = apps.get_model("contributions", "InflowCategory")
    InflowCategory.objects.filter(name="Youth Harvest Fundraiser").delete()

class Migration(migrations.Migration):

    dependencies = [
        ("contributions", "0012_contribution_pledge_pledge_member_pledge_status"),
    ]

    operations = [
        migrations.RunPython(seed_youth_harvest_fundraiser, reverse_code=reverse_seed),
    ]
