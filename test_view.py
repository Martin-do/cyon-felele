import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from contributions.views import NameSearchAPIView

factory = RequestFactory()
request = factory.get('/api/names/search/?q=jo')
view = NameSearchAPIView.as_view()
response = view(request)

print(f"Status Code: {response.status_code}")
print(f"Data: {response.data}")
