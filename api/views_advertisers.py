"""
Advertiser Management Views
Handles CRUD operations for the advertisers table (3NF normalization)
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .db import execute_query, execute_query_one, execute_insert, execute_update


class AdvertiserListView(APIView):
    """
    GET /api/advertisers/ - List all advertisers (with optional search)
    POST /api/advertisers/ - Create new advertiser
    Admin/Staff only (add authentication middleware as needed)
    """
    
    def get(self, request):
        """List all advertisers with optional search"""
        search = request.GET.get('search', '').strip()
        
        if search:
            query = """
                SELECT 
                    advertiser_id as id,
                    advertiser_name as name,
                    contact_email,
                    contact_phone,
                    address,
                    created_at,
                    updated_at,
                    (SELECT COUNT(*) FROM advertisements WHERE advertiser_id = advertisers.advertiser_id) as ad_count
                FROM advertisers
                WHERE advertiser_name LIKE %s
                   OR contact_email LIKE %s
                   OR contact_phone LIKE %s
                ORDER BY advertiser_name
            """
            advertisers = execute_query(query, [f'%{search}%', f'%{search}%', f'%{search}%'])
        else:
            query = """
                SELECT 
                    advertiser_id as id,
                    advertiser_name as name,
                    contact_email,
                    contact_phone,
                    address,
                    created_at,
                    updated_at,
                    (SELECT COUNT(*) FROM advertisements WHERE advertiser_id = advertisers.advertiser_id) as ad_count
                FROM advertisers
                ORDER BY advertiser_name
            """
            advertisers = execute_query(query)
        
        return Response(advertisers, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create new advertiser"""
        # Extract and validate data
        name = request.data.get('advertiser_name', '').strip()
        email = request.data.get('contact_email', '').strip()
        phone = request.data.get('contact_phone', '').strip()
        address = request.data.get('address', '').strip()
        
        errors = {}
        
        # Validation
        if not name:
            errors['advertiser_name'] = ['Advertiser name is required.']
        elif len(name) < 2:
            errors['advertiser_name'] = ['Advertiser name must be at least 2 characters.']
        
        if email and '@' not in email:
            errors['contact_email'] = ['Invalid email format.']
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if advertiser already exists
        existing = execute_query_one(
            "SELECT advertiser_id FROM advertisers WHERE advertiser_name = %s",
            [name]
        )
        if existing:
            return Response(
                {'advertiser_name': ['An advertiser with this name already exists.']},
                status=status.HTTP_409_CONFLICT
            )
        
        # Insert new advertiser
        try:
            advertiser_id = execute_insert(
                """
                INSERT INTO advertisers (advertiser_name, contact_email, contact_phone, address)
                VALUES (%s, %s, %s, %s)
                """,
                [name, email or None, phone or None, address or None]
            )
            
            # Fetch created advertiser
            advertiser = execute_query_one(
                """
                SELECT 
                    advertiser_id as id,
                    advertiser_name as name,
                    contact_email,
                    contact_phone,
                    address,
                    created_at,
                    updated_at
                FROM advertisers 
                WHERE advertiser_id = %s
                """,
                [advertiser_id]
            )
            
            return Response(advertiser, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {'error': f'Database error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdvertiserDetailView(APIView):
    """
    GET /api/advertisers/{id}/ - Get single advertiser with their ads
    PATCH /api/advertisers/{id}/ - Update advertiser
    DELETE /api/advertisers/{id}/ - Delete advertiser (only if no ads exist)
    Admin/Staff only (add authentication middleware as needed)
    """
    
    def get(self, request, advertiser_id):
        """Get advertiser details with list of their advertisements"""
        # Fetch advertiser
        advertiser = execute_query_one(
            """
            SELECT 
                advertiser_id as id,
                advertiser_name as name,
                contact_email,
                contact_phone,
                address,
                created_at,
                updated_at
            FROM advertisers 
            WHERE advertiser_id = %s
            """,
            [advertiser_id]
        )
        
        if not advertiser:
            return Response(
                {'error': 'Advertiser not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Fetch advertiser's advertisements
        ads = execute_query(
            """
            SELECT 
                ad_id as id,
                title,
                content_url,
                media_type,
                duration_sec,
                is_active,
                created_at,
                updated_at
            FROM advertisements
            WHERE advertiser_id = %s
            ORDER BY created_at DESC
            """,
            [advertiser_id]
        )
        
        advertiser['ads'] = ads
        advertiser['total_ads'] = len(ads)
        advertiser['active_ads'] = len([ad for ad in ads if ad['is_active']])
        
        return Response(advertiser, status=status.HTTP_200_OK)
    
    def patch(self, request, advertiser_id):
        """Update advertiser information"""
        # Check if advertiser exists
        advertiser = execute_query_one(
            "SELECT advertiser_id FROM advertisers WHERE advertiser_id = %s",
            [advertiser_id]
        )
        
        if not advertiser:
            return Response(
                {'error': 'Advertiser not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build dynamic update query
        updates = []
        params = []
        errors = {}
        
        if 'advertiser_name' in request.data:
            name = request.data['advertiser_name'].strip()
            if not name:
                errors['advertiser_name'] = ['Advertiser name cannot be empty.']
            elif len(name) < 2:
                errors['advertiser_name'] = ['Advertiser name must be at least 2 characters.']
            else:
                # Check for duplicate name (excluding current advertiser)
                existing = execute_query_one(
                    "SELECT advertiser_id FROM advertisers WHERE advertiser_name = %s AND advertiser_id != %s",
                    [name, advertiser_id]
                )
                if existing:
                    errors['advertiser_name'] = ['An advertiser with this name already exists.']
                else:
                    updates.append("advertiser_name = %s")
                    params.append(name)
        
        if 'contact_email' in request.data:
            email = request.data['contact_email'].strip()
            if email and '@' not in email:
                errors['contact_email'] = ['Invalid email format.']
            else:
                updates.append("contact_email = %s")
                params.append(email or None)
        
        if 'contact_phone' in request.data:
            updates.append("contact_phone = %s")
            params.append(request.data['contact_phone'].strip() or None)
        
        if 'address' in request.data:
            updates.append("address = %s")
            params.append(request.data['address'].strip() or None)
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        if not updates:
            return Response(
                {'error': 'No valid fields to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute update
        try:
            params.append(advertiser_id)
            query = f"UPDATE advertisers SET {', '.join(updates)} WHERE advertiser_id = %s"
            execute_update(query, params)
            
            # Fetch updated advertiser
            advertiser = execute_query_one(
                """
                SELECT 
                    advertiser_id as id,
                    advertiser_name as name,
                    contact_email,
                    contact_phone,
                    address,
                    created_at,
                    updated_at
                FROM advertisers 
                WHERE advertiser_id = %s
                """,
                [advertiser_id]
            )
            
            return Response(advertiser, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': f'Database error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, advertiser_id):
        """Delete advertiser (only if no advertisements exist)"""
        # Check if advertiser exists
        advertiser = execute_query_one(
            "SELECT advertiser_id FROM advertisers WHERE advertiser_id = %s",
            [advertiser_id]
        )
        
        if not advertiser:
            return Response(
                {'error': 'Advertiser not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if advertiser has any advertisements
        ad_count = execute_query_one(
            "SELECT COUNT(*) as count FROM advertisements WHERE advertiser_id = %s",
            [advertiser_id]
        )
        
        if ad_count and ad_count['count'] > 0:
            return Response(
                {'error': f'Cannot delete advertiser with {ad_count["count"]} active advertisement(s). Please delete or reassign the advertisements first.'},
                status=status.HTTP_409_CONFLICT
            )
        
        # Delete advertiser
        try:
            execute_update(
                "DELETE FROM advertisers WHERE advertiser_id = %s",
                [advertiser_id]
            )
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e:
            return Response(
                {'error': f'Database error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
