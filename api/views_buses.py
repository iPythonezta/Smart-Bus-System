"""
Bus API views using raw SQL queries.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one, execute_insert, execute_update
from .mapbox import get_bus_position_on_route, haversine_distance
from math import radians, sin, cos, sqrt, atan2
import logging

logger = logging.getLogger(__name__)


def is_admin(user):
    """Check if user is admin."""
    return user.user_type == 'ADMIN'


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


def format_bus_response(bus, include_route_stops=False):
    """Format a bus record into API response format."""
    response = {
        'id': bus['bus_id'],
        'registration_number': bus['registration_number'],
        'capacity': bus['capacity'],
        'status': bus['status'],
        'route_id': bus['route_id'],
        'created_at': bus['created_at'].isoformat() if bus.get('created_at') else None,
        'updated_at': bus['updated_at'].isoformat() if bus.get('updated_at') else None,
    }
    
    # Add route info if available
    if bus.get('route_id') and bus.get('route_name'):
        response['route'] = {
            'id': bus['route_id'],
            'name': bus['route_name'],
            'code': bus['route_code'],
            'color': bus['color'],
        }
        if include_route_stops and bus.get('description') is not None:
            response['route']['description'] = bus.get('description')
    else:
        response['route'] = None
    
    # Add location info if available
    if bus.get('latitude') is not None:
        response['last_location'] = {
            'latitude': float(bus['latitude']),
            'longitude': float(bus['longitude']),
            'speed': float(bus['speed']) if bus.get('speed') else 0,
            'heading': float(bus['heading']) if bus.get('heading') else 0,
            'current_stop_sequence': bus.get('current_stop_sequence'),
            'timestamp': bus['location_timestamp'].isoformat() if bus.get('location_timestamp') else None,
        }
    else:
        response['last_location'] = None
    
    return response


class BusListView(APIView):
    """
    GET /api/buses/ - List all buses with details, routes, and latest location
    POST /api/buses/ - Create a new bus (Admin only)
    """
    
    def get(self, request):
        # Get query parameters
        status_filter = request.query_params.get('status')
        route_id = request.query_params.get('route_id')
        search = request.query_params.get('search')
        
        # Build query with filters
        sql = """
            SELECT 
                b.bus_id,
                b.registration_number,
                b.capacity,
                b.status,
                b.route_id,
                b.created_at,
                b.updated_at,
                r.route_name,
                r.route_code,
                r.color,
                bl.latitude,
                bl.longitude,
                bl.speed,
                bl.heading,
                bl.current_stop_sequence,
                bl.recorded_at as location_timestamp
            FROM buses b
            LEFT JOIN routes r ON b.route_id = r.route_id
            LEFT JOIN (
                SELECT bl1.bus_id, bl1.latitude, bl1.longitude, bl1.speed, 
                       bl1.heading, bl1.current_stop_sequence, bl1.recorded_at
                FROM bus_locations bl1
                INNER JOIN (
                    SELECT bus_id, MAX(recorded_at) as max_recorded
                    FROM bus_locations
                    GROUP BY bus_id
                ) bl2 ON bl1.bus_id = bl2.bus_id AND bl1.recorded_at = bl2.max_recorded
            ) bl ON b.bus_id = bl.bus_id
            WHERE 1=1
        """
        params = []
        
        if status_filter:
            sql += " AND b.status = %s"
            params.append(status_filter)
        
        if route_id:
            sql += " AND b.route_id = %s"
            params.append(route_id)
        
        if search:
            sql += " AND b.registration_number LIKE %s"
            params.append(f'%{search}%')
        
        sql += " ORDER BY b.bus_id"
        
        buses = execute_query(sql, params)
        
        return Response([format_bus_response(bus) for bus in buses], status=status.HTTP_200_OK)
    
    def post(self, request):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can create buses.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate required fields
        registration_number = request.data.get('registration_number')
        if not registration_number:
            return Response(
                {'error': 'registration_number is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for duplicate registration number
        existing = execute_query_one(
            "SELECT bus_id FROM buses WHERE registration_number = %s",
            [registration_number]
        )
        if existing:
            return Response(
                {'error': 'A bus with this registration number already exists.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get optional fields
        capacity = request.data.get('capacity', 50)
        bus_status = request.data.get('status', 'inactive')
        route_id = request.data.get('route_id')
        
        # Validate route_id if provided
        if route_id:
            route = execute_query_one(
                "SELECT route_id FROM routes WHERE route_id = %s",
                [route_id]
            )
            if not route:
                return Response(
                    {'error': 'Invalid route_id.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Insert the bus
        bus_id = execute_insert(
            """
            INSERT INTO buses (registration_number, capacity, status, route_id)
            VALUES (%s, %s, %s, %s)
            """,
            [registration_number, capacity, bus_status, route_id]
        )
        
        # Fetch the created bus with route info
        bus = execute_query_one(
            """
            SELECT 
                b.bus_id, b.registration_number, b.capacity, b.status,
                b.route_id, b.created_at, b.updated_at,
                r.route_name, r.route_code, r.color
            FROM buses b
            LEFT JOIN routes r ON b.route_id = r.route_id
            WHERE b.bus_id = %s
            """,
            [bus_id]
        )
        
        return Response(format_bus_response(bus), status=status.HTTP_201_CREATED)


class BusDetailView(APIView):
    """
    GET /api/buses/{id}/ - Get detailed bus information with full route
    PATCH /api/buses/{id}/ - Update bus details (Admin only)
    DELETE /api/buses/{id}/ - Delete a bus (Admin only)
    """
    
    def get(self, request, bus_id):
        # Get bus with route info
        bus = execute_query_one(
            """
            SELECT 
                b.bus_id, b.registration_number, b.capacity, b.status,
                b.route_id, b.created_at, b.updated_at,
                r.route_name, r.route_code, r.color, r.description,
                bl.latitude, bl.longitude, bl.speed, bl.heading,
                bl.current_stop_sequence, bl.recorded_at as location_timestamp
            FROM buses b
            LEFT JOIN routes r ON b.route_id = r.route_id
            LEFT JOIN (
                SELECT bl1.bus_id, bl1.latitude, bl1.longitude, bl1.speed,
                       bl1.heading, bl1.current_stop_sequence, bl1.recorded_at
                FROM bus_locations bl1
                INNER JOIN (
                    SELECT bus_id, MAX(recorded_at) as max_recorded
                    FROM bus_locations
                    GROUP BY bus_id
                ) bl2 ON bl1.bus_id = bl2.bus_id AND bl1.recorded_at = bl2.max_recorded
            ) bl ON b.bus_id = bl.bus_id
            WHERE b.bus_id = %s
            """,
            [bus_id]
        )
        
        if not bus:
            return Response(
                {'error': 'Bus not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        response = format_bus_response(bus, include_route_stops=True)
        
        # Get route stops if bus has a route
        if bus['route_id']:
            stops = execute_query(
                """
                SELECT 
                    rs.sequence_number as sequence,
                    rs.stop_id,
                    s.stop_name,
                    s.latitude,
                    s.longitude,
                    rs.distance_from_prev_meters
                FROM route_stops rs
                JOIN stops s ON rs.stop_id = s.stop_id
                WHERE rs.route_id = %s
                ORDER BY rs.sequence_number
                """,
                [bus['route_id']]
            )
            
            response['route']['stops'] = [
                {
                    'sequence': stop['sequence'],
                    'stop_id': stop['stop_id'],
                    'stop_name': stop['stop_name'],
                    'latitude': float(stop['latitude']),
                    'longitude': float(stop['longitude']),
                    'distance_from_prev_meters': stop['distance_from_prev_meters']
                }
                for stop in stops
            ]
            
            # Calculate next stop info if bus has location
            if bus.get('current_stop_sequence') is not None and stops:
                current_seq = bus['current_stop_sequence']
                next_stop = None
                
                for stop in stops:
                    if stop['sequence'] > current_seq:
                        next_stop = stop
                        break
                
                if next_stop:
                    # Calculate ETA (simple estimation based on distance and average speed)
                    distance = next_stop['distance_from_prev_meters']
                    avg_speed = float(bus.get('speed', 0)) or 30  # Default 30 km/h if stopped
                    
                    # Only calculate ETA if distance is available
                    if distance is not None and avg_speed > 0:
                        eta_minutes = (distance / 1000) / avg_speed * 60
                    else:
                        eta_minutes = None
                    
                    response['next_stop'] = {
                        'sequence': next_stop['sequence'],
                        'stop_id': next_stop['stop_id'],
                        'stop_name': next_stop['stop_name'],
                        'distance_meters': distance,
                        'eta_minutes': round(eta_minutes, 1) if eta_minutes else None
                    }
                else:
                    response['next_stop'] = None
            else:
                response['next_stop'] = None
        
        return Response(response, status=status.HTTP_200_OK)
    
    def patch(self, request, bus_id):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can update buses.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if bus exists
        existing = execute_query_one(
            "SELECT bus_id FROM buses WHERE bus_id = %s",
            [bus_id]
        )
        if not existing:
            return Response(
                {'error': 'Bus not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build update query dynamically
        updates = []
        params = []
        
        if 'registration_number' in request.data:
            # Check for duplicate
            reg_num = request.data['registration_number']
            dup = execute_query_one(
                "SELECT bus_id FROM buses WHERE registration_number = %s AND bus_id != %s",
                [reg_num, bus_id]
            )
            if dup:
                return Response(
                    {'error': 'A bus with this registration number already exists.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            updates.append("registration_number = %s")
            params.append(reg_num)
        
        if 'capacity' in request.data:
            updates.append("capacity = %s")
            params.append(request.data['capacity'])
        
        if 'status' in request.data:
            if request.data['status'] not in ['active', 'inactive', 'maintenance']:
                return Response(
                    {'error': 'Invalid status. Must be active, inactive, or maintenance.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            updates.append("status = %s")
            params.append(request.data['status'])
        
        if 'route_id' in request.data:
            route_id = request.data['route_id']
            if route_id is not None:
                route = execute_query_one(
                    "SELECT route_id FROM routes WHERE route_id = %s",
                    [route_id]
                )
                if not route:
                    return Response(
                        {'error': 'Invalid route_id.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            updates.append("route_id = %s")
            params.append(route_id)
        
        if not updates:
            return Response(
                {'error': 'No valid fields to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute update
        params.append(bus_id)
        execute_update(
            f"UPDATE buses SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE bus_id = %s",
            params
        )
        
        # Return updated bus (reuse GET logic)
        return self.get(request, bus_id)
    
    def delete(self, request, bus_id):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can delete buses.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if bus exists
        existing = execute_query_one(
            "SELECT bus_id FROM buses WHERE bus_id = %s",
            [bus_id]
        )
        if not existing:
            return Response(
                {'error': 'Bus not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Delete (location history deleted via CASCADE)
        execute_update("DELETE FROM buses WHERE bus_id = %s", [bus_id])
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class BusLocationView(APIView):
    """
    POST /api/buses/{id}/location/ - Update bus GPS location
    """
    
    def post(self, request, bus_id):
        # Validate required fields
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if latitude is None or longitude is None:
            return Response(
                {'error': 'latitude and longitude are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if bus exists and get route
        bus = execute_query_one(
            """
            SELECT 
                b.bus_id, 
                b.route_id, 
                bl.current_stop_sequence
            FROM buses b
            JOIN bus_locations bl ON b.bus_id = bl.bus_id
            WHERE b.bus_id = %s
            """,
            [bus_id]
        )
        if not bus:
            return Response(
                {'error': 'Bus not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get and clamp speed/heading to valid DECIMAL(5,2) range (max 999.99)
        speed = min(max(float(request.data.get('speed', 0) or 0), 0), 999.99)
        heading = min(max(float(request.data.get('heading', 0) or 0), 0), 360)
        
        # Calculate current_stop_sequence using MapBox for accurate road-based positioning
        # This determines which stop the bus is at or heading toward.
        current_stop_seq_from_db = bus.get('current_stop_sequence') or 0
        print(current_stop_seq_from_db)
        current_stop_sequence = None
        
        if bus['route_id']:
            stops = execute_query(
                """
                SELECT rs.sequence_number as sequence, rs.stop_id, s.latitude, s.longitude
                FROM route_stops rs
                JOIN stops s ON rs.stop_id = s.stop_id
                WHERE rs.route_id = %s
                ORDER BY rs.sequence_number
                """,
                [bus['route_id']]
            )
            
            if stops:
                # Convert to format expected by MapBox function
                route_stops = [
                    {
                        'sequence': s['sequence'],
                        'stop_id': s['stop_id'],
                        'latitude': float(s['latitude']),
                        'longitude': float(s['longitude'])
                    }
                    for s in stops
                ]
                
                # Use MapBox to determine bus position on route
                position = get_bus_position_on_route(
                    bus_location=(longitude, latitude),  # MapBox uses (lon, lat)
                    route_stops=route_stops,
                    stop_seq=current_stop_seq_from_db
                )
                
                current_stop_sequence = position['current_stop_sequence']
                eta_to_next = position['eta_to_next']  # ETA in minutes
                
                logger.info(f"Bus {bus_id} position: at_stop={position['is_at_stop']}, "
                           f"sequence={current_stop_sequence}, "
                           f"next_stop={position['next_stop']}, "
                           f"eta={eta_to_next}min")
                
                # ===== SIMPLIFIED ETA-BASED STOP MARKING =====
                # When ETA < 2 min: Mark stop as passed immediately
                # Simple and straightforward!
                
                PASSED_ETA_THRESHOLD = 1.0  # minutes - mark passed when ETA drops below this
                
                # Check if bus is close to current stop (ETA < 2 min)
                if eta_to_next is not None and eta_to_next < PASSED_ETA_THRESHOLD:
                    # Get current stop's passed status
                    stop_data = execute_query_one(
                        """
                        SELECT passed 
                        FROM route_stops 
                        WHERE route_id = %s AND sequence_number = %s
                        """,
                        [bus['route_id'], current_stop_sequence]
                    )
                    
                    # If not already marked as passed, mark it now
                    if stop_data and not stop_data['passed']:
                        execute_update(
                            """
                            UPDATE route_stops 
                            SET passed = TRUE 
                            WHERE route_id = %s AND sequence_number = %s
                            """,
                            [bus['route_id'], current_stop_sequence]
                        )
                        logger.info(f"✅ Marked stop {current_stop_sequence} as PASSED (ETA: {eta_to_next} min < 2 min threshold)")
        
        # Upsert location record (update if exists, insert if not)
        # This keeps only the latest location per bus
        execute_update(
            """
            INSERT INTO bus_locations 
            (bus_id, latitude, longitude, speed, heading, current_stop_sequence, recorded_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                latitude = VALUES(latitude),
                longitude = VALUES(longitude),
                speed = VALUES(speed),
                heading = VALUES(heading),
                current_stop_sequence = VALUES(current_stop_sequence),
                recorded_at = CURRENT_TIMESTAMP
            """,
            [bus_id, latitude, longitude, speed, heading, current_stop_sequence]
        )
        
        # Update bus timestamp
        execute_update(
            "UPDATE buses SET updated_at = CURRENT_TIMESTAMP WHERE bus_id = %s",
            [bus_id]
        )
        
        # Get the location record
        location = execute_query_one(
            """
            SELECT location_id, bus_id, latitude, longitude, speed, 
                   heading, current_stop_sequence, recorded_at
            FROM bus_locations WHERE bus_id = %s
            """,
            [bus_id]
        )
        
        return Response({
            'id': location['location_id'],
            'bus_id': location['bus_id'],
            'latitude': float(location['latitude']),
            'longitude': float(location['longitude']),
            'speed': float(location['speed']),
            'heading': float(location['heading']),
            'current_stop_sequence': location['current_stop_sequence'],
            'timestamp': location['recorded_at'].isoformat()
        }, status=status.HTTP_201_CREATED)


class BusStartTripView(APIView):
    """
    POST /api/buses/{id}/start-trip/ - Set bus status to active
    """
    
    def post(self, request, bus_id):
        # Check if bus exists
        bus = execute_query_one(
            "SELECT bus_id, route_id, status FROM buses WHERE bus_id = %s",
            [bus_id]
        )
        if not bus:
            return Response(
                {'error': 'Bus not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get route_id from request or existing bus assignment
        route_id = request.data.get('route_id', bus['route_id'])
        
        if not route_id:
            return Response(
                {'error': 'route_id is required (bus has no assigned route).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate route exists
        route = execute_query_one(
            "SELECT route_id, route_name FROM routes WHERE route_id = %s",
            [route_id]
        )
        if not route:
            return Response(
                {'error': 'Invalid route_id.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update bus status to active and set route
        execute_update(
            """
            UPDATE buses 
            SET status = 'active', route_id = %s, updated_at = CURRENT_TIMESTAMP
            WHERE bus_id = %s
            """,
            [route_id, bus_id]
        )
        
        # Reset bus location to start of route (sequence 0 = trip not started yet)
        execute_update(
            """
            INSERT INTO bus_locations 
            (bus_id, latitude, longitude, speed, heading, current_stop_sequence, recorded_at)
            VALUES (%s, 0, 0, 0, 0, 0, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                current_stop_sequence = 0,
                latitude = 0,
                longitude = 0,
                speed = 0,
                heading = 0,
                recorded_at = CURRENT_TIMESTAMP
            """,
            [bus_id]
        )
        
        # CRITICAL: Reset all 'passed' flags for this route
        # This allows all stops to be visited fresh on the new trip
        execute_update(
            """
            UPDATE route_stops 
            SET passed = FALSE
            WHERE route_id = %s
            """,
            [route_id]
        )
        
        return Response({
            'bus_id': bus_id,
            'status': 'active',
            'route_id': route_id,
            'current_stop_sequence': 0,
            'message': 'Bus trip started - all stops reset'
        }, status=status.HTTP_200_OK)


class BusEndTripView(APIView):
    """
    POST /api/buses/{id}/end-trip/ - Set bus status to inactive
    """
    
    def post(self, request, bus_id):
        # Check if bus exists
        bus = execute_query_one(
            "SELECT bus_id, status FROM buses WHERE bus_id = %s",
            [bus_id]
        )
        if not bus:
            return Response(
                {'error': 'Bus not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_status = request.data.get('status', 'inactive')
        if new_status not in ['inactive', 'maintenance']:
            new_status = 'inactive'
        
        # Update bus status
        execute_update(
            """
            UPDATE buses 
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE bus_id = %s
            """,
            [new_status, bus_id]
        )
        
        # Reset speed and heading to 0 in bus_locations
        execute_update(
            """
            UPDATE bus_locations 
            SET speed = 0, heading = 0
            WHERE bus_id = %s
            """,
            [bus_id]
        )
        
        return Response({
            'bus_id': bus_id,
            'status': new_status,
            'message': 'Bus is now ' + new_status
        }, status=status.HTTP_200_OK)


class ActiveBusesView(APIView):
    """
    GET /api/buses/active/ - Get all active buses with current locations (optimized for map)
    """
    
    def get(self, request):
        buses = execute_query(
            """
            SELECT 
                b.bus_id as id,
                b.registration_number,
                b.route_id,
                r.route_code,
                r.color as route_color,
                bl.latitude,
                bl.longitude,
                bl.heading,
                bl.speed,
                bl.current_stop_sequence,
                next_stop.stop_name as next_stop_name
            FROM buses b
            LEFT JOIN routes r ON b.route_id = r.route_id
            LEFT JOIN (
                SELECT bl1.bus_id, bl1.latitude, bl1.longitude, bl1.heading, 
                       bl1.speed, bl1.current_stop_sequence
                FROM bus_locations bl1
                INNER JOIN (
                    SELECT bus_id, MAX(recorded_at) as max_recorded
                    FROM bus_locations
                    GROUP BY bus_id
                ) bl2 ON bl1.bus_id = bl2.bus_id AND bl1.recorded_at = bl2.max_recorded
            ) bl ON b.bus_id = bl.bus_id
            LEFT JOIN route_stops rs_next ON b.route_id = rs_next.route_id 
                AND rs_next.sequence_number = COALESCE(bl.current_stop_sequence, 0) + 1
            LEFT JOIN stops next_stop ON rs_next.stop_id = next_stop.stop_id
            WHERE b.status = 'active'
            """
        )
        
        return Response([
            {
                'id': bus['id'],
                'registration_number': bus['registration_number'],
                'route_id': bus['route_id'],
                'route_code': bus['route_code'],
                'route_color': bus['route_color'],
                'latitude': float(bus['latitude']) if bus['latitude'] else None,
                'longitude': float(bus['longitude']) if bus['longitude'] else None,
                'heading': float(bus['heading']) if bus['heading'] else None,
                'speed': float(bus['speed']) if bus['speed'] else None,
                'current_stop_sequence': bus['current_stop_sequence'],
                'next_stop_name': bus['next_stop_name']
            }
            for bus in buses
        ], status=status.HTTP_200_OK)
