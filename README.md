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

#### Start Trip (Admin Only)
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

#### End Trip (Admin Only)
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
| `/api/buses/` | GET | ✅ | ❌ | List all buses |
| `/api/buses/` | POST | ✅ | ✅ | Create bus |
| `/api/buses/{id}/` | GET | ✅ | ❌ | Get bus details |
| `/api/buses/{id}/` | PATCH | ✅ | ✅ | Update bus |
| `/api/buses/{id}/` | DELETE | ✅ | ✅ | Delete bus |
| `/api/buses/{id}/location/` | POST | ✅ | ❌ | Update GPS location |
| `/api/buses/{id}/start-trip/` | POST | ✅ | ✅ | Start trip |
| `/api/buses/{id}/end-trip/` | POST | ✅ | ✅ | End trip |
| `/api/buses/active/` | GET | ✅ | ❌ | Active buses for map |

---

## License

This project is for educational purposes - Database Systems Course, Semester 3.
