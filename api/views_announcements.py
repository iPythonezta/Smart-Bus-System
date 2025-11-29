"""
Announcement API views using raw SQL queries.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one, execute_insert, execute_update, parse_datetime


def get_announcement_routes(announcement_id):
    """Get routes associated with an announcement."""
    routes = execute_query(
        """
        SELECT r.route_id, r.route_name, r.route_code, r.color
        FROM announcement_routes ar
        JOIN routes r ON ar.route_id = r.route_id
        WHERE ar.announcement_id = %s
        ORDER BY r.route_id
        """,
        [announcement_id]
    )
    return routes


def format_announcement_response(announcement, include_routes=True):
    """Format an announcement record into API response format."""
    response = {
        'id': announcement['announcement_id'],
        'title': announcement['title'],
        'message': announcement['message'],
        'message_ur': announcement.get('message_ur'),
        'severity': announcement['severity'],
        'start_time': announcement['start_time'].isoformat() if announcement.get('start_time') else None,
        'end_time': announcement['end_time'].isoformat() if announcement.get('end_time') else None,
        'created_by': announcement.get('created_by_email'),
        'created_at': announcement['created_at'].isoformat() if announcement.get('created_at') else None,
        'updated_at': announcement['updated_at'].isoformat() if announcement.get('updated_at') else None,
    }
    
    if include_routes:
        routes = get_announcement_routes(announcement['announcement_id'])
        response['route_ids'] = [r['route_id'] for r in routes]
        response['routes'] = [
            {
                'id': r['route_id'],
                'name': r['route_name'],
                'code': r['route_code'],
                'color': r['color']
            }
            for r in routes
        ]
    
    return response


class AnnouncementListView(APIView):
    """
    GET /api/announcements/ - List all announcements
    POST /api/announcements/ - Create a new announcement
    """
    
    def get(self, request):
        # Get query parameters
        search = request.query_params.get('search')
        severity = request.query_params.get('severity')
        active = request.query_params.get('active')
        route_id = request.query_params.get('route_id')
        
        # Build query with filters
        sql = """
            SELECT DISTINCT
                a.announcement_id, a.title, a.message, a.message_ur,
                a.severity, a.start_time, a.end_time,
                a.created_by, a.created_at, a.updated_at,
                u.email as created_by_email
            FROM announcements a
            LEFT JOIN api_usermodel u ON a.created_by = u.id
        """
        
        # Join with routes if filtering by route
        if route_id:
            sql += " LEFT JOIN announcement_routes ar ON a.announcement_id = ar.announcement_id"
        
        sql += " WHERE 1=1"
        params = []
        
        if search:
            sql += " AND (a.title LIKE %s OR a.message LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        if severity and severity in ['info', 'warning', 'emergency']:
            sql += " AND a.severity = %s"
            params.append(severity)
        
        if active and active.lower() == 'true':
            sql += " AND NOW() BETWEEN a.start_time AND a.end_time"
        
        if route_id:
            # Filter by route - also include global announcements (no routes)
            sql += """
                AND (ar.route_id = %s OR a.announcement_id NOT IN (
                    SELECT DISTINCT announcement_id FROM announcement_routes
                ))
            """
            params.append(route_id)
        
        sql += " ORDER BY a.announcement_id DESC"
        
        announcements = execute_query(sql, params)
        
        return Response(
            [format_announcement_response(a) for a in announcements],
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        # Validate required fields
        errors = {}
        
        title = request.data.get('title')
        if not title or len(str(title).strip()) < 2:
            errors['title'] = ['Title is required and must be at least 2 characters.']
        
        message = request.data.get('message')
        if not message:
            errors['message'] = ['Message is required.']
        
        severity = request.data.get('severity')
        if not severity:
            errors['severity'] = ['Severity is required.']
        elif severity not in ['info', 'warning', 'emergency']:
            errors['severity'] = ['"' + str(severity) + '" is not a valid choice.']
        
        start_time = request.data.get('start_time')
        if not start_time:
            errors['start_time'] = ['Start time is required.']
        
        end_time = request.data.get('end_time')
        if not end_time:
            errors['end_time'] = ['End time is required.']
        
        # Validate end_time > start_time
        if start_time and end_time and end_time <= start_time:
            errors['end_time'] = ['End time must be after start time.']
        
        route_ids = request.data.get('route_ids', [])
        if not isinstance(route_ids, list):
            errors['route_ids'] = ['Route IDs must be an array.']
        else:
            # Validate all routes exist
            for rid in route_ids:
                route = execute_query_one(
                    "SELECT route_id FROM routes WHERE route_id = %s",
                    [rid]
                )
                if not route:
                    errors['route_ids'] = [f'Route with ID {rid} does not exist.']
                    break
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get optional fields
        message_ur = request.data.get('message_ur')
        created_by = request.user.id if request.user.is_authenticated else None
        
        # Parse datetime strings for MySQL
        start_time_parsed = parse_datetime(start_time)
        end_time_parsed = parse_datetime(end_time)
        
        # Insert the announcement
        announcement_id = execute_insert(
            """
            INSERT INTO announcements 
            (title, message, message_ur, severity, start_time, end_time, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [title, message, message_ur, severity, start_time_parsed, end_time_parsed, created_by]
        )
        
        # Insert route associations
        for rid in route_ids:
            execute_insert(
                """
                INSERT INTO announcement_routes (announcement_id, route_id)
                VALUES (%s, %s)
                """,
                [announcement_id, rid]
            )
        
        # Fetch the created announcement
        announcement = execute_query_one(
            """
            SELECT a.announcement_id, a.title, a.message, a.message_ur,
                   a.severity, a.start_time, a.end_time,
                   a.created_by, a.created_at, a.updated_at,
                   u.email as created_by_email
            FROM announcements a
            LEFT JOIN api_usermodel u ON a.created_by = u.id
            WHERE a.announcement_id = %s
            """,
            [announcement_id]
        )
        
        return Response(format_announcement_response(announcement), status=status.HTTP_201_CREATED)


class AnnouncementDetailView(APIView):
    """
    GET /api/announcements/{id}/ - Get announcement details
    PATCH /api/announcements/{id}/ - Update announcement
    DELETE /api/announcements/{id}/ - Delete announcement
    """
    
    def get(self, request, announcement_id):
        announcement = execute_query_one(
            """
            SELECT a.announcement_id, a.title, a.message, a.message_ur,
                   a.severity, a.start_time, a.end_time,
                   a.created_by, a.created_at, a.updated_at,
                   u.email as created_by_email
            FROM announcements a
            LEFT JOIN api_usermodel u ON a.created_by = u.id
            WHERE a.announcement_id = %s
            """,
            [announcement_id]
        )
        
        if not announcement:
            return Response(
                {'detail': 'Announcement not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(format_announcement_response(announcement), status=status.HTTP_200_OK)
    
    def patch(self, request, announcement_id):
        # Check if announcement exists
        existing = execute_query_one(
            "SELECT announcement_id FROM announcements WHERE announcement_id = %s",
            [announcement_id]
        )
        if not existing:
            return Response(
                {'detail': 'Announcement not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build update query dynamically
        updates = []
        params = []
        errors = {}
        
        if 'title' in request.data:
            title = request.data['title']
            if not title or len(str(title).strip()) < 2:
                errors['title'] = ['Title must be at least 2 characters.']
            else:
                updates.append("title = %s")
                params.append(title)
        
        if 'message' in request.data:
            updates.append("message = %s")
            params.append(request.data['message'])
        
        if 'message_ur' in request.data:
            updates.append("message_ur = %s")
            params.append(request.data['message_ur'])
        
        if 'severity' in request.data:
            severity = request.data['severity']
            if severity not in ['info', 'warning', 'emergency']:
                errors['severity'] = ['"' + str(severity) + '" is not a valid choice.']
            else:
                updates.append("severity = %s")
                params.append(severity)
        
        if 'start_time' in request.data:
            updates.append("start_time = %s")
            params.append(parse_datetime(request.data['start_time']))
        
        if 'end_time' in request.data:
            updates.append("end_time = %s")
            params.append(parse_datetime(request.data['end_time']))
        
        # Handle route_ids update
        if 'route_ids' in request.data:
            route_ids = request.data['route_ids']
            if not isinstance(route_ids, list):
                errors['route_ids'] = ['Route IDs must be an array.']
            else:
                # Validate all routes exist
                for rid in route_ids:
                    route = execute_query_one(
                        "SELECT route_id FROM routes WHERE route_id = %s",
                        [rid]
                    )
                    if not route:
                        errors['route_ids'] = [f'Route with ID {rid} does not exist.']
                        break
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Execute field updates if any
        if updates:
            params.append(announcement_id)
            execute_update(
                f"UPDATE announcements SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE announcement_id = %s",
                params
            )
        
        # Update route associations if provided
        if 'route_ids' in request.data:
            route_ids = request.data['route_ids']
            
            # Delete existing associations
            execute_update(
                "DELETE FROM announcement_routes WHERE announcement_id = %s",
                [announcement_id]
            )
            
            # Insert new associations
            for rid in route_ids:
                execute_insert(
                    """
                    INSERT INTO announcement_routes (announcement_id, route_id)
                    VALUES (%s, %s)
                    """,
                    [announcement_id, rid]
                )
        
        # Return updated announcement
        return self.get(request, announcement_id)
    
    def delete(self, request, announcement_id):
        # Check if announcement exists
        existing = execute_query_one(
            "SELECT announcement_id FROM announcements WHERE announcement_id = %s",
            [announcement_id]
        )
        if not existing:
            return Response(
                {'detail': 'Announcement not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Delete (route associations deleted via CASCADE)
        execute_update("DELETE FROM announcements WHERE announcement_id = %s", [announcement_id])
        
        return Response(status=status.HTTP_204_NO_CONTENT)
