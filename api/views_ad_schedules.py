"""
Ad Schedule API views using raw SQL queries.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one, execute_insert, execute_update, parse_datetime
from .views_advertisements import format_ad_response
import json


def format_schedule_response(schedule, ad=None):
    """Format an ad schedule record into API response format."""
    response = {
        'id': schedule['schedule_id'],
        'ad_id': schedule['ad_id'],
        'display_id': schedule['display_id'],
        'display_name': schedule.get('display_name'),
        'start_time': schedule['start_time'].isoformat() if schedule.get('start_time') else None,
        'end_time': schedule['end_time'].isoformat() if schedule.get('end_time') else None,
        'priority': schedule['priority'],
        'created_at': schedule['created_at'].isoformat() if schedule.get('created_at') else None,
    }
    
    # Add related ad object if available
    if ad:
        response['ad'] = format_ad_response(ad)
    elif schedule.get('ad_title'):
        # Ad data from JOIN (3NF schema with nested advertiser)
        metadata = schedule.get('ad_metadata')
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = None
        
        response['ad'] = {
            'id': schedule['ad_id'],
            'title': schedule['ad_title'],
            'content_url': schedule['ad_content_url'],
            'media_type': schedule['ad_media_type'],
            'duration_seconds': schedule['ad_duration_sec'],
            'advertiser': {
                'id': schedule.get('advertiser_id'),
                'name': schedule.get('advertiser_name'),
                'contact_phone': schedule.get('advertiser_phone'),
                'contact_email': schedule.get('advertiser_email'),
            },
            'metadata': metadata,
            'created_at': schedule['ad_created_at'].isoformat() if schedule.get('ad_created_at') else None,
            'updated_at': schedule['ad_updated_at'].isoformat() if schedule.get('ad_updated_at') else None,
        }
    
    return response


class AdScheduleListView(APIView):
    """
    GET /api/ad-schedules/ - List all ad schedules
    POST /api/ad-schedules/ - Create new ad schedule(s)
    """
    
    def get(self, request):
        # Get query parameters
        ad_id = request.query_params.get('ad_id')
        display_id = request.query_params.get('display_id')
        active = request.query_params.get('active')
        
        # Build query with filters (3NF schema - JOIN with advertisers table)
        sql = """
            SELECT 
                s.schedule_id, s.ad_id, s.display_id, s.priority,
                s.start_time, s.end_time, s.created_at,
                d.display_name,
                a.title as ad_title,
                a.content_url as ad_content_url,
                a.media_type as ad_media_type,
                a.duration_sec as ad_duration_sec,
                a.metadata as ad_metadata,
                a.created_at as ad_created_at,
                a.updated_at as ad_updated_at,
                adv.advertiser_id,
                adv.advertiser_name,
                adv.contact_phone as advertiser_phone,
                adv.contact_email as advertiser_email
            FROM ad_schedule s
            JOIN advertisements a ON s.ad_id = a.ad_id
            JOIN advertisers adv ON a.advertiser_id = adv.advertiser_id
            JOIN display_units d ON s.display_id = d.display_id
            WHERE 1=1
        """
        params = []
        
        if ad_id:
            sql += " AND s.ad_id = %s"
            params.append(ad_id)
        
        if display_id:
            sql += " AND s.display_id = %s"
            params.append(display_id)
        
        if active and active.lower() == 'true':
            sql += " AND NOW() BETWEEN s.start_time AND s.end_time"
        
        sql += " ORDER BY s.schedule_id DESC"
        
        schedules = execute_query(sql, params)
        
        return Response([format_schedule_response(s) for s in schedules], status=status.HTTP_200_OK)
    
    def post(self, request):
        # Validate required fields
        errors = {}
        
        ad_id = request.data.get('ad_id')
        if not ad_id:
            errors['ad_id'] = ['Ad ID is required.']
        else:
            # Validate ad exists
            ad = execute_query_one(
                "SELECT ad_id FROM advertisements WHERE ad_id = %s",
                [ad_id]
            )
            if not ad:
                errors['ad_id'] = ['Advertisement with this ID does not exist.']
        
        display_ids = request.data.get('display_ids')
        if not display_ids or not isinstance(display_ids, list) or len(display_ids) == 0:
            errors['display_ids'] = ['Display IDs array is required.']
        else:
            # Validate all displays exist
            for did in display_ids:
                display = execute_query_one(
                    "SELECT display_id FROM display_units WHERE display_id = %s",
                    [did]
                )
                if not display:
                    errors['display_ids'] = [f'Display with ID {did} does not exist.']
                    break
        
        start_time = request.data.get('start_time')
        if not start_time:
            errors['start_time'] = ['Start time is required.']
        
        end_time = request.data.get('end_time')
        if not end_time:
            errors['end_time'] = ['End time is required.']
        
        # Validate end_time > start_time
        if start_time and end_time and end_time <= start_time:
            errors['end_time'] = ['End time must be after start time.']
        
        priority = request.data.get('priority', 1)
        if not isinstance(priority, int) or priority < 0:
            errors['priority'] = ['Priority must be a non-negative integer.']
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse datetime strings for MySQL
        start_time_parsed = parse_datetime(start_time)
        end_time_parsed = parse_datetime(end_time)
        
        # Create schedule for each display
        created_schedules = []
        
        for did in display_ids:
            schedule_id = execute_insert(
                """
                INSERT INTO ad_schedule (ad_id, display_id, start_time, end_time, priority)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [ad_id, did, start_time_parsed, end_time_parsed, priority]
            )
            
            # Fetch the created schedule with related data (3NF schema)
            schedule = execute_query_one(
                """
                SELECT 
                    s.schedule_id, s.ad_id, s.display_id, s.priority,
                    s.start_time, s.end_time, s.created_at,
                    d.display_name,
                    a.title as ad_title,
                    a.content_url as ad_content_url,
                    a.media_type as ad_media_type,
                    a.duration_sec as ad_duration_sec,
                    a.metadata as ad_metadata,
                    a.created_at as ad_created_at,
                    a.updated_at as ad_updated_at,
                    adv.advertiser_id,
                    adv.advertiser_name,
                    adv.contact_phone as advertiser_phone,
                    adv.contact_email as advertiser_email
                FROM ad_schedule s
                JOIN advertisements a ON s.ad_id = a.ad_id
                JOIN advertisers adv ON a.advertiser_id = adv.advertiser_id
                JOIN display_units d ON s.display_id = d.display_id
                WHERE s.schedule_id = %s
                """,
                [schedule_id]
            )
            
            created_schedules.append(format_schedule_response(schedule))
        
        return Response(created_schedules, status=status.HTTP_201_CREATED)


class AdScheduleDetailView(APIView):
    """
    GET /api/ad-schedules/{id}/ - Get ad schedule details
    PATCH /api/ad-schedules/{id}/ - Update ad schedule
    DELETE /api/ad-schedules/{id}/ - Delete ad schedule
    """
    
    def get(self, request, schedule_id):
        schedule = execute_query_one(
            """
            SELECT 
                s.schedule_id, s.ad_id, s.display_id, s.priority,
                s.start_time, s.end_time, s.created_at,
                d.display_name,
                a.title as ad_title,
                a.content_url as ad_content_url,
                a.media_type as ad_media_type,
                a.duration_sec as ad_duration_sec,
                a.metadata as ad_metadata,
                a.created_at as ad_created_at,
                a.updated_at as ad_updated_at,
                adv.advertiser_id,
                adv.advertiser_name,
                adv.contact_phone as advertiser_phone,
                adv.contact_email as advertiser_email
            FROM ad_schedule s
            JOIN advertisements a ON s.ad_id = a.ad_id
            JOIN advertisers adv ON a.advertiser_id = adv.advertiser_id
            JOIN display_units d ON s.display_id = d.display_id
            WHERE s.schedule_id = %s
            """,
            [schedule_id]
        )
        
        if not schedule:
            return Response(
                {'detail': 'Ad schedule not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(format_schedule_response(schedule), status=status.HTTP_200_OK)
    
    def patch(self, request, schedule_id):
        # Check if schedule exists
        existing = execute_query_one(
            "SELECT schedule_id FROM ad_schedule WHERE schedule_id = %s",
            [schedule_id]
        )
        if not existing:
            return Response(
                {'detail': 'Ad schedule not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build update query dynamically
        updates = []
        params = []
        errors = {}
        
        if 'ad_id' in request.data:
            ad_id = request.data['ad_id']
            ad = execute_query_one(
                "SELECT ad_id FROM advertisements WHERE ad_id = %s",
                [ad_id]
            )
            if not ad:
                errors['ad_id'] = ['Advertisement with this ID does not exist.']
            else:
                updates.append("ad_id = %s")
                params.append(ad_id)
        
        if 'display_id' in request.data:
            display_id = request.data['display_id']
            display = execute_query_one(
                "SELECT display_id FROM display_units WHERE display_id = %s",
                [display_id]
            )
            if not display:
                errors['display_id'] = ['Display with this ID does not exist.']
            else:
                updates.append("display_id = %s")
                params.append(display_id)
        
        if 'start_time' in request.data:
            updates.append("start_time = %s")
            params.append(parse_datetime(request.data['start_time']))
        
        if 'end_time' in request.data:
            updates.append("end_time = %s")
            params.append(parse_datetime(request.data['end_time']))
        
        if 'priority' in request.data:
            priority = request.data['priority']
            if not isinstance(priority, int) or priority < 0:
                errors['priority'] = ['Priority must be a non-negative integer.']
            else:
                updates.append("priority = %s")
                params.append(priority)
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        if not updates:
            return Response(
                {'detail': 'No valid fields to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute update
        params.append(schedule_id)
        execute_update(
            f"UPDATE ad_schedule SET {', '.join(updates)} WHERE schedule_id = %s",
            params
        )
        
        # Return updated schedule
        return self.get(request, schedule_id)
    
    def delete(self, request, schedule_id):
        # Check if schedule exists
        existing = execute_query_one(
            "SELECT schedule_id FROM ad_schedule WHERE schedule_id = %s",
            [schedule_id]
        )
        if not existing:
            return Response(
                {'detail': 'Ad schedule not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        execute_update("DELETE FROM ad_schedule WHERE schedule_id = %s", [schedule_id])
        
        return Response(status=status.HTTP_204_NO_CONTENT)
