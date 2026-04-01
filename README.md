


---

## 📁 PROJECT STRUCTURE

```
/workspace
├── valhalla_data/          # Valhalla routing engine data
│   ├── philippines-latest.osm.pbf  (downloaded)
│   ├── valhalla.json               (config)
│   ├── valhalla_tiles/             (generated)
│   └── valhalla_tiles.tar          (generated)
├── backend/                  # Python Flask API
│   ├── venv/                 (Python virtual environment)
│   ├── app.py                (Main Flask application)
│   ├── init_db.py            (Database initialization)
│   └── geometry_utils.py     (Geometry utilities)
├── frontend/                 # Web interface
│   ├── index.html            (Main HTML file)
│   └── app.js                (Frontend JavaScript)
├── database/                 # SQLite database
│   └── bahacks.db            (auto-generated)
└── hardware/                 # ESP32 firmware
    └── esp32_flood_sensor.ino (Arduino code)
```

---

## ⚙️ PHASE 0: ENVIRONMENT SETUP (30 min)

### Step 1: Install Docker Desktop with WSL2

1. Download Docker Desktop from https://www.docker.com/products/docker-desktop
2. During installation, enable WSL2 backend
3. After installation, configure Docker:
   - Open Docker Desktop Settings
   - Go to Resources
   - Set Memory: 8GB
   - Set Swap: 2GB
   - Set CPUs: 4

### Step 2: Install Python 3.11+

```bash
# Check if Python is installed
python --version

# If not installed, download from https://www.python.org/downloads/
# Make sure to check "Add Python to PATH" during installation
```

### Step 3: Create Project Directory

```bash
cd /workspace
mkdir -p valhalla_data backend frontend database hardware
```

---

## 🗺️ PHASE 1: VALHALLA SETUP (60-90 min)

### Step 1: Download Philippines OSM Data

```bash
cd /workspace/valhalla_data

# Download Philippines extract (~300MB)
wget https://download.geofabrik.de/asia/philippines-latest.osm.pbf

# Verify download
ls -lh philippines-latest.osm.pbf
```

### Step 2: Verify Valhalla Configuration

The `valhalla.json` configuration file is already created at `/workspace/valhalla_data/valhalla.json`.

### Step 3: Build Valhalla Tiles

```bash
cd /workspace/valhalla_data

# Run Docker container to build tiles
docker run -t --rm \
  -v ${PWD}:/custom_files \
  ghcr.io/valhalla/valhalla:3.4.0 bash -c "
    valhalla_build_config --verbose /custom_files/valhalla.json &&
    valhalla_build_tiles --config /custom_files/valhalla.json --input /custom_files/philippines-latest.osm.pbf &&
    valhalla_build_extract --config /custom_files/valhalla.json --output /custom_files/valhalla_tiles.tar
  "
```

**Note:** This step takes 30-60 minutes depending on your system.

### Step 4: Start Valhalla Service

```bash
cd /workspace/valhalla_data

# Start persistent Valhalla container
docker run -d --name valhalla -p 8002:8002 \
  -v ${PWD}/valhalla_tiles.tar:/data/valhalla_tiles.tar \
  -v ${PWD}/valhalla.json:/custom_files/valhalla.json \
  ghcr.io/valhalla/valhalla:3.4.0

# Wait for service to start (30 seconds)
sleep 30

# Test Valhalla endpoint
curl -X POST http://localhost:8002/route \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      {"lat": 14.5995, "lon": 120.9842},
      {"lat": 14.6507, "lon": 121.0335}
    ],
    "costing": "auto"
  }'
```

If you see route data in response, Valhalla is working!

---

## 🔧 PHASE 2: BACKEND SETUP (60 min)

### Step 1: Create Python Virtual Environment

```bash
cd /workspace/backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
cd /workspace/backend

# Install required packages
pip install flask flask-cors requests python-dateutil shapely
```

### Step 3: Initialize Database

```bash
cd /workspace/backend

# Run database initialization
python init_db.py
```

This creates the SQLite database with all required tables:
- sensors
- flood_readings
- crowd_reports
- flood_zones (with triggered_reroute flag)
- admins
- active_routes

### Step 4: Start Flask Backend

```bash
cd /workspace/backend

# Start the Flask server
python app.py
```

The API will be available at `http://localhost:5000`

### Step 5: Test Backend Endpoints

```bash
# Test system status
curl http://localhost:5000/api/status

# Add a test sensor (admin only)
curl -X POST http://localhost:5000/api/sensors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: bahacks_admin_key_2024" \
  -d '{
    "device_id": "TEST_SENSOR_001",
    "name": "Test Sensor",
    "lat": 14.5995,
    "lon": 120.9842,
    "location_name": "Test Location"
  }'

# List sensors
curl http://localhost:5000/api/sensors

# Get active flood zones
curl http://localhost:5000/api/active-flood-zones
```

---

## 🌐 PHASE 3: FRONTEND SETUP (75 min)

### Step 1: Start HTTP Server

```bash
cd /workspace/frontend

# Start simple HTTP server
python -m http.server 8080
```

### Step 2: Open Frontend in Browser

Navigate to: `http://localhost:8080`

You should see:
- Map centered on Philippines
- Sidebar with routing controls
- Flood level legend
- Report flood button
- Admin panel toggle

### Step 3: Test Frontend Features

1. **Click on map** to set start point
2. **Click again** to set end point
3. **Click "Calculate Safe Route"** to get directions
4. **Click "Report Flood Here"** to submit a crowd report
5. **Click Admin toggle** to add/manage sensors

---

## 🔌 PHASE 4: HARDWARE SETUP (30 min)

### Step 1: Install Arduino IDE

1. Download from https://www.arduino.cc/en/software
2. Install Arduino IDE

### Step 2: Add ESP32 Board Support

1. Open Arduino IDE
2. Go to File > Preferences
3. Add to "Additional Boards Manager URLs":
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Go to Tools > Board > Boards Manager
5. Search for "ESP32" and install

### Step 3: Install Required Libraries

In Arduino IDE:
1. Go to Sketch > Include Library > Manage Libraries
2. Install:
   - ArduinoJson by Benoit Blanchon
   - WiFi (built-in)
   - HTTPClient (built-in)

### Step 4: Configure ESP32 Code

Open `/workspace/hardware/esp32_flood_sensor.ino` and update:

```cpp
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

const char* API_HOST = "192.168.1.XXX";  // Your laptop's IP address

const String DEVICE_ID = "ESP32_FLOOD_001";
const float SENSOR_LAT = 14.5995;  // Your sensor location
const float SENSOR_LON = 120.9842;
```

### Step 5: Upload to ESP32

1. Connect ESP32 via USB
2. Select Board: DOIT ESP32 DEVKIT V1 (or your board)
3. Select Port: COM port (Windows) or /dev/ttyUSB0 (Linux)
4. Click Upload
5. Open Serial Monitor (115200 baud) to see output

---

## 🧪 PHASE 5: INTEGRATION TESTING (45 min)

### Test Scenario 1: Basic Route Calculation

1. Open frontend at `http://localhost:8080`
2. Click map to set start point (e.g., 14.5995, 120.9842)
3. Click map to set end point (e.g., 14.6507, 121.0335)
4. Click "Calculate Safe Route"
5. Verify turn-by-turn instructions appear

### Test Scenario 2: Flood Zone Reroute ⭐ CRITICAL

1. Calculate a route as above
2. Open new terminal and add a flood zone via API:

```bash
curl -X POST http://localhost:5000/api/sensor-data \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "TEST_SENSOR_001",
    "flood_level_cm": 50,
    "rain_detected": true,
    "battery_voltage": 3.7
  }'
```

3. **Within 15 seconds**, frontend should:
   - Show reroute banner: "🌊 New flood detected..."
   - Play alert sound
   - Recalculate route avoiding flood zone
   - Display updated turn-by-turn instructions

### Test Scenario 3: Crowd Report Auto-Confirmation

1. Submit first report near a location (via UI)
2. Submit second report within 100m of first
3. Submit third report within 100m of first two
4. **Third report should auto-confirm and create flood zone**
5. Verify reroute triggers if route passes through area

### Test Scenario 4: Admin Verification

1. Submit a crowd report
2. Click Admin toggle
3. Find the report ID from reports list
4. Verify via API:

```bash
curl -X POST http://localhost:5000/api/reports/<REPORT_ID>/verify \
  -H "X-API-Key: bahacks_admin_key_2024"
```

5. **Immediate flood zone creation and reroute trigger**

### Test Scenario 5: ESP32 Integration

1. Power on ESP32 with sensor connected
2. Simulate flood by placing object under sensor
3. Watch Serial Monitor for readings
4. Verify data appears in backend:

```bash
curl http://localhost:5000/api/sensors
curl http://localhost:5000/api/flood-levels
```

5. If flood level > 30cm, verify flood zone created

---

## 📊 API ENDPOINT REFERENCE

### Public Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | System health check |
| GET | `/api/sensors` | List all sensors |
| GET | `/api/flood-levels` | Current flood status |
| GET | `/api/reports` | List crowd reports |
| GET | `/api/active-flood-zones` | Active flood zones (for polling) |
| POST | `/api/sensor-data` | ESP32 sends data |
| POST | `/api/reports` | Submit flood report |
| POST | `/api/route` | Calculate flood-aware route |

### Admin Endpoints (require X-API-Key header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sensors` | Add new sensor |
| PUT | `/api/sensors/<id>` | Update sensor |
| DELETE | `/api/sensors/<id>` | Delete sensor |
| POST | `/api/reports/<id>/verify` | Verify crowd report |

**Admin API Key:** `bahacks_admin_key_2024`

---

## 🎯 DYNAMIC REROUTING MECHANISM

### How It Works:

1. **Frontend Polling**: Every 15 seconds, calls `/api/active-flood-zones`
2. **Zone Hash Comparison**: Creates hash of zone IDs + timestamps
3. **Change Detection**: If hash differs from previous poll → zones changed!
4. **Reroute Trigger**: 
   - Shows banner: "🌊 New flood detected - Finding safe alternative route..."
   - Plays audio alert (Web Audio API beep)
   - Calls `/api/route` with same start/end points
   - Valhalla recalculates with new exclude_polygons
5. **Visual Feedback**: Banner changes to "✓ Route updated" after completion

### Backend Reroute Logic:

When flood zone created (from sensor >30cm OR 3 crowd reports OR admin verify):
1. Create polygon around location
2. Query `active_routes` table for routes in last hour
3. Check if any route intersects new flood zone (using Shapely)
4. Mark affected routes with `needs_reroute=1`
5. Set `triggered_reroute=1` on flood zone
6. Next frontend poll detects change → triggers recalculation

---

## 🔍 TROUBLESHOOTING

### Valhalla Not Starting

```bash
# Check Docker logs
docker logs valhalla

# Restart container
docker restart valhalla

# Rebuild tiles if corrupted
rm -rf valhalla_tiles valhalla_tiles.tar
# Run build command again
```

### Backend Connection Errors

```bash
# Check if Flask is running
netstat -an | grep 5000

# Check database exists
ls -la database/bahacks.db

# Reinitialize database
python init_db.py
```

### Frontend Not Loading

```bash
# Check HTTP server is running
netstat -an | grep 8080

# Check browser console for errors (F12)
# Common issue: CORS - ensure Flask has CORS enabled
```

### ESP32 Not Connecting

1. Verify WiFi credentials are correct
2. Check laptop firewall allows port 5000
3. Use laptop's local IP (not localhost) for API_HOST
4. Check Serial Monitor for error messages

### Route Calculation Fails

```bash
# Test Valhalla directly
curl -X POST http://localhost:8002/route \
  -H "Content-Type: application/json" \
  -d '{"locations":[{"lat":14.5995,"lon":120.9842},{"lat":14.6507,"lon":121.0335}],"costing":"auto"}'

# If fails, Valhalla needs tile rebuild
```

---

## 📝 THESIS DEMO SCRIPT

### Demo Flow (5-7 minutes):

1. **Introduction (1 min)**
   - Show system architecture diagram
   - Explain problem: flooding in Philippines, need for real-time detection

2. **Live Map Demo (2 min)**
   - Open frontend
   - Show current sensor locations
   - Demonstrate route calculation between two points

3. **Dynamic Rerouting (2 min)** ⭐ KEY FEATURE
   - Start navigation on a route
   - Trigger flood via API (simulate sensor reading)
   - Show automatic reroute within 15 seconds
   - Highlight banner, sound, and new route

4. **Crowdsourcing (1 min)**
   - Submit 3 reports in same area
   - Show auto-confirmation on 3rd report
   - Demonstrate flood zone creation

5. **Hardware Demo (1 min)**
   - Show ESP32 with sensor
   - Simulate flood with hand/object
   - Show data appearing in backend

---

## 📄 DATABASE SCHEMA

```sql
-- Sensors table
CREATE TABLE sensors (
    id INTEGER PRIMARY KEY,
    device_id TEXT UNIQUE,
    name TEXT,
    lat REAL,
    lon REAL,
    location_name TEXT,
    status TEXT DEFAULT 'active',
    battery_level REAL,
    last_reading TIMESTAMP
);

-- Flood readings from sensors
CREATE TABLE flood_readings (
    id INTEGER PRIMARY KEY,
    sensor_id INTEGER,
    level_cm REAL,
    rain_detected BOOLEAN,
    battery_voltage REAL,
    timestamp TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES sensors(id)
);

-- Crowdsourced reports
CREATE TABLE crowd_reports (
    id INTEGER PRIMARY KEY,
    lat REAL,
    lon REAL,
    description TEXT,
    reporter_id TEXT,
    status TEXT DEFAULT 'pending',
    report_count INTEGER DEFAULT 1,
    created_at TIMESTAMP,
    verified_by INTEGER
);

-- Active flood zones (KEY FOR REROUTING)
CREATE TABLE flood_zones (
    id INTEGER PRIMARY KEY,
    name TEXT,
    polygon_geojson TEXT,
    center_lat REAL,
    center_lon REAL,
    flood_level TEXT,
    active BOOLEAN DEFAULT 1,
    source TEXT DEFAULT 'sensor',
    created_at TIMESTAMP,
    expires_at TIMESTAMP,
    triggered_reroute BOOLEAN DEFAULT 0  -- Flags when reroute needed
);

-- Active navigation sessions
CREATE TABLE active_routes (
    id INTEGER PRIMARY KEY,
    session_id TEXT UNIQUE,
    start_lat REAL,
    start_lon REAL,
    end_lat REAL,
    end_lon REAL,
    current_route_geojson TEXT,
    created_at TIMESTAMP,
    last_updated TIMESTAMP,
    needs_reroute BOOLEAN DEFAULT 0  -- Marks routes needing recalculation
);
```

---

## ✅ REROUTE TESTING CHECKLIST

- [ ] Calculate route from Point A to Point B
- [ ] Add flood zone directly on route path via API
- [ ] Within 15 seconds, frontend shows reroute banner
- [ ] New route calculated avoiding flood zone
- [ ] Turn-by-turn instructions update
- [ ] Submit 3 crowd reports near active route
- [ ] Auto-reroute triggers on 3rd report confirmation
- [ ] Admin verifies different report
- [ ] Immediate reroute triggers
- [ ] Wait for flood zone to expire (or manually deactivate)
- [ ] Route returns to original optimal path
- [ ] ESP32 sends data with flood >30cm
- [ ] Backend creates flood zone automatically
- [ ] All active routes in area recalculate

---

## 🎓 THESIS DOCUMENTATION NOTES

### Key Innovations:

1. **Real-time Dynamic Rerouting**: Unlike static flood maps, system recalculates routes within 15 seconds of new flood detection

2. **Multi-source Flood Detection**: Combines IoT sensors + crowdsourced reports + admin verification

3. **Automatic Confirmation**: 3 independent reports within 100m/6hrs auto-create flood zone

4. **Route Intersection Detection**: Only affects active routes that actually intersect new flood zones

5. **Self-contained System**: No external API dependencies, runs entirely on local infrastructure

### Performance Metrics:

- Reroute trigger time: < 15 seconds from flood confirmation
- Sensor data interval: 30 seconds (immediate on rapid rise)
- Frontend polling: 15 seconds
- Flood zone expiration: 6 hours (auto-cleanup)
- Route calculation: 1-3 seconds (Philippines-only tiles)

### Scalability Considerations:

- Philippines-only OSM data: ~300MB download, ~2GB after tile build
- SQLite sufficient for demo; can migrate to PostgreSQL for production
- Valhalla handles 100+ route requests/second
- Frontend polling could use WebSocket for push notifications

---

## 📞 SUPPORT

For issues or questions:
1. Check troubleshooting section above
2. Review backend logs: Flask prints to console
3. Check frontend console: Press F12 in browser
4. Verify all services are running:
   - Docker: `docker ps`
   - Flask: `netstat -an | grep 5000`
   - HTTP server: `netstat -an | grep 8080`
   - Valhalla: `curl http://localhost:8002/status`

---

**BAHACKS - Bayanihan Hacks**
*Community-powered flood detection and safe navigation for the Philippines*
