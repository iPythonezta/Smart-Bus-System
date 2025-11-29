"""
Display Units (SMD) API views using raw SQL queries.
Uses MapBox Directions API for accurate road-based ETA calculations.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one, execute_insert, execute_update
from .mapbox import get_eta_to_stop, fallback_eta
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def format_display_response(display):
    """Format a display unit record into API response format."""
    response = {
        'id': display['display_id'],
        'name': display['display_name'],
        'stop_id': display['stop_id'],
        'location': display.get('location'),
        'status': display['status'],
        'last_heartbeat': display['last_heartbeat'].isoformat() if display.get('last_heartbeat') else None,
        'created_at': display['created_at'].isoformat() if display.get('created_at') else None,
        'updated_at': display['updated_at'].isoformat() if display.get('updated_at') else None,
    }
    
    # Add stop info if available from JOIN
    if display.get('stop_name'):
        response['stop'] = {
            'id': display['stop_id'],
            'name': display['stop_name'],
            'latitude': float(display['stop_latitude']) if display.get('stop_latitude') else None,
            'longitude': float(display['stop_longitude']) if display.get('stop_longitude') else None,
        }
    
    return response


class DisplayListView(APIView):
    """
    GET /api/displays/ - List all display units
    POST /api/displays/ - Create a new display unit
    """
    
    def get(self, request):
        # Get query parameters
        search = request.query_params.get('search')
        status_filter = request.query_params.get('status')
        stop_id = request.query_params.get('stop_id')
        
        # Build query with filters
        sql = """
            SELECT 
                d.display_id, d.display_name, d.stop_id, d.location,
                d.status, d.last_heartbeat, d.created_at, d.updated_at,
                s.stop_name, s.latitude as stop_latitude, s.longitude as stop_longitude
            FROM display_units d
            JOIN stops s ON d.stop_id = s.stop_id
            WHERE 1=1
        """
        params = []
        
        if search:
            sql += " AND (d.display_name LIKE %s OR d.location LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        if status_filter and status_filter in ['online', 'offline', 'error']:
            sql += " AND d.status = %s"
            params.append(status_filter)
        
        if stop_id:
            sql += " AND d.stop_id = %s"
            params.append(stop_id)
        
        sql += " ORDER BY d.display_id DESC"
        
        displays = execute_query(sql, params)
        
        return Response([format_display_response(d) for d in displays], status=status.HTTP_200_OK)
    
    def post(self, request):
        # Validate required fields
        errors = {}
        
        name = request.data.get('name')
        if not name or len(str(name).strip()) < 2:
            errors['name'] = ['Name is required and must be at least 2 characters.']
        
        stop_id = request.data.get('stop_id')
        if not stop_id:
            errors['stop_id'] = ['Stop ID is required.']
        else:
            # Validate stop exists
            stop = execute_query_one(
                "SELECT stop_id FROM stops WHERE stop_id = %s",
                [stop_id]
            )
            if not stop:
                errors['stop_id'] = [f'Stop with ID {stop_id} does not exist.']
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get optional fields
        location = request.data.get('location')
        display_status = request.data.get('status', 'offline')
        
        if display_status not in ['online', 'offline', 'error']:
            display_status = 'offline'
        
        # Insert the display unit
        display_id = execute_insert(
            """
            INSERT INTO display_units (display_name, stop_id, location, status)
            VALUES (%s, %s, %s, %s)
            """,
            [name, stop_id, location, display_status]
        )
        
        # Fetch the created display with stop info
        display = execute_query_one(
            """
            SELECT 
                d.display_id, d.display_name, d.stop_id, d.location,
                d.status, d.last_heartbeat, d.created_at, d.updated_at,
                s.stop_name, s.latitude as stop_latitude, s.longitude as stop_longitude
            FROM display_units d
            JOIN stops s ON d.stop_id = s.stop_id
            WHERE d.display_id = %s
            """,
            [display_id]
        )
        
        return Response(format_display_response(display), status=status.HTTP_201_CREATED)


class DisplayDetailView(APIView):
    """
    GET /api/displays/{id}/ - Get display unit details
    PATCH /api/displays/{id}/ - Update display unit
    DELETE /api/displays/{id}/ - Delete display unit
    """
    
    def get(self, request, display_id):
        display = execute_query_one(
            """
            SELECT 
                d.display_id, d.display_name, d.stop_id, d.location,
                d.status, d.last_heartbeat, d.created_at, d.updated_at,
                s.stop_name, s.latitude as stop_latitude, s.longitude as stop_longitude
            FROM display_units d
            JOIN stops s ON d.stop_id = s.stop_id
            WHERE d.display_id = %s
            """,
            [display_id]
        )
        
        if not display:
            return Response(
                {'detail': 'Display not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(format_display_response(display), status=status.HTTP_200_OK)
    
    def patch(self, request, display_id):
        # Check if display exists
        existing = execute_query_one(
            "SELECT display_id FROM display_units WHERE display_id = %s",
            [display_id]
        )
        if not existing:
            return Response(
                {'detail': 'Display not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build update query dynamically
        updates = []
        params = []
        errors = {}
        
        if 'name' in request.data:
            name = request.data['name']
            if not name or len(str(name).strip()) < 2:
                errors['name'] = ['Name must be at least 2 characters.']
            else:
                updates.append("display_name = %s")
                params.append(name)
        
        if 'stop_id' in request.data:
            stop_id = request.data['stop_id']
            stop = execute_query_one(
                "SELECT stop_id FROM stops WHERE stop_id = %s",
                [stop_id]
            )
            if not stop:
                errors['stop_id'] = [f'Stop with ID {stop_id} does not exist.']
            else:
                updates.append("stop_id = %s")
                params.append(stop_id)
        
        if 'location' in request.data:
            updates.append("location = %s")
            params.append(request.data['location'])
        
        if 'status' in request.data:
            display_status = request.data['status']
            if display_status not in ['online', 'offline', 'error']:
                errors['status'] = ['Status must be online, offline, or error.']
            else:
                updates.append("status = %s")
                params.append(display_status)
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        if not updates:
            return Response(
                {'detail': 'No valid fields to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute update
        params.append(display_id)
        execute_update(
            f"UPDATE display_units SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE display_id = %s",
            params
        )
        
        # Return updated display
        return self.get(request, display_id)
    
    def delete(self, request, display_id):
        # Check if display exists
        existing = execute_query_one(
            "SELECT display_id FROM display_units WHERE display_id = %s",
            [display_id]
        )
        if not existing:
            return Response(
                {'detail': 'Display not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Delete (ad schedules deleted via CASCADE)
        execute_update("DELETE FROM display_units WHERE display_id = %s", [display_id])
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class DisplayHeartbeatView(APIView):
    """
    POST /api/displays/{id}/heartbeat/ - Update display heartbeat/status
    """
    
    def post(self, request, display_id):
        # Check if display exists
        existing = execute_query_one(
            "SELECT display_id FROM display_units WHERE display_id = %s",
            [display_id]
        )
        if not existing:
            return Response(
                {'detail': 'Display not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get status from request
        display_status = request.data.get('status', 'online')
        if display_status not in ['online', 'offline', 'error']:
            display_status = 'online'
        
        # Update heartbeat and status
        execute_update(
            """
            UPDATE display_units 
            SET status = %s, last_heartbeat = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE display_id = %s
            """,
            [display_status, display_id]
        )
        
        # Get updated display
        display = execute_query_one(
            "SELECT display_id, status, last_heartbeat FROM display_units WHERE display_id = %s",
            [display_id]
        )
        
        return Response({
            'id': display['display_id'],
            'status': display['status'],
            'last_heartbeat': display['last_heartbeat'].isoformat() if display['last_heartbeat'] else None,
            'message': 'Heartbeat recorded'
        }, status=status.HTTP_200_OK)


class DisplayContentView(APIView):
    """
    GET /api/displays/{id}/content/ - Get content for display (buses, announcements, ads)
    """
    
    def get(self, request, display_id):
        # Get display with stop info
        display = execute_query_one(
            """
            SELECT 
                d.display_id, d.display_name, d.stop_id,
                s.stop_name, s.latitude as stop_latitude, s.longitude as stop_longitude
            FROM display_units d
            JOIN stops s ON d.stop_id = s.stop_id
            WHERE d.display_id = %s
            """,
            [display_id]
        )
        
        if not display:
            return Response(
                {'detail': 'Display not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        stop_id = display['stop_id']
        stop_lat = float(display['stop_latitude'])
        stop_lon = float(display['stop_longitude'])
        
        # Get routes that pass through this stop
        routes_at_stop = execute_query(
            """
            SELECT DISTINCT rs.route_id, rs.sequence_number
            FROM route_stops rs
            WHERE rs.stop_id = %s
            """,
            [stop_id]
        )
        
        route_ids = [r['route_id'] for r in routes_at_stop]
        route_sequences = {r['route_id']: r['sequence_number'] for r in routes_at_stop}
        
        # Get active buses on these routes with their locations
        upcoming_buses = []
        if route_ids:
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
                
                upcoming_buses.append({
                    'bus_id': bus['bus_id'],
                    'registration_number': bus['registration_number'],
                    'route_id': bus['route_id'],
                    'route_name': bus['route_name'],
                    'route_code': bus['route_code'],
                    'route_color': bus['color'],
                    'eta_minutes': eta_minutes,
                    'distance_meters': distance_to_stop,
                    'arrival_status': arrival_status
                })
        
        # Sort by ETA
        upcoming_buses.sort(key=lambda x: x['eta_minutes'])
        
        # Get active announcements for routes at this stop (or global)
        announcements = []
        announcement_sql = """
            SELECT DISTINCT
                a.announcement_id, a.title, a.message, a.message_ur, a.severity
            FROM announcements a
            LEFT JOIN announcement_routes ar ON a.announcement_id = ar.announcement_id
            WHERE NOW() BETWEEN a.start_time AND a.end_time
        """
        
        if route_ids:
            placeholders = ','.join(['%s'] * len(route_ids))
            announcement_sql += f"""
                AND (ar.route_id IN ({placeholders}) OR ar.route_id IS NULL)
            """
            announcement_rows = execute_query(announcement_sql, route_ids)
        else:
            announcement_sql += " AND ar.route_id IS NULL"
            announcement_rows = execute_query(announcement_sql)
        
        for ann in announcement_rows:
            announcements.append({
                'id': ann['announcement_id'],
                'title': ann['title'],
                'message': ann['message'],
                'message_ur': ann.get('message_ur'),
                'severity': ann['severity']
            })
        
        # Get active advertisements scheduled for this display
        ads = execute_query(
            """
            SELECT 
                a.ad_id, a.title, a.content_url, a.media_type, a.duration_sec,
                s.priority
            FROM ad_schedule s
            JOIN advertisements a ON s.ad_id = a.ad_id
            WHERE s.display_id = %s
              AND NOW() BETWEEN s.start_time AND s.end_time
            ORDER BY s.priority DESC
            """,
            [display_id]
        )
        
        advertisements = [
            {
                'id': ad['ad_id'],
                'title': ad['title'],
                'content_url': ad['content_url'],
                'media_type': ad['media_type'],
                'duration_seconds': ad['duration_sec'],
                'priority': ad['priority']
            }
            for ad in ads
        ]
        
        return Response({
            'display': {
                'id': display['display_id'],
                'name': display['display_name'],
                'stop_id': display['stop_id']
            },
            'stop': {
                'id': display['stop_id'],
                'name': display['stop_name'],
                'latitude': stop_lat,
                'longitude': stop_lon
            },
            'upcoming_buses': upcoming_buses,
            'announcements': announcements,
            'advertisements': advertisements,
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_200_OK)
