from django.db import migrations

INITIAL_CATEGORIES = [
    {
        "name": "Main Harvest Contributions",
        "description": "General cash and bank-transfer contributions to the 2026 Harvest.",
        "is_active": True,
        "api_key_name": None,
    },
    {
        "name": "Pledge Redemptions",
        "description": "Payment of pledges made during the harvest campaign.",
        "is_active": True,
        "api_key_name": None,
    },
    {
        "name": "Youth Week Fundraiser",
        "description": "Contributions specifically tagged to the CYON Youth Week programme.",
        "is_active": True,
        "api_key_name": None,
    },
    {
        "name": "Online / Paystack",
        "description": "Contributions received via the Paystack online payment gateway.",
        "is_active": True,
        "api_key_name": "PAYSTACK_SECRET_KEY",
    },
]


def seed_inflow_categories(apps, schema_editor):
    InflowCategory = apps.get_model("contributions", "InflowCategory")
    for data in INITIAL_CATEGORIES:
        InflowCategory.objects.get_or_create(
            name=data["name"],
            defaults={
                "description": data["description"],
                "is_active": data["is_active"],
                "api_key_name": data["api_key_name"],
            },
        )


def reverse_seed(apps, schema_editor):
    InflowCategory = apps.get_model("contributions", "InflowCategory")
    names = [d["name"] for d in INITIAL_CATEGORIES]
    InflowCategory.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("contributions", "0010_inflowcategory_api_key_name"),
    ]

    operations = [
        migrations.RunPython(seed_inflow_categories, reverse_code=reverse_seed),
    ]
