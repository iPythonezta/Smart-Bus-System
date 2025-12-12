"""
Database migration script to REMOVE arrival_time column from route_stops table.

SIMPLIFIED LOGIC:
- When ETA < 2 min: Mark stop as passed immediately
- No need for arrival_time tracking or timers!
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartbus.settings')
django.setup()

from django.db import connection

def remove_arrival_time_column():
    """Remove arrival_time column from route_stops table (if it exists)."""
    with connection.cursor() as cursor:
        try:
            # Check if column exists first
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = 'route_stops' 
                  AND COLUMN_NAME = 'arrival_time'
            """)
            exists = cursor.fetchone()[0]
            
            if exists:
                print("Removing arrival_time column from route_stops table...")
                
                # Drop the column
                cursor.execute("""
                    ALTER TABLE route_stops 
                    DROP COLUMN arrival_time
                """)
                
                print("✅ Successfully removed arrival_time column!")
            else:
                print("ℹ️  arrival_time column doesn't exist (already removed or never added)")
            
            # Verify current schema
            cursor.execute("DESCRIBE route_stops")
            columns = cursor.fetchall()
            print("\nCurrent route_stops schema:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]}")
            
        except Exception as err:
            print(f"❌ Error: {err}")

if __name__ == "__main__":
    print("=" * 80)
    print("DATABASE MIGRATION: Remove arrival_time from route_stops")
    print("=" * 80)
    print()
    
    remove_arrival_time_column()
    
    print()
    print("=" * 80)
    print("Migration complete!")
    print()
    print("SIMPLIFIED Logic:")
    print("  When ETA < 2 min: Mark passed = TRUE immediately")
    print("  No timers, no arrival_time tracking needed!")
    print("=" * 80)
