"""
ETA (Estimated Time of Arrival) API views using raw SQL queries.
Uses MapBox Directions API for accurate road-based ETA calculations.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one
from .mapbox import get_eta_to_stop, get_etas_to_multiple_stops, fallback_eta
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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
            
            # current_stop_sequence now uses MapBox for accurate positioning:
            # - If bus is at stop N (within 150m road distance): sequence = N
            # - If bus departed stop N and heading to N+1: sequence = N+1
            # So: sequence > stop_sequence means bus has passed this stop
            #     sequence == stop_sequence means bus is AT or APPROACHING this stop
            #     sequence < stop_sequence means bus is approaching this stop
            stop_sequence = route_sequences.get(bus_route_id, 0)
            bus_sequence = int(bus['current_stop_sequence'] or 0)
            
            if bus_sequence > stop_sequence:
                continue  # Bus has already passed this stop
            
            # Get ETA using MapBox
            eta_result = get_eta_to_stop(
                bus_location=(bus_lon, bus_lat),
                stop_location=(stop_lon, stop_lat)
            )
            
            # Fallback if MapBox fails
            if not eta_result:
                logger.warning(f"MapBox API failed for bus {bus['bus_id']}, using fallback")
                speed_kmh = float(bus['speed']) if bus['speed'] and float(bus['speed']) > 0 else 25
                eta_result = fallback_eta(bus_lat, bus_lon, stop_lat, stop_lon, speed_kmh)
            
            distance_to_stop = eta_result['distance_meters']
            eta_minutes = eta_result['eta_minutes']
            
            # Determine arrival status based on distance (150m threshold for "at stop")
            AT_STOP_THRESHOLD = 150
            if distance_to_stop <= AT_STOP_THRESHOLD:
                arrival_status = 'arrived'
                eta_minutes = 0
                distance_to_stop = 0
            elif eta_minutes <= 1:
                arrival_status = 'arriving'
            elif eta_minutes <= 3:
                arrival_status = 'approaching'
            else:
                arrival_status = 'on-route'
            
            etas.append({
                'bus_id': bus['bus_id'],
                'registration_number': bus['registration_number'],
                'route_id': bus['route_id'],
                'route_name': bus['route_name'],
                'route_code': bus['route_code'],
                'route_color': bus['color'],
                'eta_minutes': eta_minutes,
                'distance_meters': distance_to_stop,
                'current_latitude': bus_lat,
                'current_longitude': bus_lon,
                'arrival_status': arrival_status
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
            
            # Get upcoming stops for this bus
            upcoming_stops = []
            for stop in stops:
                if stop['sequence_number'] <= bus_sequence:
                    continue  # Already passed this stop
                upcoming_stops.append({
                    'sequence': stop['sequence_number'],
                    'stop_id': stop['stop_id'],
                    'stop_name': stop['stop_name'],
                    'latitude': float(stop['latitude']),
                    'longitude': float(stop['longitude'])
                })
            
            if not upcoming_stops:
                continue
            
            # Prepare stop locations for MapBox: (lon, lat, stop_id, stop_name)
            stop_locations = [
                (s['longitude'], s['latitude'], s['stop_id'], s['stop_name'])
                for s in upcoming_stops
            ]
            
            # Use MapBox API for multi-stop ETA calculation
            eta_results = get_etas_to_multiple_stops(
                bus_location=(bus_lon, bus_lat),
                stop_locations=stop_locations
            )
            
            # If MapBox fails, use fallback
            if not eta_results:
                logger.warning(f"MapBox API failed for bus {bus['bus_id']}, using fallback")
                speed_kmh = float(bus['speed']) if bus['speed'] and float(bus['speed']) > 0 else 25
                cumulative_eta = 0
                cumulative_distance = 0
                prev_lat, prev_lon = bus_lat, bus_lon
                
                eta_results = []
                for stop_info in upcoming_stops:
                    # Calculate incremental ETA using fallback
                    segment = fallback_eta(
                        prev_lat, prev_lon,
                        stop_info['latitude'], stop_info['longitude'],
                        speed_kmh
                    )
                    cumulative_eta += segment['eta_minutes']
                    cumulative_distance += segment['distance_meters']
                    
                    eta_results.append({
                        'stop_id': stop_info['stop_id'],
                        'stop_name': stop_info['stop_name'],
                        'eta_minutes': round(cumulative_eta, 1),
                        'distance_meters': round(cumulative_distance)
                    })
                    
                    prev_lat = stop_info['latitude']
                    prev_lon = stop_info['longitude']
            
            # Build next_stops response
            next_stops = []
            for i, stop_info in enumerate(upcoming_stops):
                if i < len(eta_results):
                    eta = eta_results[i]
                    next_stops.append({
                        'stop_id': eta['stop_id'],
                        'stop_name': eta['stop_name'],
                        'sequence': stop_info['sequence'],
                        'eta_minutes': eta['eta_minutes'],
                        'distance_meters': eta['distance_meters']
                    })
            
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
