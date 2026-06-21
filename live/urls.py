from django.urls import path
from . import views

app_name = 'live'

urlpatterns = [
    path('board/', views.projector_board_view, name='board'),
]
