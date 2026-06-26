"""
PATCH INSTRUCTIONS FOR: dashboard/views.py
==========================================

TWO lines need to change. Both use the same wrong filter.

CHANGE 1 — inside master_dashboard_view() (around line 335):
------------------------------------------------------------
FIND:
    members = Member.objects.filter(is_superuser=False).order_by('name')

REPLACE WITH:
    members = Member.objects.filter(is_active=True).order_by('name')

WHY:
    is_superuser=False excludes ALL accounts created via `createsuperuser`,
    which is typically every account including regular parish members if
    the admin seeded them that way. Filtering by is_active=True instead
    shows every real (non-deactivated) member, which is what the
    Youth Roles tab is supposed to do.

CHANGE 2 — inside debug_members_view() (around line 796):
---------------------------------------------------------
FIND:
    youth_members = Member.objects.filter(is_superuser=False).order_by('name').values(

REPLACE WITH:
    youth_members = Member.objects.filter(is_active=True).order_by('name').values(

    (and update the key name in the JsonResponse from
     'youth_members_shown_in_roles_tab' to 'members_shown_in_roles_tab'
     for clarity, though this is optional)
"""
