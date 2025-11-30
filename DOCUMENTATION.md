# Smart Bus System - Technical Documentation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Database Schema](#3-database-schema)
4. [Core Modules](#4-core-modules)
5. [API Endpoints](#5-api-endpoints)
6. [MapBox Integration](#6-mapbox-integration)
7. [ETA Calculation System](#7-eta-calculation-system)
8. [Bus Position Tracking](#8-bus-position-tracking)
9. [Display Unit (SMD) System](#9-display-unit-smd-system)
10. [Authentication & Authorization](#10-authentication--authorization)
11. [Configuration](#11-configuration)
12. [Deployment](#12-deployment)

---

## 1. Project Overview

The Smart Bus System is a real-time bus tracking and management platform built with Django REST Framework. It provides APIs for:

- **Real-time bus tracking** with GPS location updates
- **ETA calculations** using MapBox Directions API
- **Route management** with ordered stops
- **Digital signage (SMD)** content delivery for bus stops
- **Advertisement scheduling** across display units
- **Announcement broadcasting** for service alerts

### Tech Stack

| Component | Technology |
|-----------|------------|
| Backend Framework | Django 5.2.7 |
| API Framework | Django REST Framework |
| Database | MySQL |
| Authentication | Token-based (DRF TokenAuthentication) |
| Mapping/Routing | MapBox Directions API |
| Language | Python 3.12 |

### Key Design Decisions

1. **Raw SQL over ORM**: All non-user tables use raw SQL queries for direct database control and educational purposes (Database Systems course project).
2. **MapBox for ETA**: Real road-based distance and time calculations instead of straight-line (Haversine) approximations.
3. **Single Location Record**: Each bus maintains only one location record (upsert pattern) to reduce database size.

---

## 2. Architecture

### Directory Structure

```
Smart-Bus-System/
├── manage.py                 # Django management script
├── smartbus/                 # Django project settings
│   ├── settings.py          # Configuration (DB, MapBox, etc.)
│   ├── urls.py              # Root URL configuration
│   └── wsgi.py              # WSGI application
├── api/                      # Main application
│   ├── models.py            # Django ORM models (UserModel only)
│   ├── serializers.py       # DRF serializers
│   ├── urls.py              # API endpoint routing
│   ├── db.py                # Raw SQL utilities
│   ├── mapbox.py            # MapBox API integration
│   ├── views.py             # Authentication views
│   ├── views_dashboard.py   # Dashboard statistics
│   ├── views_buses.py       # Bus management
│   ├── views_stops.py       # Stop management
│   ├── views_routes.py      # Route management
│   ├── views_etas.py        # ETA calculations
│   ├── views_displays.py    # Display unit management
│   ├── views_advertisements.py    # Ad management
│   ├── views_ad_schedules.py      # Ad scheduling
│   ├── views_announcements.py     # Announcements
│   └── management/
│       └── commands/
│           └── setup_database.py  # SQL table creation
└── README.md                 # API documentation for frontend
```

### Request Flow

```
Client Request
      │
      ▼
┌─────────────┐
│  urls.py    │  Route matching
└─────┬───────┘
      │
      ▼
┌─────────────┐
│  views_*.py │  Business logic
└─────┬───────┘
      │
      ▼
┌─────────────┐     ┌─────────────┐
│   db.py     │────▶│   MySQL     │
└─────────────┘     └─────────────┘
      │
      ▼
┌─────────────┐
│ mapbox.py   │────▶ MapBox API (for ETA)
└─────────────┘
```

---

## 3. Database Schema

### Entity Relationship Diagram

```
┌──────────────┐       ┌───────────────┐       ┌──────────────┐
│    routes    │◄──────│  route_stops  │──────▶│    stops     │
└──────┬───────┘       └───────────────┘       └──────┬───────┘
       │                                              │
       │                                              │
       ▼                                              ▼
┌──────────────┐       ┌───────────────┐       ┌──────────────┐
│    buses     │──────▶│ bus_locations │       │display_units │
└──────────────┘       └───────────────┘       └──────┬───────┘
                                                      │
                                                      ▼
┌──────────────┐       ┌───────────────┐       ┌──────────────┐
│advertisements│◄──────│  ad_schedule  │──────▶│(display_units)│
└──────────────┘       └───────────────┘       └──────────────┘

┌──────────────┐       ┌────────────────────┐
│announcements │◄──────│announcement_routes │
└──────────────┘       └────────────────────┘
```

### Table Definitions

#### `routes`
| Column | Type | Description |
|--------|------|-------------|
| route_id | INT (PK) | Auto-increment primary key |
| route_name | VARCHAR(100) | Unique route name |
| route_code | VARCHAR(20) | Unique route code (e.g., "R-11") |
| description | TEXT | Optional description |
| color | VARCHAR(7) | Hex color for UI (default: #3B82F6) |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

#### `stops`
| Column | Type | Description |
|--------|------|-------------|
| stop_id | INT (PK) | Auto-increment primary key |
| stop_name | VARCHAR(100) | Stop name |
| description | TEXT | Optional description |
| latitude | DECIMAL(10,8) | GPS latitude |
| longitude | DECIMAL(11,8) | GPS longitude |
| is_active | BOOLEAN | Soft delete flag |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

#### `route_stops` (Junction Table)
| Column | Type | Description |
|--------|------|-------------|
| route_stop_id | INT (PK) | Auto-increment primary key |
| route_id | INT (FK) | Reference to routes |
| stop_id | INT (FK) | Reference to stops |
| sequence_number | INT | Order of stop on route |
| distance_from_prev_meters | INT | Distance from previous stop |

#### `buses`
| Column | Type | Description |
|--------|------|-------------|
| bus_id | INT (PK) | Auto-increment primary key |
| registration_number | VARCHAR(20) | Unique registration (e.g., "ISB-1142") |
| capacity | INT | Passenger capacity |
| status | ENUM | 'active', 'inactive', 'maintenance' |
| route_id | INT (FK) | Currently assigned route |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

#### `bus_locations`
| Column | Type | Description |
|--------|------|-------------|
| location_id | INT (PK) | Auto-increment primary key |
| bus_id | INT (FK, UNIQUE) | One row per bus |
| latitude | DECIMAL(10,8) | Current GPS latitude |
| longitude | DECIMAL(11,8) | Current GPS longitude |
| speed | DECIMAL(5,2) | Current speed in km/h |
| heading | DECIMAL(5,2) | Direction (0-360 degrees) |
| current_stop_sequence | INT | Which stop bus is at/heading to |
| recorded_at | TIMESTAMP | Last update time |

#### `display_units`
| Column | Type | Description |
|--------|------|-------------|
| display_id | INT (PK) | Auto-increment primary key |
| display_name | VARCHAR(100) | Display name |
| stop_id | INT (FK) | Stop where display is installed |
| location | VARCHAR(255) | Physical location description |
| status | ENUM | 'online', 'offline', 'error' |
| last_heartbeat | TIMESTAMP | Last heartbeat received |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

#### `announcements`
| Column | Type | Description |
|--------|------|-------------|
| announcement_id | INT (PK) | Auto-increment primary key |
| title | VARCHAR(200) | Announcement title |
| message | TEXT | Message in English |
| message_ur | TEXT | Message in Urdu (optional) |
| severity | ENUM | 'info', 'warning', 'emergency' |
| start_time | DATETIME | When to start showing |
| end_time | DATETIME | When to stop showing |
| created_by | BIGINT (FK) | User who created it |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

#### `announcement_routes` (Junction Table)
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Auto-increment primary key |
| announcement_id | INT (FK) | Reference to announcements |
| route_id | INT (FK) | Reference to routes |

#### `advertisements`
| Column | Type | Description |
|--------|------|-------------|
| ad_id | INT (PK) | Auto-increment primary key |
| title | VARCHAR(100) | Ad title |
| content_url | VARCHAR(500) | Media URL |
| media_type | ENUM | 'image', 'youtube' |
| duration_sec | INT | Display duration in seconds |
| advertiser_name | VARCHAR(100) | Advertiser name |
| advertiser_contact | VARCHAR(100) | Contact info |
| metadata | JSON | Additional data |
| is_active | BOOLEAN | Active flag |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

#### `ad_schedule`
| Column | Type | Description |
|--------|------|-------------|
| schedule_id | INT (PK) | Auto-increment primary key |
| ad_id | INT (FK) | Reference to advertisements |
| display_id | INT (FK) | Reference to display_units |
| priority | INT | Display priority (higher = more important) |
| start_time | DATETIME | Schedule start |
| end_time | DATETIME | Schedule end |
| created_at | TIMESTAMP | Creation timestamp |

---

## 4. Core Modules

### 4.1 Database Utilities (`api/db.py`)

This module provides raw SQL execution functions, bypassing Django ORM.

#### Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `parse_datetime(dt_string)` | Converts ISO 8601 datetime to MySQL format | `str` (YYYY-MM-DD HH:MM:SS) |
| `dictfetchall(cursor)` | Fetches all rows as list of dicts | `List[Dict]` |
| `dictfetchone(cursor)` | Fetches one row as dict | `Dict` or `None` |
| `execute_query(sql, params)` | Executes SELECT, returns all rows | `List[Dict]` |
| `execute_query_one(sql, params)` | Executes SELECT, returns one row | `Dict` or `None` |
| `execute_insert(sql, params)` | Executes INSERT, returns new ID | `int` |
| `execute_update(sql, params)` | Executes UPDATE/DELETE, returns affected rows | `int` |
| `execute_many(sql, params_list)` | Executes same query with multiple params | `int` |

#### Example Usage

```python
from api.db import execute_query, execute_insert

# SELECT
buses = execute_query(
    "SELECT * FROM buses WHERE status = %s",
    ['active']
)

# INSERT
new_id = execute_insert(
    "INSERT INTO stops (stop_name, latitude, longitude) VALUES (%s, %s, %s)",
    ['New Stop', 33.6844, 73.0479]
)
```

### 4.2 MapBox Integration (`api/mapbox.py`)

This module handles all interactions with MapBox APIs for routing and ETA calculations.

#### Configuration

```python
# settings.py
MAPBOX_ACCESS_TOKEN = 'your-mapbox-access-token-here'
```

#### Functions

| Function | MapBox API Used | Description |
|----------|-----------------|-------------|
| `get_access_token()` | - | Retrieves token from Django settings |
| `get_route_info(origin, destination, profile)` | Directions API | Gets distance/duration between two points |
| `get_multi_stop_route(waypoints, profile)` | Directions API | Gets route info for multiple waypoints |
| `get_eta_to_stop(bus_location, stop_location)` | Directions API | Calculates ETA from bus to stop |
| `get_etas_to_multiple_stops(bus_location, stop_locations)` | Directions API | Calculates ETAs to multiple stops |
| `get_bus_position_on_route(bus_location, route_stops)` | Directions API | Determines bus position on route |
| `has_bus_passed_stop(bus_location, stop_location, next_stop_location)` | Directions API | Checks if bus passed a stop |
| `haversine_distance(lat1, lon1, lat2, lon2)` | - | Fallback straight-line distance |
| `fallback_eta(lat1, lon1, lat2, lon2, speed_kmh)` | - | Fallback ETA when MapBox fails |

#### MapBox API Details

**Base URL**: `https://api.mapbox.com/directions/v5/mapbox`

**Routing Profile**: `driving-traffic` (accounts for real-time traffic)

**Request Format**:
```
GET /directions/v5/mapbox/driving-traffic/{lon1},{lat1};{lon2},{lat2}
    ?access_token={token}
    &geometries=geojson
    &overview=simplified
```

**Response Used**:
```json
{
  "code": "Ok",
  "routes": [{
    "distance": 1234,      // meters
    "duration": 300,       // seconds
    "legs": [...]          // for multi-waypoint
  }]
}
```

---

## 5. API Endpoints

### 5.1 Authentication Views (`api/views.py`)

#### `RegisterView`
- **Endpoint**: `POST /api/register/`
- **Permission**: Admin only
- **Function**: Creates new user account
- **Uses**: Django ORM (UserModel)

#### `LoginView`
- **Endpoint**: `POST /api/login/`
- **Permission**: Public (no auth required)
- **Function**: Authenticates user, returns token
- **Uses**: Django `authenticate()`, Token model

#### `UserDetailView`
- **Endpoint**: `GET /api/me/`
- **Permission**: Authenticated users
- **Function**: Returns current user's profile

#### `UserListView`
- **Endpoint**: `GET /api/users/`
- **Permission**: Admin only
- **Function**: Lists all users

---

### 5.2 Dashboard Views (`api/views_dashboard.py`)

#### `DashboardStatsView`
- **Endpoint**: `GET /api/dashboard/stats/`
- **Permission**: Authenticated users
- **Function**: Returns aggregated statistics

**SQL Queries Used**:
```sql
-- Bus counts by status
SELECT status, COUNT(*) as count FROM buses GROUP BY status

-- Total routes
SELECT COUNT(*) as total FROM routes

-- Active stops
SELECT COUNT(*) as total FROM stops WHERE is_active = TRUE

-- Display status counts
SELECT status, COUNT(*) as count FROM display_units GROUP BY status

-- Active announcements
SELECT COUNT(*) as total FROM announcements 
WHERE NOW() BETWEEN start_time AND end_time

-- Active ads
SELECT COUNT(DISTINCT a.ad_id) as total 
FROM advertisements a
JOIN ad_schedule s ON a.ad_id = s.ad_id
WHERE a.is_active = TRUE AND NOW() BETWEEN s.start_time AND s.end_time
```

---

### 5.3 Bus Views (`api/views_buses.py`)

#### `BusListView`
- **Endpoint**: `GET /api/buses/`, `POST /api/buses/`
- **GET**: Lists all buses with optional filters (status, route_id, search)
- **POST**: Creates new bus (Admin only)

**Helper Function**: `format_bus_response(bus, include_route_stops=False)`
- Formats raw SQL result into API response
- Optionally includes route stops with sequence

#### `BusDetailView`
- **Endpoint**: `GET/PATCH/DELETE /api/buses/{id}/`
- **GET**: Returns bus details with current location
- **PATCH**: Updates bus fields (Admin only)
- **DELETE**: Deletes bus (Admin only)

#### `BusLocationView`
- **Endpoint**: `POST /api/buses/{id}/location/`
- **Function**: Updates bus GPS location
- **Critical Logic**: Determines `current_stop_sequence` using MapBox

**Location Update Flow**:
```
1. Receive GPS coordinates (latitude, longitude, speed, heading)
2. Validate bus exists and is active
3. Get all stops on bus's route
4. Call get_bus_position_on_route() with bus location and stops
5. MapBox calculates road distance to each stop
6. Determine if bus is at a stop (within 150m) or between stops
7. Set current_stop_sequence accordingly
8. Upsert into bus_locations table
```

**SQL (Upsert Pattern)**:
```sql
INSERT INTO bus_locations 
(bus_id, latitude, longitude, speed, heading, current_stop_sequence, recorded_at)
VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
ON DUPLICATE KEY UPDATE
    latitude = VALUES(latitude),
    longitude = VALUES(longitude),
    speed = VALUES(speed),
    heading = VALUES(heading),
    current_stop_sequence = VALUES(current_stop_sequence),
    recorded_at = CURRENT_TIMESTAMP
```

#### `BusStartTripView`
- **Endpoint**: `POST /api/buses/{id}/start-trip/`
- **Function**: Sets bus status to 'active'

#### `BusEndTripView`
- **Endpoint**: `POST /api/buses/{id}/end-trip/`
- **Function**: Sets bus status to 'inactive'

#### `ActiveBusesView`
- **Endpoint**: `GET /api/buses/active/`
- **Function**: Returns all active buses with locations (for map display)

---

### 5.4 Stop Views (`api/views_stops.py`)

#### `StopListView`
- **Endpoint**: `GET /api/stops/`, `POST /api/stops/`
- **GET**: Lists all active stops, searchable by name
- **POST**: Creates new stop (Admin only)

**Validation**:
- name: Required, min 2 characters
- latitude: Required, -90 to 90
- longitude: Required, -180 to 180

#### `StopDetailView`
- **Endpoint**: `GET/PATCH/DELETE /api/stops/{id}/`
- **GET**: Returns stop details
- **PATCH**: Updates stop (Admin only)
- **DELETE**: Soft deletes stop (sets is_active=FALSE)

---

### 5.5 Route Views (`api/views_routes.py`)

#### `RouteListView`
- **Endpoint**: `GET /api/routes/`, `POST /api/routes/`
- **GET**: Lists routes with optional search and stop count
- **POST**: Creates route (Admin only)

#### `RouteDetailView`
- **Endpoint**: `GET/PATCH/DELETE /api/routes/{id}/`
- **GET**: Returns route with ordered stops
- **PATCH**: Updates route (Admin only)
- **DELETE**: Deletes route (Admin only)

#### `RouteStopsView`
- **Endpoint**: `GET /api/routes/{id}/stops/`, `POST /api/routes/{id}/stops/`
- **GET**: Lists stops on route in sequence order
- **POST**: Adds stop to route with auto-calculated sequence

**Auto-Sequence Logic**:
```python
# Get current max sequence
max_seq = execute_query_one(
    "SELECT MAX(sequence_number) as max_seq FROM route_stops WHERE route_id = %s",
    [route_id]
)
next_sequence = (max_seq['max_seq'] or 0) + 1
```

#### `RouteStopDetailView`
- **Endpoint**: `DELETE /api/routes/{id}/stops/{route_stop_id}/`
- **Function**: Removes stop from route

#### `RouteStopsReorderView`
- **Endpoint**: `PUT /api/routes/{id}/stops/reorder/`
- **Function**: Reorders stops on a route

**Request Format**:
```json
{
  "stop_order": [3, 1, 2]  // New order of stop IDs
}
```

**Implementation**:
```python
for index, stop_id in enumerate(stop_order, start=1):
    execute_update(
        "UPDATE route_stops SET sequence_number = %s WHERE route_id = %s AND stop_id = %s",
        [index, route_id, stop_id]
    )
```

---

### 5.6 ETA Views (`api/views_etas.py`)

#### `StopETAsView`
- **Endpoint**: `GET /api/stops/{stop_id}/etas/`
- **Function**: Returns ETAs for all buses approaching a stop
- **Query Params**: `route_id` (optional filter)

**Algorithm**:
```
1. Get stop coordinates
2. Find all routes that include this stop
3. Get stop's sequence number on each route
4. Find all active buses on those routes
5. For each bus:
   a. Check if bus_sequence > stop_sequence (already passed) → skip
   b. Call get_eta_to_stop(bus_location, stop_location) via MapBox
   c. If distance ≤ 150m → arrival_status = "arrived"
   d. If ETA ≤ 1 min → arrival_status = "arriving"
   e. If ETA ≤ 3 min → arrival_status = "approaching"
   f. Otherwise → arrival_status = "on-route"
6. Sort by ETA ascending
7. Return results
```

**Arrival Status Values**:
| Status | Condition |
|--------|-----------|
| `arrived` | Distance ≤ 150m |
| `arriving` | ETA ≤ 1 minute |
| `approaching` | ETA ≤ 3 minutes |
| `on-route` | ETA > 3 minutes |

#### `RouteETAsView`
- **Endpoint**: `GET /api/routes/{route_id}/etas/`
- **Function**: Returns ETAs for all buses on a route to upcoming stops

**Algorithm**:
```
1. Get route info and all stops in sequence
2. Get all active buses on this route
3. For each bus:
   a. Get bus location and current_stop_sequence
   b. Filter stops to only those ahead (sequence > current)
   c. Call get_etas_to_multiple_stops() via MapBox
   d. Returns cumulative ETA/distance to each upcoming stop
4. Return results grouped by bus
```

---

### 5.7 Display Views (`api/views_displays.py`)

#### `DisplayListView`
- **Endpoint**: `GET /api/displays/`, `POST /api/displays/`
- **GET**: Lists display units with filters (status, stop_id, search)
- **POST**: Creates display unit (Admin only)

#### `DisplayDetailView`
- **Endpoint**: `GET/PATCH/DELETE /api/displays/{id}/`
- **Standard CRUD operations**

#### `DisplayHeartbeatView`
- **Endpoint**: `POST /api/displays/{id}/heartbeat/`
- **Function**: Records heartbeat from SMD device
- **Updates**: `status` and `last_heartbeat` fields

#### `DisplayContentView`
- **Endpoint**: `GET /api/displays/{id}/content/`
- **Function**: Returns all content for SMD screen

**Response Structure**:
```json
{
  "display": { "id": 1, "name": "...", "stop_id": 5 },
  "stop": { "id": 5, "name": "...", "latitude": ..., "longitude": ... },
  "upcoming_buses": [
    {
      "bus_id": 3,
      "registration_number": "ISB-1142",
      "route_name": "...",
      "eta_minutes": 5,
      "distance_meters": 1200,
      "arrival_status": "approaching"
    }
  ],
  "announcements": [
    {
      "id": 1,
      "title": "Service Alert",
      "message": "...",
      "severity": "warning"
    }
  ],
  "advertisements": [
    {
      "id": 5,
      "title": "Ad Title",
      "content_url": "...",
      "duration_seconds": 10,
      "priority": 1
    }
  ],
  "timestamp": "2025-11-30T12:05:00"
}
```

**Content Aggregation Logic**:

1. **Upcoming Buses**: Same logic as StopETAsView
2. **Announcements**: 
   ```sql
   SELECT * FROM announcements a
   LEFT JOIN announcement_routes ar ON a.announcement_id = ar.announcement_id
   WHERE NOW() BETWEEN a.start_time AND a.end_time
   AND (ar.route_id IN (routes_at_stop) OR ar.route_id IS NULL)
   ```
3. **Advertisements**:
   ```sql
   SELECT * FROM advertisements a
   JOIN ad_schedule s ON a.ad_id = s.ad_id
   WHERE s.display_id = %s
   AND a.is_active = TRUE
   AND NOW() BETWEEN s.start_time AND s.end_time
   ORDER BY s.priority DESC
   ```

---

### 5.8 Advertisement Views (`api/views_advertisements.py`)

#### `AdvertisementListView`
- **Endpoint**: `GET /api/advertisements/`, `POST /api/advertisements/`
- **GET**: Lists ads with filters (is_active, media_type, search)
- **POST**: Creates advertisement

#### `AdvertisementDetailView`
- **Endpoint**: `GET/PATCH/DELETE /api/advertisements/{id}/`
- **Standard CRUD operations**

---

### 5.9 Ad Schedule Views (`api/views_ad_schedules.py`)

#### `AdScheduleListView`
- **Endpoint**: `GET /api/ad-schedules/`, `POST /api/ad-schedules/`
- **GET**: Lists schedules with filters (ad_id, display_id, active)
- **POST**: Creates schedule (supports multiple displays)

**Multi-Display Support**:
```json
{
  "ad_id": 1,
  "display_ids": [1, 2, 3],
  "priority": 1,
  "start_time": "2025-12-01T08:00:00",
  "end_time": "2025-12-31T20:00:00"
}
```

#### `AdScheduleDetailView`
- **Endpoint**: `GET/PATCH/DELETE /api/ad-schedules/{id}/`
- **Standard CRUD operations**

---

### 5.10 Announcement Views (`api/views_announcements.py`)

#### `AnnouncementListView`
- **Endpoint**: `GET /api/announcements/`, `POST /api/announcements/`
- **GET**: Lists announcements with filters (severity, active, route_id)
- **POST**: Creates announcement (with optional route targeting)

**Route Targeting**:
```json
{
  "title": "Service Alert",
  "message": "Route R-11 delayed",
  "severity": "warning",
  "start_time": "2025-11-30T08:00:00",
  "end_time": "2025-11-30T20:00:00",
  "route_ids": [1, 2]  // Only show on these routes
}
```

If `route_ids` is empty or omitted, announcement shows globally.

#### `AnnouncementDetailView`
- **Endpoint**: `GET/PATCH/DELETE /api/announcements/{id}/`
- **Standard CRUD operations**

---

## 6. MapBox Integration

### API Used

**MapBox Directions API v5**

- **Documentation**: https://docs.mapbox.com/api/navigation/directions/
- **Pricing**: 100,000 free requests/month, then $0.50 per 1,000

### Request Pattern

```python
# api/mapbox.py - get_route_info()

url = f"https://api.mapbox.com/directions/v5/mapbox/driving-traffic/{lon1},{lat1};{lon2},{lat2}"
params = {
    'access_token': MAPBOX_ACCESS_TOKEN,
    'geometries': 'geojson',
    'overview': 'simplified'
}
response = requests.get(url, params=params, timeout=10)
```

### Coordinate Format

**Important**: MapBox uses `(longitude, latitude)` format, not `(latitude, longitude)`.

```python
# Correct
bus_location = (73.0479, 33.6844)  # (lon, lat)

# Wrong
bus_location = (33.6844, 73.0479)  # (lat, lon) - DON'T DO THIS
```

### Routing Profiles

| Profile | Use Case |
|---------|----------|
| `driving-traffic` | Default, accounts for real-time traffic |
| `driving` | Standard driving without traffic |
| `walking` | Pedestrian routing |
| `cycling` | Bicycle routing |

### Error Handling

```python
try:
    result = get_eta_to_stop(bus_location, stop_location)
    if result is None:
        # MapBox failed, use fallback
        result = fallback_eta(lat1, lon1, lat2, lon2, speed_kmh=25)
except Exception as e:
    logger.error(f"MapBox error: {e}")
    result = fallback_eta(...)
```

### Fallback System

When MapBox API fails (network error, rate limit, invalid token):

1. **Haversine Distance**: Calculate straight-line distance
2. **30% Buffer**: Multiply by 1.3 to approximate road distance
3. **Speed Assumption**: Use 25 km/h for city bus

```python
def fallback_eta(lat1, lon1, lat2, lon2, speed_kmh=25):
    distance = haversine_distance(lat1, lon1, lat2, lon2)
    adjusted_distance = distance * 1.3  # Road distance buffer
    eta_minutes = (adjusted_distance / 1000) / speed_kmh * 60
    return {
        'eta_minutes': round(eta_minutes, 1),
        'distance_meters': round(adjusted_distance)
    }
```

---

## 7. ETA Calculation System

### Overview

The ETA system calculates how long until a bus reaches a stop using real road distances and traffic conditions via MapBox.

### Calculation Flow

```
┌─────────────────┐
│ Bus GPS Update  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ get_bus_position_on_route()         │
│ - Calculate road distance to stops  │
│ - Determine current_stop_sequence   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Store in bus_locations table        │
│ current_stop_sequence = N           │
└─────────────────────────────────────┘

         ... Later, when ETA requested ...

┌─────────────────┐
│ ETA API Request │
│ /stops/5/etas/  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Filter buses where                  │
│ current_stop_sequence <= 5          │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ For each bus:                       │
│ get_eta_to_stop(bus_loc, stop_loc)  │
│ Returns: distance_meters, eta_mins  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Determine arrival_status:           │
│ ≤150m = arrived                     │
│ ≤1min = arriving                    │
│ ≤3min = approaching                 │
│ >3min = on-route                    │
└─────────────────────────────────────┘
```

### Key Functions

#### `get_eta_to_stop(bus_location, stop_location)`

Calculates ETA from bus to a single stop.

**Input**:
- `bus_location`: `(longitude, latitude)` tuple
- `stop_location`: `(longitude, latitude)` tuple

**Output**:
```python
{
    'eta_minutes': 5.2,      # Minutes to arrival
    'distance_meters': 1500  # Road distance in meters
}
```

**MapBox Request**:
```
GET /directions/v5/mapbox/driving-traffic/73.0479,33.6844;73.0152,33.6985
```

#### `get_etas_to_multiple_stops(bus_location, stop_locations)`

Calculates cumulative ETAs from bus to multiple upcoming stops.

**Input**:
- `bus_location`: `(longitude, latitude)` tuple
- `stop_locations`: List of `(lon, lat, stop_id, stop_name)` tuples

**Output**:
```python
[
    {'stop_id': 5, 'stop_name': 'F-10', 'eta_minutes': 5.2, 'distance_meters': 1500},
    {'stop_id': 6, 'stop_name': 'F-11', 'eta_minutes': 12.0, 'distance_meters': 3500},
    {'stop_id': 7, 'stop_name': 'G-9', 'eta_minutes': 18.5, 'distance_meters': 5200}
]
```

**MapBox Request** (single call for all waypoints):
```
GET /directions/v5/mapbox/driving-traffic/73.0479,33.6844;73.0152,33.6985;73.0250,33.7100;73.0300,33.7200
```

### Accuracy Considerations

1. **Traffic Awareness**: Using `driving-traffic` profile provides real-time traffic data
2. **Road Network**: MapBox routes along actual roads, not straight lines
3. **Update Frequency**: ETA recalculated on each API request (real-time)
4. **Fallback**: If MapBox fails, Haversine + 30% buffer provides reasonable estimate

---

## 8. Bus Position Tracking

### Overview

The system tracks which stop a bus is at or heading toward using the `current_stop_sequence` field in `bus_locations`.

### Position Detection Algorithm

```python
# api/mapbox.py - get_bus_position_on_route()

def get_bus_position_on_route(bus_location, route_stops):
    """
    Determines bus position on route using MapBox road distances.
    
    Returns:
        - current_stop_sequence: Which stop to store in DB
        - is_at_stop: True if within 150m of a stop
        - next_stop: Sequence of next upcoming stop
        - distance_to_next: Meters to next stop
        - eta_to_next: Minutes to next stop
    """
```

### State Machine

```
                    ┌─────────────────┐
                    │   Start Trip    │
                    │ sequence = 1    │
                    └────────┬────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │     APPROACHING STOP N       │
              │  sequence = N                │
              │  is_at_stop = False          │
              └──────────────┬───────────────┘
                             │
                             │ distance ≤ 150m
                             ▼
              ┌──────────────────────────────┐
              │       AT STOP N              │
              │  sequence = N                │
              │  is_at_stop = True           │
              └──────────────┬───────────────┘
                             │
                             │ distance > 150m AND
                             │ closer to stop N+1
                             ▼
              ┌──────────────────────────────┐
              │   DEPARTED, HEADING TO N+1   │
              │  sequence = N+1              │
              │  is_at_stop = False          │
              └──────────────┬───────────────┘
                             │
                             │ Repeat until last stop
                             ▼
              ┌──────────────────────────────┐
              │       END OF ROUTE           │
              │  sequence = last             │
              └──────────────────────────────┘
```

### Detection Logic

```python
# Threshold for "at stop" detection
AT_STOP_THRESHOLD = 150  # meters (road distance)

# For each stop, calculate road distance from bus
stop_distances = []
for stop in route_stops:
    result = get_eta_to_stop(bus_location, (stop['longitude'], stop['latitude']))
    stop_distances.append({
        'sequence': stop['sequence'],
        'distance': result['distance_meters']
    })

# Find nearest stop
nearest = min(stop_distances, key=lambda x: x['distance'])

if nearest['distance'] <= AT_STOP_THRESHOLD:
    # Bus is AT this stop
    return {'current_stop_sequence': nearest['sequence'], 'is_at_stop': True}
else:
    # Bus is between stops - use triangulation
    # Compare distance to previous vs next stop
    ...
```

### Why 150m Threshold?

- **100m is too tight**: GPS drift, bus stopping positions vary
- **200m is too loose**: Might mark "arrived" while still on road
- **150m balances**: Accounts for GPS accuracy (~10-20m) + stop area size

### Display Filtering Logic

When a display requests content (`/api/displays/{id}/content/`):

```python
# Only show buses that haven't passed this stop
if bus_sequence > stop_sequence:
    continue  # Bus already passed, don't show

# Calculate real-time ETA for remaining buses
eta_result = get_eta_to_stop(bus_location, stop_location)

# Set arrival status
if eta_result['distance_meters'] <= 150:
    arrival_status = 'arrived'  # Bus is at the stop
elif eta_result['eta_minutes'] <= 1:
    arrival_status = 'arriving'
elif eta_result['eta_minutes'] <= 3:
    arrival_status = 'approaching'
else:
    arrival_status = 'on-route'
```

---

## 9. Display Unit (SMD) System

### Overview

Display Units are digital signage screens installed at bus stops. They show:
- Upcoming bus arrivals with ETAs
- Service announcements
- Advertisements

### Heartbeat System

Displays periodically send heartbeat to report their status:

```
POST /api/displays/{id}/heartbeat/
{
    "status": "online"  // or "error"
}
```

**Server Response**:
```json
{
    "id": 1,
    "status": "online",
    "last_heartbeat": "2025-11-30T12:00:00",
    "message": "Heartbeat recorded"
}
```

### Content Delivery

Displays fetch content via:
```
GET /api/displays/{id}/content/
```

**Polling Recommendation**: Every 10-30 seconds

### Content Priority

1. **Emergency Announcements** (severity='emergency')
2. **Bus Arrivals** (sorted by ETA)
3. **Warning Announcements** (severity='warning')
4. **Advertisements** (sorted by priority)
5. **Info Announcements** (severity='info')

### Advertisement Scheduling

Ads are scheduled per-display with:
- **Start/End Time**: When ad should run
- **Priority**: Higher priority shows first
- **Duration**: How long to display (in seconds)

---

## 10. Authentication & Authorization

### Token Authentication

All API requests (except login) require Bearer token:

```
Authorization: Token abc123def456...
```

### User Types

| Type | Permissions |
|------|-------------|
| `ADMIN` | Full access - CRUD all resources |
| `OPERATOR` | Read all, Update buses/displays |
| `VIEWER` | Read-only access |

### Permission Checks

```python
# In views
def is_admin(user):
    return user.user_type == 'ADMIN'

# Usage
if not is_admin(request.user):
    return Response(
        {'error': 'Only admins can perform this action.'},
        status=status.HTTP_403_FORBIDDEN
    )
```

### Protected Endpoints

| Action | Required Role |
|--------|---------------|
| Create/Update/Delete Bus | ADMIN |
| Create/Update/Delete Route | ADMIN |
| Create/Update/Delete Stop | ADMIN |
| Create/Update Display | ADMIN |
| Update Bus Location | OPERATOR+ |
| Create Advertisement | Any authenticated |
| View any resource | Any authenticated |

---

## 11. Configuration

### Django Settings (`smartbus/settings.py`)

```python
# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'busdb',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}

# MapBox
MAPBOX_ACCESS_TOKEN = 'pk.your_mapbox_token_here'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# CORS (for frontend)
CORS_ALLOW_ALL_ORIGINS = True  # Restrict in production
```

### Environment Variables (Recommended for Production)

```python
import os

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
MAPBOX_ACCESS_TOKEN = os.environ.get('MAPBOX_ACCESS_TOKEN')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}
```

---

## 12. Deployment

### Setup Steps

1. **Clone Repository**
   ```bash
   git clone https://github.com/iPythonezta/Smart-Bus-System.git
   cd Smart-Bus-System
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Install Dependencies**
   ```bash
   pip install django djangorestframework mysqlclient django-cors-headers requests
   ```

4. **Configure Database**
   - Create MySQL database: `CREATE DATABASE busdb;`
   - Update `settings.py` with credentials

5. **Run Migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create Raw SQL Tables**
   ```bash
   python manage.py setup_database
   ```

7. **Create Admin User**
   ```bash
   python manage.py createsuperuser
   ```

8. **Run Server**
   ```bash
   python manage.py runserver
   ```

### Production Checklist

- [ ] Set `DEBUG = False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use environment variables for secrets
- [ ] Set up proper CORS origins
- [ ] Use HTTPS
- [ ] Configure proper logging
- [ ] Set up database backups
- [ ] Monitor MapBox API usage

---

## Appendix

### A. API Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (successful delete) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 500 | Internal Server Error |

### B. Common SQL Patterns

**Upsert (Insert or Update)**:
```sql
INSERT INTO table (col1, col2) VALUES (%s, %s)
ON DUPLICATE KEY UPDATE col2 = VALUES(col2)
```

**Soft Delete**:
```sql
UPDATE table SET is_active = FALSE WHERE id = %s
-- Then filter: WHERE is_active = TRUE
```

**Junction Table Insert**:
```sql
INSERT INTO route_stops (route_id, stop_id, sequence_number)
VALUES (%s, %s, %s)
```

### C. Haversine Formula

```python
from math import radians, sin, cos, sqrt, atan2

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth's radius in meters
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c  # Distance in meters
```

### D. Glossary

| Term | Definition |
|------|------------|
| SMD | Surface-Mounted Display (digital signage at bus stops) |
| ETA | Estimated Time of Arrival |
| Heartbeat | Periodic status update from display unit |
| Sequence | Order number of a stop on a route |
| Upsert | Insert if not exists, update if exists |
| Junction Table | Table linking two entities (many-to-many) |

---

*Documentation generated for Smart Bus System v1.0*
*Last updated: November 30, 2025*
