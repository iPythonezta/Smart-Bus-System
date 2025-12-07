"""
MapBox API utilities for distance and ETA calculations.
Uses MapBox Directions API for accurate road-based routing.
"""

import requests
from django.conf import settings
from typing import List, Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)

MAPBOX_BASE_URL = "https://api.mapbox.com/directions/v5/mapbox"


def get_access_token() -> str:
    """Get MapBox access token from settings."""
    token = getattr(settings, 'MAPBOX_ACCESS_TOKEN', None)
    if not token:
        raise ValueError("MAPBOX_ACCESS_TOKEN not configured in settings")
    return token


def get_route_info(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    profile: str = "driving-traffic"
) -> Optional[Dict]:
    """
    Get route information between two points using MapBox Directions API.
    
    Args:
        origin: Tuple of (longitude, latitude) for start point
        destination: Tuple of (longitude, latitude) for end point
        profile: Routing profile - 'driving-traffic', 'driving', 'walking', 'cycling'
    
    Returns:
        Dict with 'distance' (meters), 'duration' (seconds), 'duration_minutes' (float)
        or None if API call fails
    """
    try:
        token = get_access_token()
        
        # MapBox expects coordinates as longitude,latitude
        coordinates = f"{origin[0]},{origin[1]};{destination[0]},{destination[1]}"
        url = f"{MAPBOX_BASE_URL}/{profile}/{coordinates}"
        
        params = {
            'access_token': token,
            'geometries': 'geojson',
            'overview': 'simplified'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('code') != 'Ok' or not data.get('routes'):
            logger.warning(f"MapBox API returned no routes: {data.get('code')}")
            return None
        
        route = data['routes'][0]
        distance = route['distance']  # meters
        duration = route['duration']  # seconds
        
        return {
            'distance': round(distance),
            'duration': round(duration),
            'duration_minutes': round(duration / 60, 1)
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"MapBox API request failed: {e}")
        return None
    except ValueError as e:
        logger.error(f"MapBox configuration error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in MapBox API call: {e}")
        return None


def get_multi_stop_route(
    waypoints: List[Tuple[float, float]],
    profile: str = "driving-traffic"
) -> Optional[Dict]:
    """
    Get route information for multiple waypoints (bus following a route).
    
    Args:
        waypoints: List of (longitude, latitude) tuples in order
        profile: Routing profile
    
    Returns:
        Dict with 'total_distance', 'total_duration', 'legs' (list of leg info)
        or None if API call fails
    """
    if len(waypoints) < 2:
        return None
    
    # MapBox allows max 25 waypoints per request
    if len(waypoints) > 25:
        waypoints = waypoints[:25]
    
    try:
        token = get_access_token()
        
        # Build coordinates string
        coordinates = ";".join([f"{lon},{lat}" for lon, lat in waypoints])
        url = f"{MAPBOX_BASE_URL}/{profile}/{coordinates}"
        
        params = {
            'access_token': token,
            'geometries': 'geojson',
            'overview': 'simplified',
            'steps': 'false'
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('code') != 'Ok' or not data.get('routes'):
            logger.warning(f"MapBox API returned no routes: {data.get('code')}")
            return None
        
        route = data['routes'][0]
        
        legs = []
        cumulative_distance = 0
        cumulative_duration = 0
        
        for i, leg in enumerate(route.get('legs', [])):
            cumulative_distance += leg['distance']
            cumulative_duration += leg['duration']
            
            legs.append({
                'leg_index': i,
                'distance': round(leg['distance']),
                'duration': round(leg['duration']),
                'duration_minutes': round(leg['duration'] / 60, 1),
                'cumulative_distance': round(cumulative_distance),
                'cumulative_duration': round(cumulative_duration),
                'cumulative_duration_minutes': round(cumulative_duration / 60, 1)
            })
        
        return {
            'total_distance': round(route['distance']),
            'total_duration': round(route['duration']),
            'total_duration_minutes': round(route['duration'] / 60, 1),
            'legs': legs
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"MapBox API request failed: {e}")
        return None
    except ValueError as e:
        logger.error(f"MapBox configuration error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in MapBox API call: {e}")
        return None


def get_eta_to_stop(
    bus_location: Tuple[float, float],
    stop_location: Tuple[float, float]
) -> Optional[Dict]:
    """
    Get ETA from bus current location to a specific stop.
    
    Args:
        bus_location: (longitude, latitude) of bus
        stop_location: (longitude, latitude) of stop
    
    Returns:
        Dict with 'eta_minutes', 'distance_meters' or None
    """
    result = get_route_info(bus_location, stop_location)
    
    if result:
        return {
            'eta_minutes': result['duration_minutes'],
            'distance_meters': result['distance']
        }
    return None


def get_etas_to_multiple_stops(
    bus_location: Tuple[float, float],
    stop_locations: List[Tuple[float, float, int, str]],  # (lon, lat, stop_id, stop_name)
) -> List[Dict]:
    """
    Get ETAs from bus to multiple upcoming stops along a route.
    
    Args:
        bus_location: (longitude, latitude) of bus
        stop_locations: List of (longitude, latitude, stop_id, stop_name) for each stop
    
    Returns:
        List of dicts with stop_id, stop_name, eta_minutes, distance_meters
    """
    if not stop_locations:
        return []
    
    # Build waypoints: bus location + all stop locations
    waypoints = [bus_location] + [(s[0], s[1]) for s in stop_locations]
    
    route_info = get_multi_stop_route(waypoints)
    
    if not route_info or not route_info.get('legs'):
        return []
    
    results = []
    for i, stop_data in enumerate(stop_locations):
        if i < len(route_info['legs']):
            leg = route_info['legs'][i]
            results.append({
                'stop_id': stop_data[2],
                'stop_name': stop_data[3],
                'eta_minutes': leg['cumulative_duration_minutes'],
                'distance_meters': leg['cumulative_distance']
            })
    
    return results


# Fallback Haversine calculation (used if MapBox API fails)
from math import radians, sin, cos, sqrt, atan2

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Fallback: Calculate distance using Haversine formula.
    Returns distance in meters.
    """
    R = 6371000  # Earth's radius in meters
    
    lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


def fallback_eta(lat1: float, lon1: float, lat2: float, lon2: float, speed_kmh: float = 25) -> Dict:
    """
    Fallback ETA calculation using Haversine (straight-line) distance.
    Used when MapBox API is unavailable.
    
    Args:
        lat1, lon1: Start coordinates (latitude, longitude)
        lat2, lon2: End coordinates (latitude, longitude)
        speed_kmh: Assumed average speed in km/h (default: 25 for city bus)
    
    Returns:
        Dict with eta_minutes and distance_meters
    """
    distance = haversine_distance(lat1, lon1, lat2, lon2)
    # Add 30% buffer for actual road distance vs straight line
    adjusted_distance = distance * 1.3
    eta_minutes = (adjusted_distance / 1000) / speed_kmh * 60
    
    return {
        'eta_minutes': round(eta_minutes, 1),
        'distance_meters': round(adjusted_distance)
    }


def get_bus_position_on_route(
    bus_location: Tuple[float, float],
    route_stops: List[Dict],
    stop_seq: int = None
) -> Dict:
    """
    SIMPLIFIED LOGIC - Clear state machine for bus position.
    
    Rules:
    1. If within 30m of ANY stop >= stop_seq: Bus is AT that stop
    2. If not at any stop: Bus is HEADING TO the nearest upcoming stop
    3. Sequence only increases when bus gets within 30m of next stop
    
    Args:
        bus_location: (longitude, latitude) of bus
        route_stops: List of stops with 'sequence', 'stop_id', 'longitude', 'latitude'
        stop_seq: Current stop sequence from DB
    
    Returns:
        Dict with current_stop_sequence and other metadata
    """
    if not route_stops:
        return {
            'last_passed_stop': 0,
            'next_stop': 1,
            'is_at_stop': False,
            'current_stop_sequence': 0,
            'distance_to_next': None,
            'eta_to_next': None
        }
    
    # Initialize
    stops = sorted(route_stops, key=lambda x: x['sequence'])
    if stop_seq is None:
        stop_seq = 0
    
    # Thresholds
    AT_STOP_THRESHOLD = 30  # meters - bus is physically at stop
    
    # Calculate distances to upcoming stops
    # Key insight: stop_seq represents the stop we're currently targeting (at or heading to)
    # We only consider stops >= stop_seq (current target and beyond)
    upcoming_stops = []
    for stop in stops:
        # Skip stops before our current target
        if stop["sequence"] < stop_seq:
            continue
        
        stop_loc = (stop['longitude'], stop['latitude'])
        result = get_eta_to_stop(bus_location, stop_loc)
        
        if result:
            upcoming_stops.append({
                'sequence': stop['sequence'],
                'stop_id': stop['stop_id'],
                'distance': result['distance_meters'],
                'eta': result['eta_minutes']
            })
        else:
            # Fallback
            dist = haversine_distance(
                bus_location[1], bus_location[0],
                stop['latitude'], stop['longitude']
            )
            upcoming_stops.append({
                'sequence': stop['sequence'],
                'stop_id': stop['stop_id'],
                'distance': dist * 1.3,
                'eta': (dist * 1.3 / 1000) / 25 * 60
            })
    
    # No more stops left
    if not upcoming_stops:
        logger.info(f"Bus completed route at stop {stop_seq}")
        return {
            'last_passed_stop': stop_seq,
            'next_stop': stop_seq,
            'is_at_stop': False,
            'current_stop_sequence': stop_seq,
            'distance_to_next': None,
            'eta_to_next': None
        }
    
    # Find nearest upcoming stop
    nearest = min(upcoming_stops, key=lambda x: x['distance'])
    
    # === STATE 1: Bus is AT a stop (within 30m) ===
    if nearest['distance'] <= AT_STOP_THRESHOLD:
        # Find next stop after this one
        next_stop_seq = None
        for s in upcoming_stops:
            if s['sequence'] > nearest['sequence']:
                next_stop_seq = s['sequence']
                break
        
        logger.info(f"Bus AT stop {nearest['sequence']} (distance: {nearest['distance']}m)")
        return {
            'last_passed_stop': nearest['sequence'],
            'next_stop': next_stop_seq if next_stop_seq else nearest['sequence'],
            'is_at_stop': True,
            'current_stop_sequence': nearest['sequence'],  # Update to this stop
            'distance_to_next': 0,
            'eta_to_next': 0
        }
    
    # === STATE 2: Bus is BETWEEN stops (> 30m from all) ===
    
    # Strategy: current_stop_sequence always points to the NEAREST upcoming stop
    # This naturally handles departure - when bus leaves, the NEXT stop becomes nearest
    
    # Bus is heading toward the nearest upcoming stop
    logger.info(f"Bus heading to stop {nearest['sequence']} (distance: {nearest['distance']}m, current_seq: {stop_seq})")
    return {
        'last_passed_stop': max(0, nearest['sequence'] - 1),
        'next_stop': nearest['sequence'],
        'is_at_stop': False,
        'current_stop_sequence': nearest['sequence'],  # Always target nearest
        'distance_to_next': round(nearest['distance']),
        'eta_to_next': round(nearest['eta'], 1)
    }


def has_bus_passed_stop(
    bus_location: Tuple[float, float],
    stop_location: Tuple[float, float],
    next_stop_location: Tuple[float, float]
) -> bool:
    """
    Determine if a bus has passed a stop by checking if the stop is "behind" the bus.
    
    Logic: If distance(bus→stop) + distance(stop→next) ≈ distance(bus→next),
    then the stop is on the path ahead. Otherwise, the stop is behind.
    
    Args:
        bus_location: (longitude, latitude) of bus
        stop_location: (longitude, latitude) of the stop to check
        next_stop_location: (longitude, latitude) of the next stop on route
    
    Returns:
        True if bus has passed the stop, False otherwise
    """
    # Get distances
    bus_to_stop = get_eta_to_stop(bus_location, stop_location)
    bus_to_next = get_eta_to_stop(bus_location, next_stop_location)
    stop_to_next = get_eta_to_stop(stop_location, next_stop_location)
    
    if not all([bus_to_stop, bus_to_next, stop_to_next]):
        # Fallback: use simple distance comparison
        d_bus_stop = haversine_distance(bus_location[1], bus_location[0], 
                                         stop_location[1], stop_location[0])
        d_bus_next = haversine_distance(bus_location[1], bus_location[0],
                                         next_stop_location[1], next_stop_location[0])
        d_stop_next = haversine_distance(stop_location[1], stop_location[0],
                                          next_stop_location[1], next_stop_location[0])
        
        # If stop is ahead: bus→stop + stop→next ≈ bus→next
        # If stop is behind: bus→stop + bus→next ≈ stop→next (bus is between stop and next)
        path_via_stop = d_bus_stop + d_stop_next
        direct_to_next = d_bus_next
        
        # If going via stop is much longer than direct, stop is behind us
        return path_via_stop > direct_to_next * 1.5
    
    # Using MapBox distances
    path_via_stop = bus_to_stop['distance_meters'] + stop_to_next['distance_meters']
    direct_to_next = bus_to_next['distance_meters']
    
    # If going via stop adds more than 50% distance, stop is behind us
    return path_via_stop > direct_to_next * 1.5
