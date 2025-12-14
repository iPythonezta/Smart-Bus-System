from django.urls import path
from .views import RegisterView, LoginView, UserDetailView, UserListView
from .views_dashboard import DashboardStatsView
from .views_buses import (
    BusListView, BusDetailView, BusLocationView,
    BusStartTripView, BusEndTripView, ActiveBusesView
)
from .views_stops import StopListView, StopDetailView
from .views_routes import (
    RouteListView, RouteDetailView,
    RouteStopsView, RouteStopDetailView, RouteStopsReorderView
)
from .views_advertisements import AdvertisementListView, AdvertisementDetailView
from .views_advertisers import AdvertiserListView, AdvertiserDetailView
from .views_ad_schedules import AdScheduleListView, AdScheduleDetailView
from .views_announcements import AnnouncementListView, AnnouncementDetailView
from .views_displays import (
    DisplayListView, DisplayDetailView, DisplayHeartbeatView, DisplayContentView
)
from .views_etas import StopETAsView, RouteETAsView

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
    
    # Stop endpoints
    path('stops/', StopListView.as_view(), name='stop_list'),
    path('stops/<int:stop_id>/', StopDetailView.as_view(), name='stop_detail'),
    path('stops/<int:stop_id>/etas/', StopETAsView.as_view(), name='stop_etas'),
    
    # Route endpoints
    path('routes/', RouteListView.as_view(), name='route_list'),
    path('routes/<int:route_id>/', RouteDetailView.as_view(), name='route_detail'),
    path('routes/<int:route_id>/stops/', RouteStopsView.as_view(), name='route_stops'),
    path('routes/<int:route_id>/stops/reorder/', RouteStopsReorderView.as_view(), name='route_stops_reorder'),
    path('routes/<int:route_id>/stops/<int:route_stop_id>/', RouteStopDetailView.as_view(), name='route_stop_detail'),
    path('routes/<int:route_id>/etas/', RouteETAsView.as_view(), name='route_etas'),
    
    # Advertiser endpoints (3NF normalization)
    path('advertisers/', AdvertiserListView.as_view(), name='advertiser_list'),
    path('advertisers/<int:advertiser_id>/', AdvertiserDetailView.as_view(), name='advertiser_detail'),
    
    # Advertisement endpoints
    path('advertisements/', AdvertisementListView.as_view(), name='advertisement_list'),
    path('advertisements/<int:ad_id>/', AdvertisementDetailView.as_view(), name='advertisement_detail'),
    
    # Ad Schedule endpoints
    path('ad-schedules/', AdScheduleListView.as_view(), name='ad_schedule_list'),
    path('ad-schedules/<int:schedule_id>/', AdScheduleDetailView.as_view(), name='ad_schedule_detail'),
    
    # Announcement endpoints
    path('announcements/', AnnouncementListView.as_view(), name='announcement_list'),
    path('announcements/<int:announcement_id>/', AnnouncementDetailView.as_view(), name='announcement_detail'),
    
    # Display Unit (SMD) endpoints
    path('displays/', DisplayListView.as_view(), name='display_list'),
    path('displays/<int:display_id>/', DisplayDetailView.as_view(), name='display_detail'),
    path('displays/<int:display_id>/heartbeat/', DisplayHeartbeatView.as_view(), name='display_heartbeat'),
    path('displays/<int:display_id>/content/', DisplayContentView.as_view(), name='display_content'),
]