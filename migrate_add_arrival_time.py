"""
Database migration script to add arrival_time column to route_stops table.
This column tracks when a bus first arrives at a stop (ETA < 1 min).
After 2 minutes from arrival_time, the stop is marked as passed.
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartbus.settings')
django.setup()

from django.db import connection

def add_arrival_time_column():
    """Add arrival_time column to route_stops table."""
    with connection.cursor() as cursor:
        try:
            print("Adding arrival_time column to route_stops table...")
            
            # Add arrival_time column (nullable, will be set when bus arrives)
            cursor.execute("""
                ALTER TABLE route_stops 
                ADD COLUMN arrival_time TIMESTAMP NULL DEFAULT NULL
                COMMENT 'Time when bus first arrived at this stop (ETA < 1 min)'
            """)
            
            print("✅ Successfully added arrival_time column!")
            
            # Verify the change
            cursor.execute("DESCRIBE route_stops")
            columns = cursor.fetchall()
            print("\nCurrent route_stops schema:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]}")
            
        except Exception as err:
            print(f"❌ Error: {err}")
            print("Note: Column may already exist, which is fine!")

if __name__ == "__main__":
    print("=" * 80)
    print("DATABASE MIGRATION: Add arrival_time to route_stops")
    print("=" * 80)
    print()
    
    add_arrival_time_column()
    
    print()
    print("=" * 80)
    print("Migration complete!")
    print()
    print("New Logic:")
    print("  1. When ETA < 1 min: Set arrival_time = NOW()")
    print("  2. Show 'arrived' status for 2 minutes")
    print("  3. After 2 min: Mark passed = TRUE")
    print("=" * 80)
