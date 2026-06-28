import os
import sys

# Setup Django environment
sys.path.append(r"c:\Users\USER\Documents\python_codes\cgscc_cyon")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.test import RequestFactory
from accounts.models import Member
from dashboard.views import leaderboard_view

# Retrieve a real mock member
member = Member.objects.get(id=3) # Martin Jaiyeola

# Create a mock request
factory = RequestFactory()
request = factory.get('/dashboard/leaderboard/')
request.META['HTTP_HOST'] = '127.0.0.1:8000'
request.is_secure = lambda: False
request.user = member # Attach the logged-in contestant

print(f"Rendering leaderboard view as logged-in user: {member.name}...")
try:
    response = leaderboard_view(request)
    html = response.content.decode('utf-8')
    
    # Assert key components exist
    assert "Campaign Leaderboard" in html, "Leaderboard title not found"
    assert "is-me" in html, "is-me CSS highlight class not found"
    assert "ME" in html, "ME badge/label not found in HTML"
    
    print("Success! Leaderboard view renders perfectly for logged-in contestant, with is-me highlights.")
except Exception as e:
    import traceback
    print(f"Failed to render leaderboard: {str(e)}")
    traceback.print_exc()
