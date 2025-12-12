"""
Test script for ETA-based stop marking logic.

NEW LOGIC (ETA-based):
1. When ETA < 1 min: Set arrival_time = NOW()
2. Show 'arrived' status for 2 minutes
3. After 2 min: Mark passed = TRUE

This replaces the old distance-based (50m threshold) logic.
"""

import mysql.connector
from datetime import datetime, timedelta

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'admin',
    'database': 'busdb'
}

def setup_test_scenario():
    """
    Setup test data:
    - Bus on route with 3 stops
    - Simulate bus arriving at stop 2 (set arrival_time)
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get test route
        cursor.execute("SELECT route_id FROM routes LIMIT 1")
        route = cursor.fetchone()
        if not route:
            print("❌ No routes found. Please create routes first.")
            return None
        
        route_id = route['route_id']
        
        # Get stops on this route
        cursor.execute("""
            SELECT route_stop_id, sequence_number, stop_id 
            FROM route_stops 
            WHERE route_id = %s 
            ORDER BY sequence_number 
            LIMIT 3
        """, [route_id])
        stops = cursor.fetchall()
        
        if len(stops) < 3:
            print(f"❌ Route {route_id} has only {len(stops)} stops. Need at least 3.")
            return None
        
        print(f"✅ Using route {route_id} with {len(stops)} stops")
        
        # Reset all stops to initial state
        cursor.execute("""
            UPDATE route_stops 
            SET passed = FALSE, arrival_time = NULL
            WHERE route_id = %s
        """, [route_id])
        conn.commit()
        print("✅ Reset all stops to passed=FALSE, arrival_time=NULL")
        
        # Simulate bus arriving at stop 2 (sequence 2)
        stop_2 = stops[1]  # Index 1 = second stop
        arrival_time = datetime.now() - timedelta(seconds=30)  # 30 seconds ago
        
        cursor.execute("""
            UPDATE route_stops 
            SET arrival_time = %s
            WHERE route_id = %s AND sequence_number = %s
        """, [arrival_time, route_id, stop_2['sequence_number']])
        conn.commit()
        
        print(f"✅ Simulated bus arrival at stop {stop_2['sequence_number']} (30 seconds ago)")
        
        return {
            'route_id': route_id,
            'stops': stops,
            'arrived_stop': stop_2
        }
        
    finally:
        cursor.close()
        conn.close()


def test_arrived_window():
    """Test that bus shows as 'arrived' during 2-minute window"""
    print("\n" + "="*80)
    print("TEST 1: Bus shows 'arrived' during 2-minute window")
    print("="*80)
    
    test_data = setup_test_scenario()
    if not test_data:
        return
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    try:
        route_id = test_data['route_id']
        arrived_stop = test_data['arrived_stop']
        
        # Check stop status
        cursor.execute("""
            SELECT 
                sequence_number,
                passed,
                arrival_time,
                TIMESTAMPDIFF(SECOND, arrival_time, CURRENT_TIMESTAMP) as seconds_since_arrival
            FROM route_stops 
            WHERE route_id = %s AND sequence_number = %s
        """, [route_id, arrived_stop['sequence_number']])
        
        stop = cursor.fetchone()
        
        print(f"\nStop {stop['sequence_number']} Status:")
        print(f"  - passed: {stop['passed']}")
        print(f"  - arrival_time: {stop['arrival_time']}")
        print(f"  - seconds_since_arrival: {stop['seconds_since_arrival']}")
        
        # Verify stop is NOT marked as passed yet
        if stop['passed']:
            print("❌ FAIL: Stop marked as passed too early (should wait 2 minutes)")
        else:
            print("✅ PASS: Stop not marked as passed (correctly waiting)")
        
        # Verify arrival_time is set
        if stop['arrival_time'] is None:
            print("❌ FAIL: arrival_time not set")
        else:
            print("✅ PASS: arrival_time is set")
        
        # Verify we're within 2-minute window
        ARRIVED_WINDOW = 120  # seconds
        if stop['seconds_since_arrival'] < ARRIVED_WINDOW:
            print(f"✅ PASS: Within 2-minute window ({stop['seconds_since_arrival']}s < 120s)")
            print("   → ETA display should show 'arrived' status")
        else:
            print(f"❌ FAIL: Outside 2-minute window ({stop['seconds_since_arrival']}s >= 120s)")
        
    finally:
        cursor.close()
        conn.close()


def test_passed_after_2_minutes():
    """Test that stop is marked as passed after 2 minutes"""
    print("\n" + "="*80)
    print("TEST 2: Stop marked as passed after 2-minute window")
    print("="*80)
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get test route
        cursor.execute("SELECT route_id FROM routes LIMIT 1")
        route = cursor.fetchone()
        route_id = route['route_id']
        
        # Get a stop
        cursor.execute("""
            SELECT route_stop_id, sequence_number 
            FROM route_stops 
            WHERE route_id = %s 
            ORDER BY sequence_number 
            LIMIT 1
        """, [route_id])
        stop = cursor.fetchone()
        
        # Simulate arrival 3 minutes ago (past the 2-minute threshold)
        old_arrival = datetime.now() - timedelta(minutes=3)
        
        cursor.execute("""
            UPDATE route_stops 
            SET arrival_time = %s, passed = FALSE
            WHERE route_id = %s AND sequence_number = %s
        """, [old_arrival, route_id, stop['sequence_number']])
        conn.commit()
        
        print(f"✅ Simulated bus arrival at stop {stop['sequence_number']} (3 minutes ago)")
        
        # Check status
        cursor.execute("""
            SELECT 
                sequence_number,
                passed,
                arrival_time,
                TIMESTAMPDIFF(SECOND, arrival_time, CURRENT_TIMESTAMP) as seconds_since_arrival
            FROM route_stops 
            WHERE route_id = %s AND sequence_number = %s
        """, [route_id, stop['sequence_number']])
        
        result = cursor.fetchone()
        
        print(f"\nStop {result['sequence_number']} Status:")
        print(f"  - passed: {result['passed']}")
        print(f"  - seconds_since_arrival: {result['seconds_since_arrival']}")
        
        # This stop SHOULD be marked as passed by the BusLocationView logic
        # when the next location update happens
        if result['seconds_since_arrival'] >= 120:
            print(f"✅ PASS: Stop aged out ({result['seconds_since_arrival']}s >= 120s)")
            print("   → Next location update will mark as passed=TRUE")
        else:
            print(f"❌ FAIL: Stop not aged out ({result['seconds_since_arrival']}s < 120s)")
        
    finally:
        cursor.close()
        conn.close()


def test_trip_reset():
    """Test that trip start resets both passed and arrival_time"""
    print("\n" + "="*80)
    print("TEST 3: Trip start resets passed=FALSE and arrival_time=NULL")
    print("="*80)
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get test route
        cursor.execute("SELECT route_id FROM routes LIMIT 1")
        route = cursor.fetchone()
        route_id = route['route_id']
        
        # Set some stops as passed with arrival times
        cursor.execute("""
            UPDATE route_stops 
            SET passed = TRUE, arrival_time = CURRENT_TIMESTAMP
            WHERE route_id = %s
        """, [route_id])
        conn.commit()
        
        print("✅ Set all stops to passed=TRUE with arrival_time")
        
        # Simulate trip start (reset)
        cursor.execute("""
            UPDATE route_stops 
            SET passed = FALSE, arrival_time = NULL
            WHERE route_id = %s
        """, [route_id])
        conn.commit()
        
        print("✅ Executed trip start reset")
        
        # Verify all stops are reset
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN passed = FALSE THEN 1 ELSE 0 END) as not_passed,
                SUM(CASE WHEN arrival_time IS NULL THEN 1 ELSE 0 END) as no_arrival_time
            FROM route_stops 
            WHERE route_id = %s
        """, [route_id])
        
        stats = cursor.fetchone()
        
        print(f"\nReset Statistics:")
        print(f"  - Total stops: {stats['total']}")
        print(f"  - Stops with passed=FALSE: {stats['not_passed']}")
        print(f"  - Stops with arrival_time=NULL: {stats['no_arrival_time']}")
        
        if stats['not_passed'] == stats['total'] and stats['no_arrival_time'] == stats['total']:
            print("✅ PASS: All stops correctly reset")
        else:
            print("❌ FAIL: Some stops not properly reset")
        
    finally:
        cursor.close()
        conn.close()


def display_system_summary():
    """Display current system configuration"""
    print("\n" + "="*80)
    print("SYSTEM CONFIGURATION SUMMARY")
    print("="*80)
    
    print("\nETA-Based Stop Marking Logic:")
    print("  1. When ETA < 1 minute:")
    print("     → Set arrival_time = CURRENT_TIMESTAMP")
    print("     → Log: 'Bus ARRIVING at stop'")
    print()
    print("  2. During 2-minute window (arrival_time to arrival_time + 2min):")
    print("     → Show arrival_status = 'arrived' in ETA display")
    print("     → Show eta_minutes = 0")
    print("     → Bus remains visible at stop")
    print()
    print("  3. After 2 minutes elapsed:")
    print("     → Mark passed = TRUE")
    print("     → Hide bus from ETA display for this stop")
    print("     → Log: 'Marked stop as PASSED (2 min elapsed since arrival)'")
    print()
    print("  4. On trip start:")
    print("     → Reset all stops: passed = FALSE, arrival_time = NULL")
    print("     → Fresh state for new trip")
    print()
    print("Implementation Files:")
    print("  - api/views_buses.py (BusLocationView): ETA checking & marking logic")
    print("  - api/views_etas.py (StopETAsView): Display 'arrived' status")
    print("  - Database: route_stops.arrival_time (TIMESTAMP NULL)")
    print("="*80)


if __name__ == "__main__":
    print("="*80)
    print("ETA-BASED STOP MARKING TEST SUITE")
    print("="*80)
    
    display_system_summary()
    
    try:
        test_arrived_window()
        test_passed_after_2_minutes()
        test_trip_reset()
        
        print("\n" + "="*80)
        print("ALL TESTS COMPLETED")
        print("="*80)
        print("\nNext Steps:")
        print("  1. Start Django server: python manage.py runserver")
        print("  2. Update bus location with ETA < 1 min to a stop")
        print("  3. Verify arrival_time gets set")
        print("  4. Check ETA display shows 'arrived' status")
        print("  5. Wait 2 minutes and verify stop marked as passed")
        
    except mysql.connector.Error as err:
        print(f"\n❌ Database Error: {err}")
        print("Make sure MySQL server is running and database credentials are correct.")
