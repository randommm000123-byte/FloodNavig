"""
BAHACKS Backend API - Flood Detection and Safe Route Navigation System
With Dynamic Rerouting Capabilities
"""

import sqlite3
import hashlib
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from functools import wraps

from geometry_utils import (
    create_flood_zone_polygon,
    check_route_intersects_zone,
    get_zone_bounding_box,
    routes_in_bbox,
    find_reports_nearby,
    convert_to_valhalla_exclude_format,
    calculate_distance
)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Configuration
DATABASE = 'database/bahacks.db'
VALHALLA_URL = 'http://localhost:8002'
ADMIN_API_KEY = 'bahacks_admin_key_2024'  # Simple auth for demo

# Helper functions
def get_db():
    """Get database connection for current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Close database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def require_admin(f):
    """Decorator to require admin authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != ADMIN_API_KEY:
            return jsonify({'error': 'Admin authentication required'}), 401
        return f(*args, **kwargs)
    return decorated

def row_to_dict(row):
    """Convert sqlite3.Row to dictionary."""
    if row is None:
        return None
    return dict(row)

def rows_to_list(rows):
    """Convert list of sqlite3.Row to list of dictionaries."""
    return [dict(row) for row in rows]


# ==================== SENSOR ENDPOINTS ====================

@app.route('/api/sensors', methods=['POST'])
@require_admin
def add_sensor():
    """Add a new ESP32 sensor (admin only)."""
    data = request.get_json()
    
    required_fields = ['device_id', 'name', 'lat', 'lon']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO sensors (device_id, name, lat, lon, location_name, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        ''', (
            data['device_id'],
            data['name'],
            data['lat'],
            data['lon'],
            data.get('location_name', '')
        ))
        db.commit()
        
        sensor_id = cursor.lastrowid
        return jsonify({
            'message': 'Sensor added successfully',
            'sensor_id': sensor_id
        }), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Device ID already exists'}), 409


@app.route('/api/sensors', methods=['GET'])
def list_sensors():
    """List all sensors with their latest readings."""
    db = get_db()
    cursor = db.cursor()
    
    # Get all sensors with their latest reading
    cursor.execute('''
        SELECT s.*, 
               fr.level_cm, 
               fr.rain_detected, 
               fr.battery_voltage, 
               fr.timestamp as reading_timestamp
        FROM sensors s
        LEFT JOIN flood_readings fr ON s.id = fr.sensor_id
        WHERE fr.id = (
            SELECT MAX(id) FROM flood_readings WHERE sensor_id = s.id
        )
        ORDER BY s.id
    ''')
    
    sensors = rows_to_list(cursor.fetchall())
    return jsonify({'sensors': sensors})


@app.route('/api/sensors/<int:sensor_id>', methods=['PUT'])
@require_admin
def update_sensor(sensor_id):
    """Update sensor information."""
    data = request.get_json()
    db = get_db()
    
    # Build update query dynamically
    updates = []
    values = []
    
    allowed_fields = ['name', 'lat', 'lon', 'location_name', 'status']
    for field in allowed_fields:
        if field in data:
            updates.append(f'{field} = ?')
            values.append(data[field])
    
    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    values.append(sensor_id)
    
    cursor = db.cursor()
    cursor.execute(f'''
        UPDATE sensors SET {', '.join(updates)}
        WHERE id = ?
    ''', values)
    db.commit()
    
    if cursor.rowcount == 0:
        return jsonify({'error': 'Sensor not found'}), 404
    
    return jsonify({'message': 'Sensor updated successfully'})


@app.route('/api/sensors/<int:sensor_id>', methods=['DELETE'])
@require_admin
def delete_sensor(sensor_id):
    """Delete a sensor."""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('DELETE FROM sensors WHERE id = ?', (sensor_id,))
    db.commit()
    
    if cursor.rowcount == 0:
        return jsonify({'error': 'Sensor not found'}), 404
    
    return jsonify({'message': 'Sensor deleted successfully'})


# ==================== SENSOR DATA ENDPOINT ====================

@app.route('/api/sensor-data', methods=['POST'])
def receive_sensor_data():
    """
    Receive flood data from ESP32 sensors.
    Auto-creates flood zone if level > 30cm and triggers reroute.
    """
    data = request.get_json()
    
    required_fields = ['device_id', 'flood_level_cm']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Find sensor by device_id
    cursor.execute('SELECT * FROM sensors WHERE device_id = ?', (data['device_id'],))
    sensor = cursor.fetchone()
    
    if not sensor:
        return jsonify({'error': 'Sensor not registered'}), 404
    
    sensor_id = sensor['id']
    flood_level = data['flood_level_cm']
    rain_detected = data.get('rain_detected', False)
    battery_voltage = data.get('battery_voltage', 0)
    
    # Store flood reading
    cursor.execute('''
        INSERT INTO flood_readings (sensor_id, level_cm, rain_detected, battery_voltage)
        VALUES (?, ?, ?, ?)
    ''', (sensor_id, flood_level, 1 if rain_detected else 0, battery_voltage))
    
    # Update sensor last reading
    cursor.execute('''
        UPDATE sensors 
        SET last_reading = CURRENT_TIMESTAMP, 
            battery_level = ?
        WHERE id = ?
    ''', (battery_voltage, sensor_id))
    
    db.commit()
    
    # CRITICAL: If flood level > 30cm, create flood zone and trigger reroute
    if flood_level > 30:
        determine_flood_level(flood_level)
        create_flood_zone_from_sensor(
            sensor['lat'], 
            sensor['lon'], 
            flood_level,
            sensor['location_name'] or f"Sensor {data['device_id']}"
        )
    
    return jsonify({
        'message': 'Data received',
        'flood_level': flood_level,
        'zone_created': flood_level > 30
    })


def determine_flood_level(level_cm):
    """Determine flood level category based on MMDA standards."""
    if level_cm <= 30:
        return 'green'
    elif level_cm <= 60:
        return 'yellow'
    elif level_cm <= 100:
        return 'orange'
    else:
        return 'red'


def create_flood_zone_from_sensor(lat, lon, flood_level_cm, location_name):
    """Create flood zone from sensor reading and trigger reroute notification."""
    db = get_db()
    cursor = db.cursor()
    
    flood_category = determine_flood_level(flood_level_cm)
    
    # Create circular polygon around sensor location
    polygon = create_flood_zone_polygon(lat, lon, radius_meters=150)
    polygon_json = json.dumps(polygon)
    
    # Set expiration time (6 hours from now)
    expires_at = datetime.now() + timedelta(hours=6)
    
    # Check if zone already exists nearby
    cursor.execute('''
        SELECT id FROM flood_zones 
        WHERE active = 1 
        AND center_lat BETWEEN ? AND ?
        AND center_lon BETWEEN ? AND ?
    ''', (lat - 0.002, lat + 0.002, lon - 0.002, lon + 0.002))
    
    existing = cursor.fetchone()
    
    if existing:
        # Update existing zone
        cursor.execute('''
            UPDATE flood_zones 
            SET flood_level = ?, 
                created_at = CURRENT_TIMESTAMP,
                expires_at = ?,
                triggered_reroute = 1
            WHERE id = ?
        ''', (flood_category, expires_at, existing['id']))
        zone_id = existing['id']
    else:
        # Create new zone with triggered_reroute=1
        cursor.execute('''
            INSERT INTO flood_zones 
            (name, polygon_geojson, center_lat, center_lon, flood_level, active, source, expires_at, triggered_reroute)
            VALUES (?, ?, ?, ?, ?, 1, 'sensor', ?, 1)
        ''', (location_name, polygon_json, lat, lon, flood_category, expires_at))
        zone_id = cursor.lastrowid
    
    db.commit()
    
    # Mark active routes for reroute
    mark_affected_routes_for_reroute(lat, lon, polygon)
    
    return zone_id


# ==================== FLOOD LEVELS ENDPOINT ====================

@app.route('/api/flood-levels', methods=['GET'])
def get_flood_levels():
    """Get current flood status for all sensors."""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT s.id, s.device_id, s.name, s.lat, s.lon, s.location_name,
               fr.level_cm, fr.rain_detected, fr.timestamp,
               CASE 
                   WHEN fr.level_cm <= 30 THEN 'green'
                   WHEN fr.level_cm <= 60 THEN 'yellow'
                   WHEN fr.level_cm <= 100 THEN 'orange'
                   ELSE 'red'
               END as flood_category
        FROM sensors s
        LEFT JOIN flood_readings fr ON s.id = fr.sensor_id
        WHERE fr.id = (SELECT MAX(id) FROM flood_readings WHERE sensor_id = s.id)
        ORDER BY fr.level_cm DESC
    ''')
    
    readings = rows_to_list(cursor.fetchall())
    return jsonify({'flood_levels': readings})


# ==================== CROWD REPORT ENDPOINTS ====================

@app.route('/api/reports', methods=['POST'])
def submit_report():
    """
    Submit crowdsourced flood report.
    When 3rd report within 100m/6hrs, auto-confirm and create flood zone.
    """
    data = request.get_json()
    
    required_fields = ['lat', 'lon']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    description = data.get('description', '')
    reporter_id = data.get('reporter_id', 'anonymous')
    
    # Find existing reports nearby (within 100m) and recent (within 6 hours)
    cursor.execute('''
        SELECT * FROM crowd_reports
        WHERE status IN ('pending', 'confirmed')
        AND created_at > datetime('now', '-6 hours')
    ''')
    
    recent_reports = rows_to_list(cursor.fetchall())
    nearby_reports = find_reports_nearby(recent_reports, data['lat'], data['lon'], 100)
    
    # Insert new report
    cursor.execute('''
        INSERT INTO crowd_reports (lat, lon, description, reporter_id, status, report_count)
        VALUES (?, ?, ?, ?, 'pending', 1)
    ''', (data['lat'], data['lon'], description, reporter_id))
    
    report_id = cursor.lastrowid
    
    # Check if this is the 3rd+ report in the area
    if len(nearby_reports) >= 2:
        # This is the 3rd report - auto-confirm!
        cursor.execute('''
            UPDATE crowd_reports 
            SET status = 'confirmed', report_count = report_count + 1
            WHERE id = ?
        ''', (report_id,))
        
        # Update nearby reports to link them
        nearby_ids = [r['id'] for r in nearby_reports]
        if nearby_ids:
            placeholders = ','.join('?' * len(nearby_ids))
            cursor.execute(f'''
                UPDATE crowd_reports 
                SET status = 'confirmed'
                WHERE id IN ({placeholders})
            ''', nearby_ids)
        
        db.commit()
        
        # Create flood zone and trigger reroute
        create_flood_zone_from_report(data['lat'], data['lon'], 'crowd_report')
        
        return jsonify({
            'message': 'Report submitted and confirmed (multiple reports in area)',
            'report_id': report_id,
            'status': 'confirmed',
            'zone_created': True
        }), 201
    else:
        db.commit()
        return jsonify({
            'message': 'Report submitted successfully',
            'report_id': report_id,
            'status': 'pending'
        }), 201


def create_flood_zone_from_report(lat, lon, source='crowd_report'):
    """Create flood zone from confirmed crowd report and trigger reroute."""
    db = get_db()
    cursor = db.cursor()
    
    # Create circular polygon
    polygon = create_flood_zone_polygon(lat, lon, radius_meters=100)
    polygon_json = json.dumps(polygon)
    
    expires_at = datetime.now() + timedelta(hours=6)
    
    # Check for existing zone
    cursor.execute('''
        SELECT id FROM flood_zones 
        WHERE active = 1 
        AND center_lat BETWEEN ? AND ?
        AND center_lon BETWEEN ? AND ?
    ''', (lat - 0.002, lat + 0.002, lon - 0.002, lon + 0.002))
    
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute('''
            UPDATE flood_zones 
            SET created_at = CURRENT_TIMESTAMP,
                expires_at = ?,
                triggered_reroute = 1
            WHERE id = ?
        ''', (expires_at, existing['id']))
        zone_id = existing['id']
    else:
        cursor.execute('''
            INSERT INTO flood_zones 
            (name, polygon_geojson, center_lat, center_lon, flood_level, active, source, expires_at, triggered_reroute)
            VALUES (?, ?, ?, ?, 'yellow', 1, ?, ?, 1)
        ''', ('Crowd Report Area', polygon_json, lat, lon, source, expires_at))
        zone_id = cursor.lastrowid
    
    db.commit()
    
    # Mark affected routes for reroute
    mark_affected_routes_for_reroute(lat, lon, polygon)
    
    return zone_id


@app.route('/api/reports', methods=['GET'])
def list_reports():
    """List all crowd reports."""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT * FROM crowd_reports 
        ORDER BY created_at DESC
    ''')
    
    reports = rows_to_list(cursor.fetchall())
    return jsonify({'reports': reports})


@app.route('/api/reports/<int:report_id>/verify', methods=['POST'])
@require_admin
def verify_report(report_id):
    """
    Admin verifies a crowd report.
    Immediately creates flood zone and triggers reroute.
    """
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM crowd_reports WHERE id = ?', (report_id,))
    report = cursor.fetchone()
    
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    
    # Update report status
    cursor.execute('''
        UPDATE crowd_reports 
        SET status = 'verified', verified_by = ?
        WHERE id = ?
    ''', (g.get('admin_id', 1), report_id))  # Default to admin ID 1
    
    db.commit()
    
    # Create flood zone immediately and trigger reroute
    create_flood_zone_from_report(report['lat'], report['lon'], 'verified_report')
    
    return jsonify({
        'message': 'Report verified and flood zone activated',
        'zone_created': True
    })


# ==================== ACTIVE FLOOD ZONES ENDPOINT ====================

@app.route('/api/active-flood-zones', methods=['GET'])
def get_active_flood_zones():
    """
    Get currently active flood zones for frontend polling.
    Includes triggered_reroute flag for change detection.
    Frontend calls this every 15 seconds.
    """
    db = get_db()
    cursor = db.cursor()
    
    # Get active zones that haven't expired
    cursor.execute('''
        SELECT id, name, polygon_geojson, center_lat, center_lon, 
               flood_level, source, created_at, expires_at, triggered_reroute
        FROM flood_zones
        WHERE active = 1 
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY created_at DESC
    ''')
    
    zones = rows_to_list(cursor.fetchall())
    
    # Parse polygon GeoJSON for each zone
    for zone in zones:
        if zone['polygon_geojson']:
            try:
                zone['polygon'] = json.loads(zone['polygon_geojson'])
            except:
                zone['polygon'] = None
        else:
            zone['polygon'] = None
    
    # Reset triggered_reroute flag after returning (so it only triggers once per poll)
    cursor.execute('''
        UPDATE flood_zones SET triggered_reroute = 0 WHERE triggered_reroute = 1
    ''')
    db.commit()
    
    return jsonify({
        'zones': zones,
        'timestamp': datetime.now().isoformat(),
        'count': len(zones)
    })


# ==================== ROUTING ENDPOINT ====================

@app.route('/api/route', methods=['POST'])
def calculate_route():
    """
    Calculate flood-aware route using Valhalla.
    Uses exclude_polygons to avoid active flood zones.
    Supports dynamic rerouting.
    """
    data = request.get_json()
    
    required_fields = ['start_lat', 'start_lon', 'end_lat', 'end_lon']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    start_lat = data['start_lat']
    start_lon = data['start_lon']
    end_lat = data['end_lat']
    end_lon = data['end_lon']
    session_id = data.get('session_id', None)
    
    db = get_db()
    cursor = db.cursor()
    
    # Get active flood zones
    cursor.execute('''
        SELECT polygon_geojson, center_lat, center_lon 
        FROM flood_zones
        WHERE active = 1 
        AND (expires_at IS NULL OR expires_at > datetime('now'))
    ''')
    
    zones = cursor.fetchall()
    
    # Build exclude_polygons for Valhalla
    exclude_polygons = []
    for zone in zones:
        if zone['polygon_geojson']:
            try:
                polygon = json.loads(zone['polygon_geojson'])
                valhalla_format = convert_to_valhalla_exclude_format(polygon)
                if valhalla_format:
                    exclude_polygons.append(valhalla_format)
            except Exception as e:
                print(f"Error parsing zone polygon: {e}")
    
    # Build Valhalla request
    valhalla_request = {
        "locations": [
            {"lat": start_lat, "lon": start_lon},
            {"lat": end_lat, "lon": end_lon}
        ],
        "costing": "auto",
        "directions_options": {
            "units": "kilometers",
            "language": "en-US"
        }
    }
    
    # Add exclude_polygons if there are flood zones
    if exclude_polygons:
        valhalla_request["exclude_polygons"] = exclude_polygons
    
    # Call Valhalla routing engine
    try:
        response = requests.post(
            f"{VALHALLA_URL}/route",
            json=valhalla_request,
            timeout=10
        )
        
        if response.status_code == 200:
            route_data = response.json()
            
            # Extract route geometry and instructions
            route_geometry = route_data.get('trip', {}).get('legs', [{}])[0].get('shape', '')
            instructions = route_data.get('trip', {}).get('legs', [{}])[0].get('maneuvers', [])
            summary = route_data.get('trip', {}).get('summary', {})
            
            # Store/update active route for reroute tracking
            if session_id:
                store_active_route(
                    session_id, start_lat, start_lon, end_lat, end_lon, route_geometry
                )
            
            return jsonify({
                'success': True,
                'route': route_data,
                'geometry': route_geometry,
                'instructions': instructions,
                'summary': summary,
                'flood_zones_avoided': len(exclude_polygons),
                'rerouted': len(exclude_polygons) > 0
            })
        else:
            # Route failed with exclusions - try without exclusions
            if exclude_polygons:
                print("Route with exclusions failed, trying without...")
                valhalla_request_no_exclude = {k: v for k, v in valhalla_request.items() if k != 'exclude_polygons'}
                
                response = requests.post(
                    f"{VALHALLA_URL}/route",
                    json=valhalla_request_no_exclude,
                    timeout=10
                )
                
                if response.status_code == 200:
                    route_data = response.json()
                    route_geometry = route_data.get('trip', {}).get('legs', [{}])[0].get('shape', '')
                    
                    if session_id:
                        store_active_route(
                            session_id, start_lat, start_lon, end_lat, end_lon, route_geometry
                        )
                    
                    return jsonify({
                        'success': True,
                        'route': route_data,
                        'geometry': route_geometry,
                        'instructions': route_data.get('trip', {}).get('legs', [{}])[0].get('maneuvers', []),
                        'summary': route_data.get('trip', {}).get('summary', {}),
                        'flood_zones_avoided': 0,
                        'rerouted': False,
                        'warning': 'Unable to avoid flood zones - area may be completely flooded'
                    })
            
            return jsonify({
                'success': False,
                'error': 'Route calculation failed',
                'valhalla_error': response.text
            }), 500
    
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Valhalla service unavailable: {str(e)}'
        }), 503


def store_active_route(session_id, start_lat, start_lon, end_lat, end_lon, route_geometry):
    """Store or update active route for reroute tracking."""
    db = get_db()
    cursor = db.cursor()
    
    # Check if route exists
    cursor.execute('SELECT id FROM active_routes WHERE session_id = ?', (session_id,))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute('''
            UPDATE active_routes 
            SET current_route_geojson = ?, 
                last_updated = CURRENT_TIMESTAMP,
                needs_reroute = 0
            WHERE session_id = ?
        ''', (route_geometry, session_id))
    else:
        cursor.execute('''
            INSERT INTO active_routes 
            (session_id, start_lat, start_lon, end_lat, end_lon, current_route_geojson)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, start_lat, start_lon, end_lat, end_lon, route_geometry))
    
    db.commit()


def mark_affected_routes_for_reroute(lat, lon, polygon):
    """Mark all active routes that intersect with the new flood zone."""
    db = get_db()
    cursor = db.cursor()
    
    # Get all active routes from the last hour
    cursor.execute('''
        SELECT id, session_id, start_lat, start_lon, end_lat, end_lon, current_route_geojson
        FROM active_routes
        WHERE created_at > datetime('now', '-1 hour')
    ''')
    
    active_routes = rows_to_list(cursor.fetchall())
    
    affected_count = 0
    for route in active_routes:
        # Quick bounding box check first
        bbox = get_zone_bounding_box(polygon)
        if bbox:
            # Check if route endpoints are near the zone
            start_near = calculate_distance(lat, lon, route['start_lat'], route['start_lon']) < 5000
            end_near = calculate_distance(lat, lon, route['end_lat'], route['end_lon']) < 5000
            
            if start_near or end_near:
                # Detailed intersection check
                if route['current_route_geojson'] and check_route_intersects_zone(
                    route['current_route_geojson'], polygon
                ):
                    cursor.execute('''
                        UPDATE active_routes 
                        SET needs_reroute = 1, last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (route['id'],))
                    affected_count += 1
    
    db.commit()
    print(f"Marked {affected_count} routes for reroute due to new flood zone at ({lat}, {lon})")
    return affected_count


# ==================== STATUS ENDPOINT ====================

@app.route('/api/status', methods=['GET'])
def system_status():
    """System health check."""
    db = get_db()
    cursor = db.cursor()
    
    # Count various entities
    cursor.execute('SELECT COUNT(*) as count FROM sensors WHERE status = "active"')
    active_sensors = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM flood_zones WHERE active = 1 AND (expires_at IS NULL OR expires_at > datetime("now"))')
    active_zones = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM crowd_reports WHERE status = "pending"')
    pending_reports = cursor.fetchone()['count']
    
    # Check Valhalla connectivity
    valhalla_status = 'unknown'
    try:
        response = requests.get(f"{VALHALLA_URL}/status", timeout=2)
        if response.status_code == 200:
            valhalla_status = 'online'
        else:
            valhalla_status = 'error'
    except:
        valhalla_status = 'offline'
    
    return jsonify({
        'status': 'healthy',
        'active_sensors': active_sensors,
        'active_flood_zones': active_zones,
        'pending_reports': pending_reports,
        'valhalla_routing': valhalla_status,
        'timestamp': datetime.now().isoformat()
    })


# Initialize database on startup
with app.app_context():
    try:
        from init_db import init_database
        init_database(DATABASE)
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization warning: {e}")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
