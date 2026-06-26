# CYON Harvest Portal — Fix Brief for Agent
> Prepared after running the live debug endpoint at `/dashboard/master/debug-members/`

---

## Debug Output Findings (from live server)

```json
{
  "total_all": 2,
  "total_youth_visible": 1,
  "all_members": [
    {
      "id": 2,
      "name": "admin\t",
      "identifier": "admin_cyon@felele",
      "role": "member",
      "is_superuser": true,
      "is_staff": true,
      "is_active": true
    },
    {
      "id": 1,
      "name": "Martin Jaiyeola",
      "identifier": "martinjaiyeola40@gmail.com",
      "role": "member",
      "is_superuser": false,
      "is_staff": false,
      "is_active": true
    }
  ]
}
```

This reveals **three problems** that must all be fixed.

---

## Problem 1 — Youth Roles: filter excludes the admin account

**What is happening:**
The admin account (`admin\t`, id=2) has `is_superuser=true`. The current query
`Member.objects.filter(is_superuser=False)` **excludes it from the Youth Roles table entirely**.
That means nobody can change the admin account's role from the dashboard.

Additionally, the admin account currently has `role: "member"` — if `is_superuser` is ever
revoked, it will lose all access immediately.

**Fix — `dashboard/views.py`, inside `master_dashboard_view`:**

Find this line (approximately line 335):
```python
members = Member.objects.filter(is_superuser=False).order_by('name')
```
Replace with:
```python
members = Member.objects.filter(is_active=True).order_by('name')
```

Also update the same filter inside `debug_members_view` (approximately line 796):
```python
# FIND:
youth_members = Member.objects.filter(is_superuser=False).order_by('name').values(

# REPLACE WITH:
youth_members = Member.objects.filter(is_active=True).order_by('name').values(
```

**Fix — also update the admin account's role in the database:**

After deploying the view change above, go to the Youth Roles tab in the dashboard.
The `admin\t` account will now appear in the table. Use the role dropdown to change
its role from `Member / Contestant` to `Admin`, then click Update.

This ensures the admin account has `role="admin"` as a safety net independent of
the `is_superuser` flag.

---

## Problem 2 — Inflow Categories: table is completely empty

**What is happening:**
The `InflowCategory` model was added in migration `0009` (22 June 2026) with no
seed data. The table has zero rows on the live server. Additionally, `InflowCategory`
was never registered in `contributions/admin.py`, so it cannot be managed from
Django's `/admin/` panel either.

### Fix A — Register in Django admin

**File: `contributions/admin.py`**

Add the following import and class (everything else in the file stays the same):

```python
# Add InflowCategory to the import line at the top:
from .models import Contribution, Pledge, HarvestSession, Parishioner, InflowCategory

# Add this new class at the bottom of the file:
@admin.register(InflowCategory)
class InflowCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'api_key_name', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
```

### Fix B — Create a data migration to seed initial categories

**Create a new file: `contributions/migrations/0011_seed_inflow_categories.py`**

```python
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
```

---

## Problem 3 — Minor: admin account name has a stray tab character

**What is happening:**
The admin account shows `"name": "admin\t"` — there is a literal tab character in the name.
While not breaking anything, it will look wrong on flyers, leaderboards, and receipts if
this account ever makes contributions.

**Fix:**
In the Django admin at `/admin/accounts/member/2/change/`, correct the `name` field
to `Admin CYON` (or whatever the intended display name is).

---

## Deployment Checklist (in order)

Run these steps on the VPS:

```bash
# 1. Pull latest code (after committing the two file changes above)
git pull

# 2. Run the new migration
cd /path/to/project
python manage.py migrate contributions

# 3. Confirm migration ran
python manage.py showmigrations contributions
# Should show [X] 0011_seed_inflow_categories

# 4. Restart the app server
sudo systemctl restart gunicorn   # or: supervisorctl restart cyon
```

After restarting:

1. Visit `/dashboard/master/` → click **Inflow Categories** tab → 4 default categories
   should appear immediately.

2. Click **Youth Roles** tab → both accounts (`admin\t` and `Martin Jaiyeola`) should
   now appear in the table.

3. Use the Youth Roles dropdown to set `admin\t`'s role to **Admin** and click Update.

4. (Optional) Go to `/admin/accounts/member/2/change/` and fix the name from `admin\t`
   to the correct admin name.

---

## Summary of files changed

| File | Change |
|------|--------|
| `dashboard/views.py` | 2 lines: `is_superuser=False` → `is_active=True` |
| `contributions/admin.py` | Add `InflowCategory` import + `InflowCategoryAdmin` class |
| `contributions/migrations/0011_seed_inflow_categories.py` | **New file** — seeds 4 default categories |

No template changes, no URL changes, no model changes required.
