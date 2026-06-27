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
    path('master/roles/<int:pk>/update/', views.update_member_role_view, name='update_member_role'),
    path('master/categories/add/', views.add_inflow_category_view, name='add_inflow_category'),
    path('master/resets/<int:pk>/approve/', views.approve_pin_reset_view, name='approve_pin_reset'),
    path('approvals/', views.approval_center_view, name='approval_center'),
    path('approvals/<uuid:pk>/approve/', views.approve_contribution_view, name='approve_contribution'),
    path('approvals/<uuid:pk>/reject/', views.reject_contribution_view, name='reject_contribution'),
    path('live-entry/', views.live_entry_view, name='live_entry'),
    path('login/', views.admin_login_view, name='admin_login'),
    path('api/transactions/', views.AdminTransactionListAPIView.as_view(), name='admin_transaction_list'),
    path('api/transactions/<uuid:pk>/action/', views.ContributionActionAPIView.as_view(), name='contribution_action'),
    path('api/transactions/<uuid:pk>/requery/', views.RequeryPaystackTransactionView.as_view(), name='requery_paystack'),
    path('master/send-announcement/', views.send_announcement_view, name='send_announcement'),
    path('master/categories/<int:pk>/edit/', views.edit_inflow_category_view, name='edit_inflow_category'),
    path('master/categories/<int:pk>/toggle/', views.toggle_inflow_category_view, name='toggle_inflow_category'),
    path('master/parishioners/import/', views.import_parishioners_view, name='import_parishioners'),
    path('api/webpush/save/', views.save_push_subscription_view, name='save_push_subscription'),
]
