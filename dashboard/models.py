from django.db import models


class SiteSettings(models.Model):
    """
    Singleton model for site-wide configuration flags.
    Only one row should ever exist (id=1). Manage via Django Admin.
    """
    show_kids_leaderboard = models.BooleanField(
        default=False,
        verbose_name="Show Kids Harvest leaderboard",
        help_text=(
            "Tick this to display the Kids / Children category on the public leaderboard. "
            "Leave unticked to show Youth Ambassadors only (recommended until kids data is available)."
        )
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Site Settings"

    @classmethod
    def get(cls):
        """Return the singleton settings row, creating it if necessary."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
