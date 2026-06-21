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
        ('Mr CYON Felele', 'Mr CYON Felele'),
        ('Miss CYON Felele', 'Miss CYON Felele'),
        ('None', 'Not Contesting'),
    )

    identifier = models.CharField(max_length=150, unique=True, help_text="Phone number or Email")
    name = models.CharField(max_length=255)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    contestant_title = models.CharField(max_length=50, choices=TITLE_CHOICES, default='None')
    referral_slug = models.SlugField(max_length=150, unique=True, blank=True)
    levy_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    levy_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    has_completed_onboarding = models.BooleanField(default=False)
    
    objects = MemberManager()

    USERNAME_FIELD = 'identifier'
    REQUIRED_FIELDS = ['name']

    def save(self, *args, **kwargs):
        if not self.referral_slug and self.name:
            base_slug = slugify(self.name)
            self.referral_slug = f"{base_slug}-{str(uuid.uuid4())[:6]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.identifier})"
