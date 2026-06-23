import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cgscc_cyon.settings")
django.setup()

from django.contrib.auth import get_user_model
from contributions.models import Parishioner, Contribution
from rest_framework.test import APIClient

User = get_user_model()

# Create user
user, created = User.objects.get_or_create(identifier='testuser', defaults={'name': 'Test User'})
if created:
    user.set_password('password')
    user.save()

# Create some dummy data (more than 5 to test the limit)
for i in range(7):
    Parishioner.objects.get_or_create(name=f'xyz_parishioner_{i}')
for i in range(7):
    Contribution.objects.get_or_create(name=f'xyz_contribution_{i}', amount=10.00)

client = APIClient()

# Unauthenticated request
response = client.get('/api/names/search/?q=xyz')
print("Unauthenticated status:", response.status_code)

# Authenticated request
client.force_authenticate(user=user)
response = client.get('/api/names/search/?q=xyz')
print("Authenticated status:", response.status_code)
print("Returned items count:", len(response.data))
print("Returned items:", response.data)
