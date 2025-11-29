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
    route_stops: List[Dict]
) -> Dict:
    """
    Determine which stop the bus has passed and which it's heading to,
    using MapBox to calculate actual road distances.
    
    Args:
        bus_location: (longitude, latitude) of bus
        route_stops: List of stops with 'sequence', 'stop_id', 'longitude', 'latitude'
    
    Returns:
        Dict with:
        - 'last_passed_stop': sequence of last stop bus has passed (or is at)
        - 'next_stop': sequence of next stop bus is heading to
        - 'is_at_stop': True if bus is at a stop (within threshold)
        - 'current_stop_sequence': The sequence to store in DB
        - 'distance_to_next': Distance in meters to next stop
        - 'eta_to_next': ETA in minutes to next stop
    """
    if not route_stops:
        return {
            'last_passed_stop': 0,
            'next_stop': 1,
            'is_at_stop': False,
            'current_stop_sequence': 1,
            'distance_to_next': None,
            'eta_to_next': None
        }
    
    # Sort stops by sequence
    stops = sorted(route_stops, key=lambda x: x['sequence'])
    
    # Get distances from bus to each stop using MapBox
    stop_distances = []
    for stop in stops:
        stop_loc = (stop['longitude'], stop['latitude'])
        result = get_eta_to_stop(bus_location, stop_loc)
        
        if result:
            stop_distances.append({
                'sequence': stop['sequence'],
                'stop_id': stop['stop_id'],
                'distance': result['distance_meters'],
                'eta': result['eta_minutes']
            })
        else:
            # Fallback to haversine
            dist = haversine_distance(
                bus_location[1], bus_location[0],  # lat, lon
                stop['latitude'], stop['longitude']
            )
            stop_distances.append({
                'sequence': stop['sequence'],
                'stop_id': stop['stop_id'],
                'distance': dist * 1.3,  # 30% buffer
                'eta': (dist * 1.3 / 1000) / 25 * 60  # Assume 25 km/h
            })
    
    # Find the nearest stop
    nearest = min(stop_distances, key=lambda x: x['distance'])
    
    # Threshold: if within 150m (road distance), consider bus "at" the stop
    AT_STOP_THRESHOLD = 150  # meters
    
    if nearest['distance'] <= AT_STOP_THRESHOLD:
        # Bus is at this stop
        return {
            'last_passed_stop': nearest['sequence'],
            'next_stop': nearest['sequence'] + 1 if nearest['sequence'] < len(stops) else nearest['sequence'],
            'is_at_stop': True,
            'current_stop_sequence': nearest['sequence'],
            'distance_to_next': 0,
            'eta_to_next': 0
        }
    
    # Bus is not at any stop - find which segment it's on
    # The bus is between stop A and stop B if:
    # distance(bus→A) + distance(bus→B) ≈ distance(A→B)
    # And distance(bus→B) < distance(bus→A) means heading toward B
    
    # Simpler approach: find the stop where the bus is closest,
    # then check if it's heading toward it or away from it
    # by comparing distances to adjacent stops
    
    nearest_idx = next(i for i, s in enumerate(stop_distances) if s['sequence'] == nearest['sequence'])
    
    # Check previous and next stops to determine direction
    if nearest_idx == 0:
        # Nearest is first stop - bus is approaching first stop
        return {
            'last_passed_stop': 0,
            'next_stop': nearest['sequence'],
            'is_at_stop': False,
            'current_stop_sequence': nearest['sequence'],
            'distance_to_next': round(nearest['distance']),
            'eta_to_next': round(nearest['eta'], 1)
        }
    
    if nearest_idx == len(stop_distances) - 1:
        # Nearest is last stop - bus is heading to last stop
        return {
            'last_passed_stop': stop_distances[nearest_idx - 1]['sequence'],
            'next_stop': nearest['sequence'],
            'is_at_stop': False,
            'current_stop_sequence': nearest['sequence'],
            'distance_to_next': round(nearest['distance']),
            'eta_to_next': round(nearest['eta'], 1)
        }
    
    # Bus is between stops - determine if it passed the nearest stop or not
    prev_stop = stop_distances[nearest_idx - 1]
    next_stop = stop_distances[nearest_idx + 1]
    
    # If distance to previous stop > distance to nearest stop, 
    # bus has passed previous and is heading to nearest
    if prev_stop['distance'] > nearest['distance']:
        # Bus is heading TOWARD nearest stop (hasn't reached it yet)
        return {
            'last_passed_stop': prev_stop['sequence'],
            'next_stop': nearest['sequence'],
            'is_at_stop': False,
            'current_stop_sequence': nearest['sequence'],
            'distance_to_next': round(nearest['distance']),
            'eta_to_next': round(nearest['eta'], 1)
        }
    else:
        # Bus has passed nearest stop and is heading to next
        return {
            'last_passed_stop': nearest['sequence'],
            'next_stop': next_stop['sequence'],
            'is_at_stop': False,
            'current_stop_sequence': next_stop['sequence'],
            'distance_to_next': round(next_stop['distance']),
            'eta_to_next': round(next_stop['eta'], 1)
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
