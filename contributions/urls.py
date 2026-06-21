from django.urls import path
from . import views

app_name = 'contributions'

urlpatterns = [
    path('', views.landing_page_view, name='landing'),
    path('api/contribute/', views.ContributionCreateAPIView.as_view(), name='api_contribute'),
    path('api/verify-paystack/', views.VerifyPaystackPaymentView.as_view(), name='api_verify_paystack'),
    path('api/names/search/', views.NameSearchAPIView.as_view(), name='api_name_search'),
    path('support/cyon/', views.donation_form_view, name='generic_donation'),
    path('support/<slug:referral_slug>/', views.donation_form_view, name='referral_donation'),
    path('receipt/<uuid:pk>/', views.receipt_view, name='receipt'),
]

