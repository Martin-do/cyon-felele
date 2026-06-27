from django.conf import settings

def vapid_settings(request):
    return {
        'WEBPUSH_VAPID_PUBLIC_KEY': getattr(settings, 'WEBPUSH_VAPID_PUBLIC_KEY', '')
    }
