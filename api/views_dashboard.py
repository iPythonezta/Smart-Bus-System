"""
Dashboard API views using raw SQL queries.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one


class DashboardStatsView(APIView):
    """
    GET /api/dashboard/stats/
    Returns all dashboard statistics in a single call.
    """
    
    def get(self, request):
        # Get bus counts by status
        bus_stats = execute_query("""
            SELECT status, COUNT(*) as count 
            FROM buses 
            GROUP BY status
        """)
        
        # Convert to dict for easy access
        bus_counts = {row['status']: row['count'] for row in bus_stats}
        total_buses = sum(bus_counts.values())
        
        # Get total routes
        routes_result = execute_query_one("""
            SELECT COUNT(*) as total FROM routes
        """)
        total_routes = routes_result['total'] if routes_result else 0
        
        # Get active stops count
        stops_result = execute_query_one("""
            SELECT COUNT(*) as total FROM stops WHERE is_active = TRUE
        """)
        total_stops = stops_result['total'] if stops_result else 0
        
        # Get display units by status
        display_stats = execute_query("""
            SELECT status, COUNT(*) as count 
            FROM display_units 
            GROUP BY status
        """)
        display_counts = {row['status']: row['count'] for row in display_stats}
        
        # Get active announcements count
        announcements_result = execute_query_one("""
            SELECT COUNT(*) as total 
            FROM announcements 
            WHERE NOW() BETWEEN start_time AND end_time
        """)
        active_announcements = announcements_result['total'] if announcements_result else 0
        
        # Get active ads count
        ads_result = execute_query_one("""
            SELECT COUNT(DISTINCT a.ad_id) as total 
            FROM advertisements a
            JOIN ad_schedule s ON a.ad_id = s.ad_id
            WHERE a.is_active = TRUE 
            AND NOW() BETWEEN s.start_time AND s.end_time
        """)
        active_ads = ads_result['total'] if ads_result else 0
        
        return Response({
            'total_buses': total_buses,
            'active_buses': bus_counts.get('active', 0),
            'inactive_buses': bus_counts.get('inactive', 0),
            'maintenance_buses': bus_counts.get('maintenance', 0),
            'total_routes': total_routes,
            'total_stops': total_stops,
            'online_displays': display_counts.get('online', 0),
            'offline_displays': display_counts.get('offline', 0),
            'error_displays': display_counts.get('error', 0),
            'active_announcements': active_announcements,
            'active_ads': active_ads
        }, status=status.HTTP_200_OK)
