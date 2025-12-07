# Bus Stop Sequence Logic - Complete Documentation

## 🎯 Core Principles

### Three Unbreakable Rules:
1. **Monotonic Progression**: `current_stop_sequence` can ONLY increase, never decrease
2. **One Visit Per Stop**: Each stop can only be visited ONCE per trip
3. **Forward Progress Only**: Once a bus passes stop N, it can never show as being at/before stop N again

---

## 🔄 Complete Flow

### 1. Trip Start
**Endpoint**: `POST /api/buses/{id}/start-trip/`

**Actions**:
```sql
-- Set bus to active
UPDATE buses SET status = 'active', route_id = X

-- Reset sequence to 0 (beginning of route)
UPDATE bus_locations SET current_stop_sequence = 0
```

**Result**: Bus is at sequence 0, ready to approach first stop

---

### 2. GPS Location Updates
**Endpoint**: `POST /api/buses/{id}/location/`

**Process**:
```python
1. Receive GPS coordinates (lat, lon)
2. Get current_stop_sequence from database (e.g., currently at 3)
3. Get all route stops
4. Call get_bus_position_on_route(bus_location, route_stops, stop_seq=3)
5. MapBox calculates distances to all stops >= 3
6. Determine new sequence (3, 4, 5, etc. - NEVER 2, 1, 0)
7. Update database with new sequence
```

---

### 3. Position Detection Algorithm

#### Input:
- `bus_location`: (longitude, latitude)
- `route_stops`: All stops on route
- `stop_seq`: Current sequence from DB (e.g., 3)

#### Step 1: Filter Stops
```python
for stop in route_stops:
    if stop.sequence < stop_seq:  # Skip stops 1, 2 if stop_seq=3
        continue
    # Only consider stops 3, 4, 5, 6, ...
```

**Why?** Stops 1, 2 are already visited and can't be revisited.

#### Step 2: Calculate Distances
```python
# Use MapBox to get road distance from bus to each remaining stop
stop_distances = [
    {'sequence': 3, 'distance': 500m},
    {'sequence': 4, 'distance': 1200m},
    {'sequence': 5, 'distance': 2800m},
]
```

#### Step 3: Find Nearest Stop
```python
nearest = min(stop_distances, key=lambda x: x['distance'])
# nearest = {'sequence': 3, 'distance': 500m}
```

#### Step 4: Check if AT Stop (within 150m)
```python
AT_STOP_THRESHOLD = 150  # meters

if nearest['distance'] <= 150:
    # Bus is AT this stop
    
    # Guard: Prevent going backwards
    if nearest['sequence'] < stop_seq:
        return stop_seq  # Keep current, don't regress
    
    # Mark arrival
    return nearest['sequence']  # e.g., return 3
```

**Scenario**: Bus drives within 150m of stop 3
- **Database Update**: `current_stop_sequence = 3`
- **Display Logic**: Stop 3 shows "Bus Arrived"

#### Step 5: Check if BETWEEN Stops (> 150m from all)
```python
# Bus is 500m from stop 3, 1200m from stop 4
# Heading TOWARD stop 3

if prev_distance > nearest_distance:
    # Bus hasn't reached nearest yet
    return max(nearest['sequence'], stop_seq)  # Return 3
else:
    # Bus PASSED nearest, heading to next
    return max(next_stop['sequence'], stop_seq)  # Return 4
```

**Scenario 1**: Bus is 500m from stop 3 (approaching)
- **Database Update**: `current_stop_sequence = 3` (heading toward 3)
- **Display Logic**: Stop 3 shows "Bus 5 min away"

**Scenario 2**: Bus WAS at stop 3, now 200m past it heading to stop 4
- **Logic**: Bus passed stop 3 boundary (150m)
- **Database Update**: `current_stop_sequence = 4` (jumped to next)
- **Display Logic**: 
  - Stop 3: Bus NOT shown (sequence 4 > 3, filtered out)
  - Stop 4: Shows "Bus Approaching"

---

### 4. Display Filtering
**Endpoint**: `GET /api/displays/{id}/content/`

```python
for bus in active_buses:
    bus_sequence = bus['current_stop_sequence']  # e.g., 4
    stop_sequence = current_stop['sequence']      # e.g., 3
    
    if bus_sequence > stop_sequence:
        continue  # Skip - bus already passed this stop
    
    # Show bus (it's at or approaching this stop)
```

**Example**:
- Bus at sequence 4, approaching stop 4
- Display at stop 3: `4 > 3` → DON'T SHOW ✅
- Display at stop 4: `4 == 4` → SHOW "Arriving" ✅
- Display at stop 5: `4 < 5` → SHOW "On route" ✅

---

## 🔍 Edge Cases Handled

### Case 1: GPS Drift (Bus appears to move backwards)
```python
# Bus is at sequence 5, GPS glitches and shows near stop 3
if nearest['sequence'] < stop_seq:  # 3 < 5
    return stop_seq  # Keep at 5, ignore false reading
```

### Case 2: Bus Doesn't Stop (Drives Past Without Stopping)
```python
# Bus at sequence 3, drives past stop 3 (151m+), heading to stop 4
# Distance check shows: stop 3 is BEHIND, stop 4 is AHEAD
return next_stop['sequence']  # Jump from 3 to 4
```

**Effect**: Stop 3 will never show this bus again (correctly skipped)

### Case 3: End of Route
```python
# Bus at sequence 10 (last stop), no more stops left
if not stop_distances:
    return stop_seq  # Keep at 10, can't progress further
```

### Case 4: Trip Restart
```python
# Bus completes route, driver clicks "Start Trip" again
# BusStartTripView resets: current_stop_sequence = 0
# All stops become available again for new trip
```

---

## 📊 State Transition Diagram

```
Start Trip
   ↓
sequence = 0
   ↓
GPS Update → MapBox → Within 150m of Stop 1? 
   ↓ Yes                              ↓ No
sequence = 1                    sequence = 1 (approaching)
"At Stop 1"                     "5 min to Stop 1"
   ↓
Leaves Stop 1 (> 150m)
   ↓
sequence = 2 (heading to Stop 2)
   ↓
GPS Update → Within 150m of Stop 2?
   ↓ Yes
sequence = 2
"At Stop 2"
   ↓
... continues until end of route
```

---

## ✅ Guarantees

| Guarantee | How It's Enforced |
|-----------|-------------------|
| Stop visited once | `if stop["sequence"] < stop_seq: continue` filters out visited stops |
| Sequence only increases | `return max(new_seq, stop_seq)` in all branches |
| No backwards movement | `if nearest['sequence'] < stop_seq: return stop_seq` |
| Clean trip restart | `BusStartTripView` sets sequence = 0 |
| MapBox failure handled | Haversine fallback calculation |
| Empty stops handled | Returns current sequence if no stops left |

---

## 🐛 Testing Checklist

- [ ] Bus starts trip → sequence = 0
- [ ] Bus approaches stop 1 → sequence = 1
- [ ] Bus arrives at stop 1 (< 150m) → sequence = 1, is_at_stop = True
- [ ] Bus departs stop 1 (> 150m) → sequence = 2
- [ ] Bus can't regress to stop 1 after leaving
- [ ] Display at stop 1 hides bus after it passes
- [ ] Bus completes route → sequence stays at last stop
- [ ] New trip restart → sequence resets to 0

---

## 🔧 Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `AT_STOP_THRESHOLD` | 150m | Distance to consider "at stop" |
| `MapBox Profile` | driving-traffic | Real-time traffic routing |
| `Fallback Buffer` | 30% | Haversine to road distance adjustment |
| `Default Speed` | 25 km/h | Fallback ETA calculation |

---

**Last Updated**: December 7, 2025
**Status**: Production Ready ✅
