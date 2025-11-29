"""
Routes API views using raw SQL queries.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one, execute_insert, execute_update


def is_admin(user):
    """Check if user is admin."""
    return user.user_type == 'ADMIN'


def format_route_stop_response(route_stop):
    """Format a route_stop record into API response format."""
    response = {
        'id': route_stop['route_stop_id'],
        'route_id': route_stop['route_id'],
        'stop_id': route_stop['stop_id'],
        'sequence_number': route_stop['sequence_number'],
        'distance_from_prev': route_stop.get('distance_from_prev_meters'),
    }
    
    # Include nested stop if available
    if route_stop.get('stop_name'):
        response['stop'] = {
            'id': route_stop['stop_id'],
            'name': route_stop['stop_name'],
            'description': route_stop.get('stop_description'),
            'latitude': float(route_stop['latitude']),
            'longitude': float(route_stop['longitude']),
            'created_at': route_stop['stop_created_at'].isoformat() if route_stop.get('stop_created_at') else None,
            'updated_at': route_stop['stop_updated_at'].isoformat() if route_stop.get('stop_updated_at') else None,
        }
    
    return response


def get_route_with_stops(route_id):
    """Get a route with all its stops."""
    route = execute_query_one(
        """
        SELECT route_id, route_name, route_code, description, color,
               created_at, updated_at
        FROM routes WHERE route_id = %s
        """,
        [route_id]
    )
    
    if not route:
        return None
    
    # Get route stops with stop details
    route_stops = execute_query(
        """
        SELECT 
            rs.route_stop_id, rs.route_id, rs.stop_id, rs.sequence_number,
            rs.distance_from_prev_meters,
            s.stop_name, s.description as stop_description, s.latitude, s.longitude,
            s.created_at as stop_created_at, s.updated_at as stop_updated_at
        FROM route_stops rs
        JOIN stops s ON rs.stop_id = s.stop_id
        WHERE rs.route_id = %s
        ORDER BY rs.sequence_number
        """,
        [route_id]
    )
    
    return {
        'id': route['route_id'],
        'name': route['route_name'],
        'code': route['route_code'],
        'description': route.get('description'),
        'color': route['color'],
        'created_at': route['created_at'].isoformat() if route.get('created_at') else None,
        'updated_at': route['updated_at'].isoformat() if route.get('updated_at') else None,
        'route_stops': [format_route_stop_response(rs) for rs in route_stops]
    }


class RouteListView(APIView):
    """
    GET /api/routes/ - List all routes with stops
    POST /api/routes/ - Create a new route (Admin only)
    """
    
    def get(self, request):
        search = request.query_params.get('search')
        
        sql = """
            SELECT route_id, route_name, route_code, description, color,
                   created_at, updated_at
            FROM routes
            WHERE 1=1
        """
        params = []
        
        if search:
            sql += " AND (route_name LIKE %s OR route_code LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        sql += " ORDER BY route_name"
        
        routes = execute_query(sql, params)
        
        # Get stops for each route
        result = []
        for route in routes:
            route_data = get_route_with_stops(route['route_id'])
            if route_data:
                result.append(route_data)
        
        return Response(result, status=status.HTTP_200_OK)
    
    def post(self, request):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can create routes.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate required fields
        name = request.data.get('name')
        code = request.data.get('code')
        
        errors = {}
        
        if not name:
            errors['name'] = ['This field is required.']
        elif len(name) < 2:
            errors['name'] = ['Ensure this value has at least 2 characters.']
        
        if not code:
            errors['code'] = ['This field is required.']
        elif len(code) < 2 or len(code) > 10:
            errors['code'] = ['Ensure this value has between 2 and 10 characters.']
        else:
            # Check for duplicate code
            existing = execute_query_one(
                "SELECT route_id FROM routes WHERE route_code = %s",
                [code]
            )
            if existing:
                errors['code'] = ['Route with this code already exists.']
        
        # Check for duplicate name
        if name:
            existing_name = execute_query_one(
                "SELECT route_id FROM routes WHERE route_name = %s",
                [name]
            )
            if existing_name:
                errors['name'] = ['Route with this name already exists.']
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        description = request.data.get('description')
        color = request.data.get('color', '#3B82F6')
        
        # Validate color format
        if color and not (color.startswith('#') and len(color) == 7):
            color = '#3B82F6'
        
        # Insert the route
        route_id = execute_insert(
            """
            INSERT INTO routes (route_name, route_code, description, color)
            VALUES (%s, %s, %s, %s)
            """,
            [name, code, description, color]
        )
        
        return Response(get_route_with_stops(route_id), status=status.HTTP_201_CREATED)


class RouteDetailView(APIView):
    """
    GET /api/routes/{id}/ - Get route details with stops
    PATCH /api/routes/{id}/ - Update route (Admin only)
    DELETE /api/routes/{id}/ - Delete route (Admin only)
    """
    
    def get(self, request, route_id):
        route = get_route_with_stops(route_id)
        
        if not route:
            return Response(
                {'detail': 'Route not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(route, status=status.HTTP_200_OK)
    
    def patch(self, request, route_id):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can update routes.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if route exists
        existing = execute_query_one(
            "SELECT route_id FROM routes WHERE route_id = %s",
            [route_id]
        )
        if not existing:
            return Response(
                {'detail': 'Route not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build update query
        updates = []
        params = []
        errors = {}
        
        if 'name' in request.data:
            name = request.data['name']
            if len(name) < 2:
                errors['name'] = ['Ensure this value has at least 2 characters.']
            else:
                # Check for duplicate
                dup = execute_query_one(
                    "SELECT route_id FROM routes WHERE route_name = %s AND route_id != %s",
                    [name, route_id]
                )
                if dup:
                    errors['name'] = ['Route with this name already exists.']
                else:
                    updates.append("route_name = %s")
                    params.append(name)
        
        if 'code' in request.data:
            code = request.data['code']
            if len(code) < 2 or len(code) > 10:
                errors['code'] = ['Ensure this value has between 2 and 10 characters.']
            else:
                # Check for duplicate
                dup = execute_query_one(
                    "SELECT route_id FROM routes WHERE route_code = %s AND route_id != %s",
                    [code, route_id]
                )
                if dup:
                    errors['code'] = ['Route with this code already exists.']
                else:
                    updates.append("route_code = %s")
                    params.append(code)
        
        if 'description' in request.data:
            updates.append("description = %s")
            params.append(request.data['description'])
        
        if 'color' in request.data:
            color = request.data['color']
            if color and color.startswith('#') and len(color) == 7:
                updates.append("color = %s")
                params.append(color)
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        if not updates:
            return Response(
                {'error': 'No valid fields to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute update
        params.append(route_id)
        execute_update(
            f"UPDATE routes SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE route_id = %s",
            params
        )
        
        return Response(get_route_with_stops(route_id), status=status.HTTP_200_OK)
    
    def delete(self, request, route_id):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can delete routes.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if route exists
        existing = execute_query_one(
            "SELECT route_id FROM routes WHERE route_id = %s",
            [route_id]
        )
        if not existing:
            return Response(
                {'detail': 'Route not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if route has assigned buses
        bus_usage = execute_query_one(
            "SELECT COUNT(*) as count FROM buses WHERE route_id = %s",
            [route_id]
        )
        if bus_usage and bus_usage['count'] > 0:
            return Response(
                {'detail': 'Cannot delete route that has buses assigned'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete route (route_stops deleted via CASCADE)
        execute_update("DELETE FROM routes WHERE route_id = %s", [route_id])
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class RouteStopsView(APIView):
    """
    POST /api/routes/{route_id}/stops/ - Add a stop to a route
    """
    
    def post(self, request, route_id):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can modify route stops.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if route exists
        route = execute_query_one(
            "SELECT route_id FROM routes WHERE route_id = %s",
            [route_id]
        )
        if not route:
            return Response(
                {'detail': 'Route not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate required fields
        stop_id = request.data.get('stop_id')
        sequence_number = request.data.get('sequence_number')
        
        errors = {}
        
        if not stop_id:
            errors['stop_id'] = ['This field is required.']
        else:
            # Check if stop exists
            stop = execute_query_one(
                "SELECT stop_id FROM stops WHERE stop_id = %s AND is_active = TRUE",
                [stop_id]
            )
            if not stop:
                errors['stop_id'] = ['Stop not found.']
            else:
                # Check if stop is already in this route
                existing = execute_query_one(
                    "SELECT route_stop_id FROM route_stops WHERE route_id = %s AND stop_id = %s",
                    [route_id, stop_id]
                )
                if existing:
                    errors['stop_id'] = ['Stop is already part of this route.']
        
        if sequence_number is None:
            errors['sequence_number'] = ['This field is required.']
        else:
            try:
                sequence_number = int(sequence_number)
                if sequence_number < 1:
                    errors['sequence_number'] = ['Ensure this value is at least 1.']
            except (ValueError, TypeError):
                errors['sequence_number'] = ['A valid integer is required.']
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Shift existing stops if needed
        execute_update(
            """
            UPDATE route_stops 
            SET sequence_number = sequence_number + 1
            WHERE route_id = %s AND sequence_number >= %s
            """,
            [route_id, sequence_number]
        )
        
        # Insert the new route_stop
        route_stop_id = execute_insert(
            """
            INSERT INTO route_stops (route_id, stop_id, sequence_number, distance_from_prev_meters)
            VALUES (%s, %s, %s, %s)
            """,
            [route_id, stop_id, sequence_number, None]
        )
        
        # Fetch the created route_stop with stop details
        route_stop = execute_query_one(
            """
            SELECT 
                rs.route_stop_id, rs.route_id, rs.stop_id, rs.sequence_number,
                rs.distance_from_prev_meters,
                s.stop_name, s.description as stop_description, s.latitude, s.longitude,
                s.created_at as stop_created_at, s.updated_at as stop_updated_at
            FROM route_stops rs
            JOIN stops s ON rs.stop_id = s.stop_id
            WHERE rs.route_stop_id = %s
            """,
            [route_stop_id]
        )
        
        return Response(format_route_stop_response(route_stop), status=status.HTTP_201_CREATED)


class RouteStopDetailView(APIView):
    """
    DELETE /api/routes/{route_id}/stops/{route_stop_id}/ - Remove a stop from a route
    """
    
    def delete(self, request, route_id, route_stop_id):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can modify route stops.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if route_stop exists
        route_stop = execute_query_one(
            """
            SELECT route_stop_id, sequence_number 
            FROM route_stops 
            WHERE route_stop_id = %s AND route_id = %s
            """,
            [route_stop_id, route_id]
        )
        if not route_stop:
            return Response(
                {'detail': 'Route stop not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        deleted_sequence = route_stop['sequence_number']
        
        # Delete the route_stop
        execute_update(
            "DELETE FROM route_stops WHERE route_stop_id = %s",
            [route_stop_id]
        )
        
        # Re-sequence remaining stops
        execute_update(
            """
            UPDATE route_stops 
            SET sequence_number = sequence_number - 1
            WHERE route_id = %s AND sequence_number > %s
            """,
            [route_id, deleted_sequence]
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class RouteStopsReorderView(APIView):
    """
    PUT /api/routes/{route_id}/stops/reorder/ - Reorder all stops in a route
    """
    
    def put(self, request, route_id):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can modify route stops.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if route exists
        route = execute_query_one(
            "SELECT route_id FROM routes WHERE route_id = %s",
            [route_id]
        )
        if not route:
            return Response(
                {'detail': 'Route not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get route_stop_ids from request
        route_stop_ids = request.data.get('route_stop_ids', [])
        
        if not route_stop_ids or not isinstance(route_stop_ids, list):
            return Response(
                {'detail': 'route_stop_ids must be a non-empty array'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get existing route_stops
        existing_stops = execute_query(
            "SELECT route_stop_id FROM route_stops WHERE route_id = %s",
            [route_id]
        )
        existing_ids = {rs['route_stop_id'] for rs in existing_stops}
        provided_ids = set(route_stop_ids)
        
        # Validate all stops are included
        if existing_ids != provided_ids:
            return Response(
                {'detail': 'Invalid route_stop_ids - must include all stops in route'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update sequence numbers
        for index, route_stop_id in enumerate(route_stop_ids, start=1):
            execute_update(
                "UPDATE route_stops SET sequence_number = %s WHERE route_stop_id = %s",
                [index, route_stop_id]
            )
        
        # Get updated route with stops
        route_data = get_route_with_stops(route_id)
        
        return Response({
            'message': 'Route stops reordered successfully',
            'route_stops': route_data['route_stops']
        }, status=status.HTTP_200_OK)
