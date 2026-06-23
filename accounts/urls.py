from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('forgot-pin/', views.forgot_pin_view, name='forgot_pin'),
    path('onboarding/', views.onboarding_view, name='onboarding'),
    path('logout/', views.logout_view, name='logout'),
    path('settings/', views.settings_view, name='settings'),
    path('api/verify-pin/', views.verify_pin_api, name='api_verify_pin'),
]
