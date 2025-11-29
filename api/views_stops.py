"""
Stops API views using raw SQL queries.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one, execute_insert, execute_update


def is_admin(user):
    """Check if user is admin."""
    return user.user_type == 'ADMIN'


def format_stop_response(stop):
    """Format a stop record into API response format."""
    return {
        'id': stop['stop_id'],
        'name': stop['stop_name'],
        'description': stop.get('description'),
        'latitude': float(stop['latitude']),
        'longitude': float(stop['longitude']),
        'created_at': stop['created_at'].isoformat() if stop.get('created_at') else None,
        'updated_at': stop['updated_at'].isoformat() if stop.get('updated_at') else None,
    }


class StopListView(APIView):
    """
    GET /api/stops/ - List all stops
    POST /api/stops/ - Create a new stop (Admin only)
    """
    
    def get(self, request):
        search = request.query_params.get('search')
        
        sql = """
            SELECT stop_id, stop_name, description, latitude, longitude,
                   created_at, updated_at
            FROM stops
            WHERE is_active = TRUE
        """
        params = []
        
        if search:
            sql += " AND stop_name LIKE %s"
            params.append(f'%{search}%')
        
        sql += " ORDER BY stop_name"
        
        stops = execute_query(sql, params)
        
        return Response([format_stop_response(stop) for stop in stops], status=status.HTTP_200_OK)
    
    def post(self, request):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can create stops.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate required fields
        name = request.data.get('name')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        errors = {}
        
        if not name:
            errors['name'] = ['This field is required.']
        elif len(name) < 2:
            errors['name'] = ['Ensure this value has at least 2 characters.']
        
        if latitude is None:
            errors['latitude'] = ['This field is required.']
        else:
            try:
                lat = float(latitude)
                if lat < -90 or lat > 90:
                    errors['latitude'] = ['Ensure this value is between -90 and 90.']
            except (ValueError, TypeError):
                errors['latitude'] = ['A valid number is required.']
        
        if longitude is None:
            errors['longitude'] = ['This field is required.']
        else:
            try:
                lon = float(longitude)
                if lon < -180 or lon > 180:
                    errors['longitude'] = ['Ensure this value is between -180 and 180.']
            except (ValueError, TypeError):
                errors['longitude'] = ['A valid number is required.']
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        description = request.data.get('description')
        
        # Insert the stop
        stop_id = execute_insert(
            """
            INSERT INTO stops (stop_name, description, latitude, longitude, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            """,
            [name, description, latitude, longitude]
        )
        
        # Fetch the created stop
        stop = execute_query_one(
            """
            SELECT stop_id, stop_name, description, latitude, longitude,
                   created_at, updated_at
            FROM stops WHERE stop_id = %s
            """,
            [stop_id]
        )
        
        return Response(format_stop_response(stop), status=status.HTTP_201_CREATED)


class StopDetailView(APIView):
    """
    GET /api/stops/{id}/ - Get stop details
    PATCH /api/stops/{id}/ - Update stop (Admin only)
    DELETE /api/stops/{id}/ - Delete stop (Admin only)
    """
    
    def get(self, request, stop_id):
        stop = execute_query_one(
            """
            SELECT stop_id, stop_name, description, latitude, longitude,
                   created_at, updated_at
            FROM stops WHERE stop_id = %s AND is_active = TRUE
            """,
            [stop_id]
        )
        
        if not stop:
            return Response(
                {'detail': 'Stop not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(format_stop_response(stop), status=status.HTTP_200_OK)
    
    def patch(self, request, stop_id):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can update stops.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if stop exists
        existing = execute_query_one(
            "SELECT stop_id FROM stops WHERE stop_id = %s AND is_active = TRUE",
            [stop_id]
        )
        if not existing:
            return Response(
                {'detail': 'Stop not found'},
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
                updates.append("stop_name = %s")
                params.append(name)
        
        if 'description' in request.data:
            updates.append("description = %s")
            params.append(request.data['description'])
        
        if 'latitude' in request.data:
            try:
                lat = float(request.data['latitude'])
                if lat < -90 or lat > 90:
                    errors['latitude'] = ['Ensure this value is between -90 and 90.']
                else:
                    updates.append("latitude = %s")
                    params.append(lat)
            except (ValueError, TypeError):
                errors['latitude'] = ['A valid number is required.']
        
        if 'longitude' in request.data:
            try:
                lon = float(request.data['longitude'])
                if lon < -180 or lon > 180:
                    errors['longitude'] = ['Ensure this value is between -180 and 180.']
                else:
                    updates.append("longitude = %s")
                    params.append(lon)
            except (ValueError, TypeError):
                errors['longitude'] = ['A valid number is required.']
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        if not updates:
            return Response(
                {'error': 'No valid fields to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute update
        params.append(stop_id)
        execute_update(
            f"UPDATE stops SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE stop_id = %s",
            params
        )
        
        # Return updated stop
        return self.get(request, stop_id)
    
    def delete(self, request, stop_id):
        # Admin only
        if not is_admin(request.user):
            return Response(
                {'error': 'Only admins can delete stops.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if stop exists
        existing = execute_query_one(
            "SELECT stop_id FROM stops WHERE stop_id = %s AND is_active = TRUE",
            [stop_id]
        )
        if not existing:
            return Response(
                {'detail': 'Stop not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if stop is used in any routes
        route_usage = execute_query_one(
            "SELECT COUNT(*) as count FROM route_stops WHERE stop_id = %s",
            [stop_id]
        )
        if route_usage and route_usage['count'] > 0:
            return Response(
                {'detail': 'Cannot delete stop that is assigned to routes'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete the stop
        execute_update("DELETE FROM stops WHERE stop_id = %s", [stop_id])
        
        return Response(status=status.HTTP_204_NO_CONTENT)
