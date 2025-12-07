"""
Add 'passed' column to route_stops table
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartbus.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    try:
        cursor.execute("""
            ALTER TABLE route_stops 
            ADD COLUMN passed BOOLEAN DEFAULT FALSE 
            AFTER distance_from_prev_meters
        """)
        print("✅ Successfully added 'passed' column to route_stops table")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("⚠️  Column 'passed' already exists")
        else:
            print(f"❌ Error: {e}")
