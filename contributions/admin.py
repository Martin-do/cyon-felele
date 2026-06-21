from django.contrib import admin
from .models import Contribution, Pledge, HarvestSession, Parishioner

@admin.register(Parishioner)
class ParishionerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'source', 'created_at')
    list_filter = ('source',)
    search_fields = ('name', 'phone')

@admin.register(HarvestSession)
class HarvestSessionAdmin(admin.ModelAdmin):
    list_display = ('label', 'date', 'is_active')

@admin.register(Pledge)
class PledgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'amount_pledged', 'amount_fulfilled', 'timestamp')
    search_fields = ('name', 'phone')

@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'method', 'source', 'referred_by', 'is_voided', 'timestamp')
    list_filter = ('source', 'is_voided', 'referred_by', 'method')
    search_fields = ('name', 'phone', 'id')
