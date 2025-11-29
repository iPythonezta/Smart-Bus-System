# Smart Bus Management System API

A Django REST API for managing a smart bus system with real-time tracking, route management, and display unit coordination.

## Getting Started

### Prerequisites
- Python 3.12+
- MySQL Server
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/iPythonezta/Smart-Bus-System.git
cd Smart-Bus-System

# Install dependencies
pip install -r requirements.txt

# Run Django migrations
python manage.py makemigrations
python manage.py migrate

# Setup database tables
python manage.py setup_database

# Create admin user
python manage.py createsuperuser

# Run the server
python manage.py runserver
```

## Authentication

All endpoints (except `/api/login/`) require token authentication.

**Header Format:**
```
Authorization: Token <your_token>
```

---

## API Endpoints

### Authentication

#### Login
```
POST /api/login/
```

**Request:**
```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response:** `200 OK`
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

**Error:** `401 Unauthorized`
```json
{
  "error": "Invalid Credentials"
}
```

---

#### Register User (Admin Only)
```
POST /api/register/
```

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "secure_password",
  "first_name": "John",
  "last_name": "Doe",
  "user_type": "STAFF"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string | Yes | Unique email address |
| password | string | Yes | User password |
| first_name | string | No | First name |
| last_name | string | No | Last name |
| user_type | string | No | `ADMIN` or `STAFF` (default: `STAFF`) |

**Response:** `201 Created`
```json
{
  "token": "new_user_token_here"
}
```

---

#### Get Current User
```
GET /api/me/
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "user_type": "ADMIN"
}
```

---

#### List All Users (Admin Only)
```
GET /api/users/
```

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "email": "admin@example.com",
    "first_name": "Admin",
    "last_name": "User",
    "user_type": "ADMIN"
  },
  {
    "id": 2,
    "email": "staff@example.com",
    "first_name": "Staff",
    "last_name": "Member",
    "user_type": "STAFF"
  }
]
```

---

### Dashboard

#### Get Dashboard Statistics
```
GET /api/dashboard/stats/
```

**Response:** `200 OK`
```json
{
  "total_buses": 25,
  "active_buses": 18,
  "inactive_buses": 5,
  "maintenance_buses": 2,
  "total_routes": 12,
  "total_stops": 45,
  "online_displays": 38,
  "offline_displays": 7,
  "error_displays": 0,
  "active_announcements": 3,
  "active_ads": 15
}
```

---

### Stops

#### List All Stops
```
GET /api/stops/
```

**Query Parameters:**
| Parameter | Description |
|-----------|-------------|
| search | Filter stops by name (partial match) |

**Example:** `GET /api/stops/?search=Blue`

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "name": "Blue Area",
    "description": "Main commercial area",
    "latitude": 33.7077,
    "longitude": 73.0469,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
]
```

---

#### Get Stop Details
```
GET /api/stops/{id}/
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "Blue Area",
  "description": "Main commercial area",
  "latitude": 33.7077,
  "longitude": 73.0469,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

**Error:** `404 Not Found`
```json
{
  "detail": "Stop not found"
}
```

---

#### Create Stop (Admin Only)
```
POST /api/stops/
```

**Request:**
```json
{
  "name": "Faizabad",
  "description": "Major intersection",
  "latitude": 33.6507,
  "longitude": 73.0681
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Stop name (min 2 chars) |
| description | string | No | Stop description |
| latitude | number | Yes | Latitude (-90 to 90) |
| longitude | number | Yes | Longitude (-180 to 180) |

**Response:** `201 Created`
```json
{
  "id": 2,
  "name": "Faizabad",
  "description": "Major intersection",
  "latitude": 33.6507,
  "longitude": 73.0681,
  "created_at": "2024-01-15T11:00:00",
  "updated_at": "2024-01-15T11:00:00"
}
```

---

#### Update Stop (Admin Only)
```
PATCH /api/stops/{id}/
```

**Request:** (all fields optional)
```json
{
  "name": "Faizabad Interchange",
  "description": "Updated description",
  "latitude": 33.6510,
  "longitude": 73.0685
}
```

**Response:** `200 OK` - Returns updated stop object

---

#### Delete Stop (Admin Only)
```
DELETE /api/stops/{id}/
```

**Response:** `204 No Content`

**Error:** `400 Bad Request` (if stop is assigned to routes)
```json
{
  "detail": "Cannot delete stop that is assigned to routes"
}
```

---

### Routes

#### List All Routes
```
GET /api/routes/
```

**Query Parameters:**
| Parameter | Description |
|-----------|-------------|
| search | Filter routes by name or code |

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "name": "Blue Line",
    "code": "BL",
    "description": "Blue Area to Faizabad",
    "color": "#3b82f6",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00",
    "route_stops": [
      {
        "id": 1,
        "route_id": 1,
        "stop_id": 1,
        "sequence_number": 1,
        "distance_from_prev": null,
        "stop": {
          "id": 1,
          "name": "Blue Area",
          "description": "Main commercial area",
          "latitude": 33.7077,
          "longitude": 73.0469,
          "created_at": "2024-01-15T10:30:00",
          "updated_at": "2024-01-15T10:30:00"
        }
      }
    ]
  }
]
```

---

#### Get Route Details
```
GET /api/routes/{id}/
```

**Response:** `200 OK` - Same format as list item with all stops

**Error:** `404 Not Found`
```json
{
  "detail": "Route not found"
}
```

---

#### Create Route (Admin Only)
```
POST /api/routes/
```

**Request:**
```json
{
  "name": "Green Line",
  "code": "GL",
  "description": "Secretariat to Melody",
  "color": "#10b981"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Route name (min 2 chars) |
| code | string | Yes | Route code (2-10 chars, unique) |
| description | string | No | Route description |
| color | string | No | Hex color (default: #3B82F6) |

**Response:** `201 Created`
```json
{
  "id": 2,
  "name": "Green Line",
  "code": "GL",
  "description": "Secretariat to Melody",
  "color": "#10b981",
  "created_at": "2024-01-15T11:00:00",
  "updated_at": "2024-01-15T11:00:00",
  "route_stops": []
}
```

---

#### Update Route (Admin Only)
```
PATCH /api/routes/{id}/
```

**Request:** (all fields optional)
```json
{
  "name": "Green Express Line",
  "code": "GEL",
  "description": "Express service",
  "color": "#059669"
}
```

**Response:** `200 OK` - Returns updated route with stops

---

#### Delete Route (Admin Only)
```
DELETE /api/routes/{id}/
```

**Response:** `204 No Content`

**Error:** `400 Bad Request` (if route has buses assigned)
```json
{
  "detail": "Cannot delete route that has buses assigned"
}
```

---

### Route Stops

#### Add Stop to Route (Admin Only)
```
POST /api/routes/{route_id}/stops/
```

**Request:**
```json
{
  "stop_id": 3,
  "sequence_number": 2
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| stop_id | integer | Yes | ID of the stop to add |
| sequence_number | integer | Yes | Position in route (1-based) |

**Response:** `201 Created`
```json
{
  "id": 5,
  "route_id": 1,
  "stop_id": 3,
  "sequence_number": 2,
  "distance_from_prev": null,
  "stop": {
    "id": 3,
    "name": "Aabpara Market",
    "description": null,
    "latitude": 33.7150,
    "longitude": 73.0550,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
}
```

*Note: Existing stops at or after the sequence number are shifted down automatically.*

---

#### Remove Stop from Route (Admin Only)
```
DELETE /api/routes/{route_id}/stops/{route_stop_id}/
```

**Response:** `204 No Content`

*Note: Remaining stops are re-sequenced automatically.*

---

#### Reorder Route Stops (Admin Only)
```
PUT /api/routes/{route_id}/stops/reorder/
```

**Request:**
```json
{
  "route_stop_ids": [3, 1, 5, 2, 4]
}
```

**Response:** `200 OK`
```json
{
  "message": "Route stops reordered successfully",
  "route_stops": [...]
}
```

**Error:** `400 Bad Request`
```json
{
  "detail": "Invalid route_stop_ids - must include all stops in route"
}
```

---

### Buses

#### List All Buses
```
GET /api/buses/
```

**Query Parameters:**
| Parameter | Description |
|-----------|-------------|
| status | Filter by `active`, `inactive`, or `maintenance` |
| route_id | Filter by assigned route |
| search | Search by registration number |

**Example:** `GET /api/buses/?status=active&search=ABC`

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "registration_number": "ABC-1234",
    "capacity": 50,
    "status": "active",
    "route_id": 2,
    "route": {
      "id": 2,
      "name": "Green Line",
      "code": "GL-01",
      "color": "#22C55E"
    },
    "last_location": {
      "latitude": 31.5204,
      "longitude": 74.3587,
      "speed": 35.5,
      "heading": 180,
      "current_stop_sequence": 3,
      "timestamp": "2025-11-29T10:30:00"
    },
    "created_at": "2025-11-01T00:00:00",
    "updated_at": "2025-11-29T10:30:00"
  }
]
```

---

#### Create Bus (Admin Only)
```
POST /api/buses/
```

**Request:**
```json
{
  "registration_number": "XYZ-5678",
  "capacity": 45,
  "status": "inactive",
  "route_id": 3
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| registration_number | string | Yes | Unique bus registration |
| capacity | integer | No | Seating capacity (default: 50) |
| status | string | No | `active`, `inactive`, `maintenance` (default: `inactive`) |
| route_id | integer | No | Assigned route ID |

**Response:** `201 Created`
```json
{
  "id": 5,
  "registration_number": "XYZ-5678",
  "capacity": 45,
  "status": "inactive",
  "route_id": 3,
  "route": {
    "id": 3,
    "name": "Blue Line",
    "code": "BL-01",
    "color": "#3B82F6"
  },
  "last_location": null,
  "created_at": "2025-11-29T12:00:00",
  "updated_at": "2025-11-29T12:00:00"
}
```

---

#### Get Bus Details
```
GET /api/buses/{id}/
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "registration_number": "ABC-1234",
  "capacity": 50,
  "status": "active",
  "route_id": 2,
  "route": {
    "id": 2,
    "name": "Green Line",
    "code": "GL-01",
    "color": "#22C55E",
    "description": "Main city route",
    "stops": [
      {
        "sequence": 1,
        "stop_id": 5,
        "stop_name": "Central Station",
        "latitude": 31.5200,
        "longitude": 74.3500,
        "distance_from_prev_meters": 0
      },
      {
        "sequence": 2,
        "stop_id": 8,
        "stop_name": "Mall Road",
        "latitude": 31.5300,
        "longitude": 74.3600,
        "distance_from_prev_meters": 1200
      }
    ]
  },
  "last_location": {
    "latitude": 31.5204,
    "longitude": 74.3587,
    "speed": 35.5,
    "heading": 180,
    "current_stop_sequence": 1,
    "timestamp": "2025-11-29T10:30:00"
  },
  "next_stop": {
    "sequence": 2,
    "stop_id": 8,
    "stop_name": "Mall Road",
    "distance_meters": 1200,
    "eta_minutes": 5
  },
  "created_at": "2025-11-01T00:00:00",
  "updated_at": "2025-11-29T10:30:00"
}
```

---

#### Update Bus (Admin Only)
```
PATCH /api/buses/{id}/
```

**Request:** (all fields optional)
```json
{
  "registration_number": "ABC-1234-NEW",
  "capacity": 55,
  "status": "maintenance",
  "route_id": null
}
```

**Response:** `200 OK` - Returns updated bus object

---

#### Delete Bus (Admin Only)
```
DELETE /api/buses/{id}/
```

**Response:** `204 No Content`

---

#### Update Bus Location
```
POST /api/buses/{id}/location/
```

Used by GPS tracking devices to update bus position.

**Request:**
```json
{
  "latitude": 31.5210,
  "longitude": 74.3590,
  "speed": 40.0,
  "heading": 185
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| latitude | decimal | Yes | GPS latitude |
| longitude | decimal | Yes | GPS longitude |
| speed | decimal | No | Speed in km/h (default: 0) |
| heading | decimal | No | Direction in degrees (default: 0) |

**Response:** `201 Created`
```json
{
  "id": 12345,
  "bus_id": 1,
  "latitude": 31.5210,
  "longitude": 74.3590,
  "speed": 40.0,
  "heading": 185,
  "current_stop_sequence": 2,
  "timestamp": "2025-11-29T10:35:00"
}
```

---

#### Start Trip
```
POST /api/buses/{id}/start-trip/
```

**Request:**
```json
{
  "route_id": 2,
  "direction": "outbound",
  "start_stop_sequence": 1
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| route_id | integer | No* | Route ID (*required if bus has no assigned route) |
| direction | string | No | `outbound` or `inbound` (default: `outbound`) |
| start_stop_sequence | integer | No | Starting stop sequence |

**Response:** `200 OK`
```json
{
  "bus_id": 1,
  "status": "active",
  "trip": {
    "id": 45,
    "route_id": 2,
    "direction": "outbound",
    "start_time": "2025-11-29T10:00:00",
    "current_stop_sequence": 1,
    "status": "in-progress"
  },
  "message": "Trip started successfully"
}
```

---

#### End Trip
```
POST /api/buses/{id}/end-trip/
```

**Request:** (optional)
```json
{
  "status": "inactive"
}
```

| Field | Type | Description |
|-------|------|-------------|
| status | string | `inactive` or `maintenance` (default: `inactive`) |

**Response:** `200 OK`
```json
{
  "bus_id": 1,
  "status": "inactive",
  "trip": {
    "id": 45,
    "route_id": 2,
    "direction": "outbound",
    "start_time": "2025-11-29T10:00:00",
    "end_time": "2025-11-29T11:30:00",
    "status": "completed",
    "total_duration_minutes": 90
  },
  "message": "Trip ended successfully"
}
```

---

#### Get Active Buses (Map View)
```
GET /api/buses/active/
```

Optimized endpoint for displaying buses on a map.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "registration_number": "ABC-1234",
    "route_id": 2,
    "route_code": "GL-01",
    "route_color": "#22C55E",
    "latitude": 31.5204,
    "longitude": 74.3587,
    "heading": 180,
    "speed": 35.5,
    "current_stop_sequence": 3,
    "next_stop_name": "University"
  }
]
```

---

## Error Responses

| Status Code | Description |
|-------------|-------------|
| 400 | Bad Request - Invalid data or validation error |
| 401 | Unauthorized - Invalid or missing token |
| 403 | Forbidden - Insufficient permissions (Admin required) |
| 404 | Not Found - Resource doesn't exist |

**Example Error Response:**
```json
{
  "error": "Only admins can create buses."
}
```

---

## Endpoint Summary

| Endpoint | Method | Auth | Admin Only | Description |
|----------|--------|------|------------|-------------|
| `/api/login/` | POST | ❌ | ❌ | Login & get token |
| `/api/register/` | POST | ✅ | ✅ | Register new user |
| `/api/me/` | GET | ✅ | ❌ | Get current user |
| `/api/users/` | GET | ✅ | ✅ | List all users |
| `/api/dashboard/stats/` | GET | ✅ | ❌ | Dashboard statistics |
| `/api/stops/` | GET | ✅ | ❌ | List all stops |
| `/api/stops/` | POST | ✅ | ✅ | Create stop |
| `/api/stops/{id}/` | GET | ✅ | ❌ | Get stop details |
| `/api/stops/{id}/` | PATCH | ✅ | ✅ | Update stop |
| `/api/stops/{id}/` | DELETE | ✅ | ✅ | Delete stop |
| `/api/routes/` | GET | ✅ | ❌ | List all routes |
| `/api/routes/` | POST | ✅ | ✅ | Create route |
| `/api/routes/{id}/` | GET | ✅ | ❌ | Get route details |
| `/api/routes/{id}/` | PATCH | ✅ | ✅ | Update route |
| `/api/routes/{id}/` | DELETE | ✅ | ✅ | Delete route |
| `/api/routes/{id}/stops/` | POST | ✅ | ✅ | Add stop to route |
| `/api/routes/{id}/stops/{rs_id}/` | DELETE | ✅ | ✅ | Remove stop from route |
| `/api/routes/{id}/stops/reorder/` | PUT | ✅ | ✅ | Reorder route stops |
| `/api/buses/` | GET | ✅ | ❌ | List all buses |
| `/api/buses/` | POST | ✅ | ✅ | Create bus |
| `/api/buses/{id}/` | GET | ✅ | ❌ | Get bus details |
| `/api/buses/{id}/` | PATCH | ✅ | ✅ | Update bus |
| `/api/buses/{id}/` | DELETE | ✅ | ✅ | Delete bus |
| `/api/buses/{id}/location/` | POST | ✅ | ❌ | Update GPS location |
| `/api/buses/{id}/start-trip/` | POST | ✅ | ❌ | Start trip |
| `/api/buses/{id}/end-trip/` | POST | ✅ | ❌ | End trip |
| `/api/buses/active/` | GET | ✅ | ❌ | Active buses for map |

---

## License

This project is for educational purposes - Database Systems Course, Semester 3.
