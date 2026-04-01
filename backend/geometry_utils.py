"""
Geometry utilities for flood zone intersection detection.
Used to determine if active routes intersect with new flood zones.
"""

import json
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import unary_union


def decode_polyline(polyline_str, precision=5):
    """
    Decode a Google-style polyline string into a list of (lat, lon) tuples.
    Valhalla returns encoded polylines in this format.
    """
    index = 0
    lat = 0
    lng = 0
    coordinates = []
    
    while index < len(polyline_str):
        # Latitude
        shift = 0
        result = 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if not (b >= 0x20):
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat
        
        # Longitude
        shift = 0
        result = 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if not (b >= 0x20):
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        
        coordinates.append((lat / 10**precision, lng / 10**precision))
    
    return coordinates


def create_flood_zone_polygon(center_lat, center_lon, radius_meters=100):
    """
    Create a circular polygon around a point for flood zone.
    Returns GeoJSON-like dictionary.
    """
    # Approximate degrees per meter at Earth's surface
    deg_per_meter = 1 / 111320
    
    # Create circle with ~32 points
    import math
    points = []
    for i in range(32):
        angle = 2 * math.pi * i / 32
        dx = radius_meters * math.cos(angle)
        dy = radius_meters * math.sin(angle)
        
        lon = center_lon + (dx * deg_per_meter / math.cos(math.radians(center_lat)))
        lat = center_lat + (dy * deg_per_meter)
        
        points.append([lon, lat])
    
    # Close the polygon
    points.append(points[0])
    
    return {
        "type": "Polygon",
        "coordinates": [points]
    }


def check_route_intersects_zone(route_geometry, zone_polygon_geojson):
    """
    Check if a route (polyline or list of coordinates) intersects with a flood zone.
    
    Args:
        route_geometry: Either encoded polyline string OR list of (lat, lon) tuples
        zone_polygon_geojson: GeoJSON polygon dictionary
    
    Returns:
        bool: True if route intersects zone
    """
    try:
        # Decode route if it's an encoded polyline
        if isinstance(route_geometry, str):
            route_coords = decode_polyline(route_geometry)
        else:
            route_coords = route_geometry
        
        # Convert route to LineString (swap lat/lon to lon/lat for Shapely)
        route_points = [(lon, lat) for lat, lon in route_coords]
        if len(route_points) < 2:
            return False
        
        route_line = LineString(route_points)
        
        # Convert zone polygon to Shapely Polygon
        zone_coords = zone_polygon_geojson['coordinates'][0]
        zone_polygon = Polygon(zone_coords)
        
        # Check intersection
        return route_line.intersects(zone_polygon)
    
    except Exception as e:
        print(f"Error checking route intersection: {e}")
        return False


def get_zone_bounding_box(zone_polygon_geojson):
    """
    Get bounding box of a flood zone for quick filtering.
    Returns (min_lon, min_lat, max_lon, max_lat)
    """
    try:
        coords = zone_polygon_geojson['coordinates'][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return (min(lons), min(lats), max(lons), max(lats))
    except:
        return None


def point_in_bbox(lat, lon, bbox):
    """Check if a point is within a bounding box."""
    if bbox is None:
        return False
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def routes_in_bbox(routes, bbox):
    """
    Filter routes that have start or end points within a bounding box.
    Quick pre-filter before detailed intersection check.
    """
    matching_routes = []
    for route in routes:
        start_in = point_in_bbox(route['start_lat'], route['start_lon'], bbox)
        end_in = point_in_bbox(route['end_lat'], route['end_lon'], bbox)
        if start_in or end_in:
            matching_routes.append(route)
    return matching_routes


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two points in meters using Haversine formula.
    """
    import math
    
    R = 6371000  # Earth's radius in meters
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda/2)**2 * math.cos(phi1) * math.cos(phi2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def find_reports_nearby(reports, lat, lon, radius_meters=100):
    """
    Find crowd reports within a radius of a point.
    """
    nearby = []
    for report in reports:
        dist = calculate_distance(lat, lon, report['lat'], report['lon'])
        if dist <= radius_meters:
            nearby.append(report)
    return nearby


def convert_to_valhalla_exclude_format(zone_polygon_geojson):
    """
    Convert GeoJSON polygon to Valhalla exclude_polygons format.
    Valhalla expects: [[lon1, lat1], [lon2, lat2], ...]
    """
    try:
        coords = zone_polygon_geojson['coordinates'][0]
        # Valhalla wants [lon, lat] format
        return [[c[0], c[1]] for c in coords]
    except:
        return None
