"""
Advertisement API views using raw SQL queries.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one, execute_insert, execute_update
import json


def format_ad_response(ad):
    """Format an advertisement record into API response format."""
    metadata = ad.get('metadata')
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = None
    
    # Format advertiser object (3NF structure)
    advertiser = {
        'id': ad.get('advertiser_id'),
        'name': ad.get('advertiser_name'),
        'contact_phone': ad.get('contact_phone'),
        'contact_email': ad.get('contact_email')
    }
    
    return {
        'id': ad['ad_id'],
        'title': ad['title'],
        'content_url': ad['content_url'],
        'media_type': ad['media_type'],
        'duration_seconds': ad['duration_sec'],
        'advertiser': advertiser,  # Nested advertiser object (3NF)
        'metadata': metadata,
        'created_at': ad['created_at'].isoformat() if ad.get('created_at') else None,
        'updated_at': ad['updated_at'].isoformat() if ad.get('updated_at') else None,
    }


class AdvertisementListView(APIView):
    """
    GET /api/advertisements/ - List all advertisements
    POST /api/advertisements/ - Create a new advertisement
    """
    
    def get(self, request):
        # Get query parameters
        search = request.query_params.get('search')
        media_type = request.query_params.get('media_type')
        advertiser_id = request.query_params.get('advertiser_id')
        
        # Build query with JOIN to get advertiser details (3NF)
        sql = """
            SELECT 
                a.ad_id, a.title, a.content_url, a.media_type, a.duration_sec,
                a.advertiser_id, a.metadata, a.created_at, a.updated_at,
                adv.advertiser_name, adv.contact_phone, adv.contact_email
            FROM advertisements a
            JOIN advertisers adv ON a.advertiser_id = adv.advertiser_id
            WHERE 1=1
        """
        params = []
        
        if search:
            sql += " AND (a.title LIKE %s OR adv.advertiser_name LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        if media_type and media_type in ['image', 'youtube']:
            sql += " AND a.media_type = %s"
            params.append(media_type)
        
        if advertiser_id:
            sql += " AND a.advertiser_id = %s"
            params.append(advertiser_id)
        
        sql += " ORDER BY a.ad_id DESC"
        
        ads = execute_query(sql, params)
        
        return Response([format_ad_response(ad) for ad in ads], status=status.HTTP_200_OK)
    
    def post(self, request):
        # Validate required fields
        errors = {}
        
        title = request.data.get('title')
        if not title or len(str(title).strip()) < 2:
            errors['title'] = ['Title is required and must be at least 2 characters.']
        
        content_url = request.data.get('content_url')
        if not content_url:
            errors['content_url'] = ['Content URL is required.']
        
        media_type = request.data.get('media_type')
        if not media_type:
            errors['media_type'] = ['Media type is required.']
        elif media_type not in ['image', 'youtube']:
            errors['media_type'] = ['"' + str(media_type) + '" is not a valid choice.']
        
        duration_seconds = request.data.get('duration_seconds')
        if duration_seconds is None:
            errors['duration_seconds'] = ['Duration is required.']
        elif not isinstance(duration_seconds, int) or duration_seconds < 1:
            errors['duration_seconds'] = ['Duration must be a positive integer.']
        
        # 3NF Change: Use advertiser_id instead of advertiser_name
        advertiser_id = request.data.get('advertiser_id')
        if not advertiser_id:
            errors['advertiser_id'] = ['Advertiser ID is required.']
        else:
            # Verify advertiser exists
            advertiser = execute_query_one(
                "SELECT advertiser_id FROM advertisers WHERE advertiser_id = %s",
                [advertiser_id]
            )
            if not advertiser:
                errors['advertiser_id'] = ['Advertiser with this ID does not exist.']
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get optional fields
        metadata = request.data.get('metadata')
        
        # Convert metadata to JSON string if provided
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Insert the advertisement (3NF schema)
        ad_id = execute_insert(
            """
            INSERT INTO advertisements 
            (title, content_url, media_type, duration_sec, advertiser_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [title, content_url, media_type, duration_seconds, advertiser_id, metadata_json]
        )
        
        # Fetch the created advertisement with advertiser details
        ad = execute_query_one(
            """
            SELECT 
                a.ad_id, a.title, a.content_url, a.media_type, a.duration_sec,
                a.advertiser_id, a.metadata, a.created_at, a.updated_at,
                adv.advertiser_name, adv.contact_phone, adv.contact_email
            FROM advertisements a
            JOIN advertisers adv ON a.advertiser_id = adv.advertiser_id
            WHERE a.ad_id = %s
            """,
            [ad_id]
        )
        
        return Response(format_ad_response(ad), status=status.HTTP_201_CREATED)


class AdvertisementDetailView(APIView):
    """
    GET /api/advertisements/{id}/ - Get advertisement details
    PATCH /api/advertisements/{id}/ - Update advertisement
    DELETE /api/advertisements/{id}/ - Delete advertisement
    """
    
    def get(self, request, ad_id):
        ad = execute_query_one(
            """
            SELECT 
                a.ad_id, a.title, a.content_url, a.media_type, a.duration_sec,
                a.advertiser_id, a.metadata, a.created_at, a.updated_at,
                adv.advertiser_name, adv.contact_phone, adv.contact_email
            FROM advertisements a
            JOIN advertisers adv ON a.advertiser_id = adv.advertiser_id
            WHERE a.ad_id = %s
            """,
            [ad_id]
        )
        
        if not ad:
            return Response(
                {'detail': 'Advertisement not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(format_ad_response(ad), status=status.HTTP_200_OK)
    
    def patch(self, request, ad_id):
        # Check if advertisement exists
        existing = execute_query_one(
            "SELECT ad_id FROM advertisements WHERE ad_id = %s",
            [ad_id]
        )
        if not existing:
            return Response(
                {'detail': 'Advertisement not found'},
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
        
        if 'content_url' in request.data:
            updates.append("content_url = %s")
            params.append(request.data['content_url'])
        
        if 'media_type' in request.data:
            media_type = request.data['media_type']
            if media_type not in ['image', 'youtube']:
                errors['media_type'] = ['"' + str(media_type) + '" is not a valid choice.']
            else:
                updates.append("media_type = %s")
                params.append(media_type)
        
        if 'duration_seconds' in request.data:
            duration = request.data['duration_seconds']
            if not isinstance(duration, int) or duration < 1:
                errors['duration_seconds'] = ['Duration must be a positive integer.']
            else:
                updates.append("duration_sec = %s")
                params.append(duration)
        
        # 3NF Change: Use advertiser_id instead of advertiser_name/contact
        if 'advertiser_id' in request.data:
            advertiser_id = request.data['advertiser_id']
            # Verify advertiser exists
            advertiser = execute_query_one(
                "SELECT advertiser_id FROM advertisers WHERE advertiser_id = %s",
                [advertiser_id]
            )
            if not advertiser:
                errors['advertiser_id'] = ['Advertiser with this ID does not exist.']
            else:
                updates.append("advertiser_id = %s")
                params.append(advertiser_id)
        
        if 'metadata' in request.data:
            metadata = request.data['metadata']
            metadata_json = json.dumps(metadata) if metadata else None
            updates.append("metadata = %s")
            params.append(metadata_json)
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        if not updates:
            return Response(
                {'detail': 'No valid fields to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute update
        params.append(ad_id)
        execute_update(
            f"UPDATE advertisements SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE ad_id = %s",
            params
        )
        
        # Return updated advertisement
        return self.get(request, ad_id)
    
    def delete(self, request, ad_id):
        # Check if advertisement exists
        existing = execute_query_one(
            "SELECT ad_id FROM advertisements WHERE ad_id = %s",
            [ad_id]
        )
        if not existing:
            return Response(
                {'detail': 'Advertisement not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Delete (schedules deleted via CASCADE)
        execute_update("DELETE FROM advertisements WHERE ad_id = %s", [ad_id])
        
        return Response(status=status.HTTP_204_NO_CONTENT)
