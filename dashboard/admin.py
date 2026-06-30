from django.contrib import admin
from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """
    Admin for SiteSettings singleton.
    Redirects 'Add' directly to the single settings row.
    Hides the delete action so the row can never be accidentally removed.
    """
    fieldsets = (
        ('Leaderboard Display', {
            'fields': ('show_kids_leaderboard',),
            'description': (
                'Control which categories appear on the public leaderboard. '
                'When "Show Kids Harvest leaderboard" is OFF, only Youth Ambassadors are shown.'
            ),
        }),
    )

    def has_add_permission(self, request):
        # Only allow adding if no row exists yet (auto-created on first access anyway)
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redirect list view straight to the edit form
        from django.shortcuts import redirect
        obj = SiteSettings.get()
        return redirect(f'/admin/dashboard/sitesettings/{obj.pk}/change/')
