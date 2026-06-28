import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.text import slugify

class MemberManager(BaseUserManager):
    def create_user(self, identifier, password=None, **extra_fields):
        if not identifier:
            raise ValueError('The Identifier (Phone or Email) must be set')
        user = self.model(identifier=identifier, **extra_fields)
        # PIN is stored as the password hash
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, identifier, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(identifier, password, **extra_fields)

class Member(AbstractBaseUser, PermissionsMixin):
    TITLE_CHOICES = (
        ('Most Influential Youth Fundraiser', 'Most Influential Youth Fundraiser'),
        ('Master Harvest', 'Master Harvest'),
        ('Miss Harvest', 'Miss Harvest'),
        ('None', 'Not Contesting'),
    )

    ROLE_CHOICES = (
        ('member', 'Member / Contestant'),
        ('usher', 'Usher / Recorder'),
        ('approver', 'Approver / Auditor'),
        ('admin', 'Admin'),
    )

    identifier = models.CharField(max_length=150, unique=True, help_text="Phone number or Email")
    name = models.CharField(max_length=255)
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    custom_flyer = models.ImageField(upload_to='flyers/', blank=True, null=True, help_text="Optional custom flyer for sharing")
    contestant_title = models.CharField(max_length=50, choices=TITLE_CHOICES, default='None')
    referral_slug = models.SlugField(max_length=150, unique=True, blank=True)
    levy_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    levy_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    has_completed_onboarding = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    
    LOCK_CHOICES = (
        (5, '5 Minutes'),
        (15, '15 Minutes'),
        (60, '60 Minutes'),
    )
    lock_timeout = models.IntegerField(choices=LOCK_CHOICES, default=15)
    is_flyer_locked = models.BooleanField(default=False, help_text="Lock flyer and profile picture modification/regeneration on dashboard")
    
    objects = MemberManager()

    USERNAME_FIELD = 'identifier'
    REQUIRED_FIELDS = ['name']

    @property
    def is_usher(self):
        return self.role == 'usher' or self.role == 'admin' or self.is_superuser

    @property
    def is_approver(self):
        return self.role == 'approver' or self.role == 'admin' or self.is_superuser

    @property
    def is_admin_user(self):
        return self.role == 'admin' or self.is_superuser or self.is_staff

    def save(self, *args, **kwargs):
        if not self.referral_slug and self.name:
            from django.utils.crypto import get_random_string
            slug = get_random_string(6)
            # Ensure no collisions
            while type(self).objects.filter(referral_slug=slug).exists():
                slug = get_random_string(6)
            self.referral_slug = slug
            
        # Compress profile picture if it's a new upload
        if self.profile_picture and getattr(self.profile_picture, '_committed', True) is False:
            from PIL import Image, ImageOps
            from io import BytesIO
            from django.core.files.uploadedfile import InMemoryUploadedFile
            import sys
            
            try:
                img = Image.open(self.profile_picture)
                # Correct orientation if EXIF data is present
                img = ImageOps.exif_transpose(img)
                
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                    
                # Resize if it's huge, keeping aspect ratio
                max_size = (800, 800)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                output = BytesIO()
                # Save as JPEG with 75% quality to significantly reduce file size
                img.save(output, format='JPEG', quality=75, optimize=True)
                output.seek(0)
                
                # Replace the field's file with the compressed version
                file_name = self.profile_picture.name.split('.')[0] + '.jpg'
                self.profile_picture = InMemoryUploadedFile(
                    output, 'ImageField', file_name, 
                    'image/jpeg', len(output.getvalue()), None
                )
            except Exception as e:
                # If compression fails, just continue and save normally
                pass

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.identifier})"


class PinResetRequest(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='pin_resets')
    is_resolved = models.BooleanField(default=False)
    temp_pin = models.CharField(max_length=4, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    @property
    def whatsapp_link(self):
        # Clean phone number (remove +, convert 080... to 23480...)
        phone = self.member.identifier.strip()
        if '@' in phone:
            return None
        
        # Strip spaces and formatting
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        if phone.startswith('+'):
            phone = phone[1:]
        elif phone.startswith('0'):
            phone = '234' + phone[1:]
        
        # Message text
        text = f"Hello {self.member.name}, your CYON Harvest portal PIN has been reset.\n\nYour new temporary PIN is: {self.temp_pin}\n\nPlease log in and update it on your hub profile."
        import urllib.parse
        encoded_text = urllib.parse.quote(text)
        return f"https://wa.me/{phone}?text={encoded_text}"

    def __str__(self):
        return f"Reset request for {self.member.name} ({'Resolved' if self.is_resolved else 'Pending'})"

class AdminToken(models.Model):
    admin = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='generated_tokens')
    token = models.CharField(max_length=6, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"Token by {self.admin.name} ({'Valid' if self.is_valid() else 'Invalid'})"
class WebPushSubscription(models.Model):
    user = models.ForeignKey(Member, on_delete=models.CASCADE, null=True, blank=True, related_name='webpush_subscriptions')
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        username = self.user.name if self.user else "Anonymous Guest"
        return f"Push subscription for {username} ({self.endpoint[:40]}...)"


