from django.urls import path
from .views import RegisterView, LoginView, UserDetailView, UserListView
from .views_dashboard import DashboardStatsView
from .views_buses import (
    BusListView, BusDetailView, BusLocationView,
    BusStartTripView, BusEndTripView, ActiveBusesView
)

urlpatterns = [
    # Auth endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('me/', UserDetailView.as_view(), name='user_detail'),
    path('users/', UserListView.as_view(), name='user_list'),
    
    # Dashboard endpoints
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),
    
    # Bus endpoints
    path('buses/', BusListView.as_view(), name='bus_list'),
    path('buses/active/', ActiveBusesView.as_view(), name='active_buses'),
    path('buses/<int:bus_id>/', BusDetailView.as_view(), name='bus_detail'),
    path('buses/<int:bus_id>/location/', BusLocationView.as_view(), name='bus_location'),
    path('buses/<int:bus_id>/start-trip/', BusStartTripView.as_view(), name='bus_start_trip'),
    path('buses/<int:bus_id>/end-trip/', BusEndTripView.as_view(), name='bus_end_trip'),
]