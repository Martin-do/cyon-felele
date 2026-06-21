from django.contrib import admin
from .models import Member

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'identifier', 'referral_slug', 'levy_amount', 'levy_paid', 'is_staff')
    search_fields = ('name', 'identifier', 'referral_slug')
