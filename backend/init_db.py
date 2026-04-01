import sqlite3
import hashlib
from datetime import datetime

def init_database(db_path='database/bahacks.db'):
    """Initialize SQLite database with all required tables."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Create sensors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            location_name TEXT,
            status TEXT DEFAULT 'active',
            battery_level REAL,
            last_reading TIMESTAMP
        )
    ''')
    
    # Create flood_readings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flood_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER NOT NULL,
            level_cm REAL NOT NULL,
            rain_detected BOOLEAN DEFAULT 0,
            battery_voltage REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sensor_id) REFERENCES sensors(id)
        )
    ''')
    
    # Create crowd_reports table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crowd_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            description TEXT,
            reporter_id TEXT,
            status TEXT DEFAULT 'pending',
            report_count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified_by INTEGER,
            FOREIGN KEY (verified_by) REFERENCES admins(id)
        )
    ''')
    
    # Create flood_zones table WITH triggered_reroute flag
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flood_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            polygon_geojson TEXT NOT NULL,
            center_lat REAL NOT NULL,
            center_lon REAL NOT NULL,
            flood_level TEXT DEFAULT 'unknown',
            active BOOLEAN DEFAULT 1,
            source TEXT DEFAULT 'sensor',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            triggered_reroute BOOLEAN DEFAULT 0
        )
    ''')
    
    # Create admins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT
        )
    ''')
    
    # Create active_routes table for tracking routes that need recalculation
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            start_lat REAL NOT NULL,
            start_lon REAL NOT NULL,
            end_lat REAL NOT NULL,
            end_lon REAL NOT NULL,
            current_route_geojson TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            needs_reroute BOOLEAN DEFAULT 0
        )
    ''')
    
    # Create index on flood_zones for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_flood_zones_active ON flood_zones(active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_flood_zones_expires ON flood_zones(expires_at)')
    
    # Create index on active_routes for reroute detection
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_active_routes_session ON active_routes(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_active_routes_needs_reroute ON active_routes(needs_reroute)')
    
    # Insert default admin user (password: admin123)
    default_password = hashlib.sha256('admin123'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO admins (username, password_hash, name) 
        VALUES ('admin', ?, 'System Administrator')
    ''', (default_password,))
    
    conn.commit()
    conn.close()
    
    print(f"Database initialized successfully at {db_path}")
    print("Default admin credentials: username='admin', password='admin123'")

if __name__ == '__main__':
    init_database()
