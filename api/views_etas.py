"""
ETA (Estimated Time of Arrival) API views using raw SQL queries.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula.
    Returns distance in meters.
    """
    R = 6371000  # Earth's radius in meters
    
    lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


class StopETAsView(APIView):
    """
    GET /api/stops/{stop_id}/etas/ - Get ETAs for all buses approaching a stop
    """
    
    def get(self, request, stop_id):
        # Get stop info
        stop = execute_query_one(
            "SELECT stop_id, stop_name, latitude, longitude FROM stops WHERE stop_id = %s",
            [stop_id]
        )
        
        if not stop:
            return Response(
                {'detail': 'Stop not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        stop_lat = float(stop['latitude'])
        stop_lon = float(stop['longitude'])
        
        # Get optional route filter
        route_id_filter = request.query_params.get('route_id')
        
        # Get routes that pass through this stop
        route_sql = """
            SELECT rs.route_id, rs.sequence_number
            FROM route_stops rs
            WHERE rs.stop_id = %s
        """
        route_params = [stop_id]
        
        if route_id_filter:
            route_sql += " AND rs.route_id = %s"
            route_params.append(route_id_filter)
        
        routes_at_stop = execute_query(route_sql, route_params)
        
        if not routes_at_stop:
            return Response({
                'stop': {
                    'id': stop['stop_id'],
                    'name': stop['stop_name']
                },
                'etas': [],
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_200_OK)
        
        route_ids = [r['route_id'] for r in routes_at_stop]
        route_sequences = {r['route_id']: r['sequence_number'] for r in routes_at_stop}
        
        # Get active buses on these routes
        placeholders = ','.join(['%s'] * len(route_ids))
        buses = execute_query(
            f"""
            SELECT 
                b.bus_id, b.registration_number, b.route_id,
                r.route_name, r.route_code, r.color,
                bl.latitude, bl.longitude, bl.speed, bl.current_stop_sequence
            FROM buses b
            JOIN routes r ON b.route_id = r.route_id
            LEFT JOIN bus_locations bl ON b.bus_id = bl.bus_id
            WHERE b.status = 'active' AND b.route_id IN ({placeholders})
            """,
            route_ids
        )
        
        etas = []
        for bus in buses:
            if not bus['latitude'] or not bus['longitude']:
                continue
            
            bus_lat = float(bus['latitude'])
            bus_lon = float(bus['longitude'])
            bus_route_id = bus['route_id']
            
            # Only show buses that haven't passed this stop yet
            stop_sequence = route_sequences.get(bus_route_id, 0)
            bus_sequence = bus['current_stop_sequence'] or 0
            
            if bus_sequence >= stop_sequence:
                continue  # Bus has already passed or is at this stop
            
            # Calculate distance to stop
            distance = calculate_distance(bus_lat, bus_lon, stop_lat, stop_lon)
            
            # Estimate ETA based on speed (or default 25 km/h)
            speed_kmh = float(bus['speed']) if bus['speed'] and float(bus['speed']) > 0 else 25
            eta_minutes = (distance / 1000) / speed_kmh * 60
            
            etas.append({
                'bus_id': bus['bus_id'],
                'registration_number': bus['registration_number'],
                'route_id': bus['route_id'],
                'route_name': bus['route_name'],
                'route_code': bus['route_code'],
                'route_color': bus['color'],
                'eta_minutes': round(eta_minutes, 1),
                'distance_meters': round(distance),
                'current_latitude': bus_lat,
                'current_longitude': bus_lon
            })
        
        # Sort by ETA
        etas.sort(key=lambda x: x['eta_minutes'])
        
        return Response({
            'stop': {
                'id': stop['stop_id'],
                'name': stop['stop_name']
            },
            'etas': etas,
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_200_OK)


class RouteETAsView(APIView):
    """
    GET /api/routes/{route_id}/etas/ - Get ETAs for buses on a route at all stops
    """
    
    def get(self, request, route_id):
        # Get route info
        route = execute_query_one(
            "SELECT route_id, route_name, route_code, color FROM routes WHERE route_id = %s",
            [route_id]
        )
        
        if not route:
            return Response(
                {'detail': 'Route not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all stops on this route
        stops = execute_query(
            """
            SELECT 
                rs.sequence_number, rs.stop_id,
                s.stop_name, s.latitude, s.longitude
            FROM route_stops rs
            JOIN stops s ON rs.stop_id = s.stop_id
            WHERE rs.route_id = %s
            ORDER BY rs.sequence_number
            """,
            [route_id]
        )
        
        # Get active buses on this route
        buses = execute_query(
            """
            SELECT 
                b.bus_id, b.registration_number,
                bl.latitude, bl.longitude, bl.speed, bl.current_stop_sequence
            FROM buses b
            LEFT JOIN bus_locations bl ON b.bus_id = bl.bus_id
            WHERE b.status = 'active' AND b.route_id = %s
            """,
            [route_id]
        )
        
        bus_data = []
        for bus in buses:
            if not bus['latitude'] or not bus['longitude']:
                continue
            
            bus_lat = float(bus['latitude'])
            bus_lon = float(bus['longitude'])
            bus_sequence = bus['current_stop_sequence'] or 0
            speed_kmh = float(bus['speed']) if bus['speed'] and float(bus['speed']) > 0 else 25
            
            # Calculate ETAs to upcoming stops
            next_stops = []
            cumulative_distance = 0
            prev_lat, prev_lon = bus_lat, bus_lon
            
            for stop in stops:
                if stop['sequence_number'] <= bus_sequence:
                    continue  # Already passed this stop
                
                stop_lat = float(stop['latitude'])
                stop_lon = float(stop['longitude'])
                
                # Calculate distance from previous point (bus or last stop)
                segment_distance = calculate_distance(prev_lat, prev_lon, stop_lat, stop_lon)
                cumulative_distance += segment_distance
                
                # Estimate ETA
                eta_minutes = (cumulative_distance / 1000) / speed_kmh * 60
                
                next_stops.append({
                    'stop_id': stop['stop_id'],
                    'stop_name': stop['stop_name'],
                    'sequence': stop['sequence_number'],
                    'eta_minutes': round(eta_minutes, 1),
                    'distance_meters': round(cumulative_distance)
                })
                
                prev_lat, prev_lon = stop_lat, stop_lon
            
            bus_data.append({
                'bus_id': bus['bus_id'],
                'registration_number': bus['registration_number'],
                'current_stop_sequence': bus_sequence,
                'next_stops': next_stops
            })
        
        return Response({
            'route': {
                'id': route['route_id'],
                'name': route['route_name'],
                'code': route['route_code'],
                'color': route['color']
            },
            'buses': bus_data,
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_200_OK)
