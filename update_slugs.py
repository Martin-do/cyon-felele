import os
import django
from django.utils.crypto import get_random_string

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Member

members = Member.objects.all()
count = 0
for member in members:
    slug = get_random_string(6)
    while Member.objects.filter(referral_slug=slug).exists():
        slug = get_random_string(6)
    member.referral_slug = slug
    member.save(update_fields=['referral_slug'])
    count += 1

print(f"Successfully updated {count} member short links to the new 6-character format!")
