from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('hub/', views.member_hub_view, name='member_hub'),
    path('flyer/', views.generate_flyer_view, name='flyer'),
    path('qr-code/', views.generate_qr_code_view, name='qr_code'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('master/', views.master_dashboard_view, name='master_dashboard'),
    path('master/export/', views.export_csv_view, name='export_csv'),
    path('approvals/', views.approval_center_view, name='approval_center'),
    path('approvals/<uuid:pk>/approve/', views.approve_contribution_view, name='approve_contribution'),
    path('approvals/<uuid:pk>/reject/', views.reject_contribution_view, name='reject_contribution'),
    path('live-entry/', views.live_entry_view, name='live_entry'),
]
