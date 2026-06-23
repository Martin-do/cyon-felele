import uuid
from django.db import models
from django.conf import settings

class HarvestSession(models.Model):
    label = models.CharField(max_length=255, help_text='e.g., "2025 Launching"')
    date = models.DateField()
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.label

from django.utils import timezone

class InflowCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    api_key_name = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. PAYSTACK_SECRET_KEY_LAUNCHING (Leave blank for default)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Parishioner(models.Model):
    SOURCE_CHOICES = (
        ('registry', 'Registry'),
        ('manual', 'Manual'),
    )
    name = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='registry')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class Pledge(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    amount_pledged = models.DecimalField(max_digits=12, decimal_places=2)
    amount_fulfilled = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    inflow_category = models.ForeignKey(InflowCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='pledges')
    note = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.amount_pledged}"

class Contribution(models.Model):
    SOURCE_CHOICES = (
        ('guest_form', 'Guest Form'),
        ('member_hub', 'Member Hub'),
        ('live_log', 'Live Log (Usher)'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=100, blank=True, null=True)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default='guest_form')
    inflow_category = models.ForeignKey(InflowCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='contributions')
    
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='referrals'
    )
    
    recorder_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID or name of the usher who recorded this")
    proof_url = models.URLField(blank=True, null=True)
    receipt_image = models.ImageField(upload_to='receipts/', blank=True, null=True)
    is_anonymous = models.BooleanField(default=False)
    is_voided = models.BooleanField(default=False)
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Idempotency key from the frontend to prevent double-submissions
    idempotency_key = models.UUIDField(unique=True, null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.amount}"
