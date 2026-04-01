# BAHACKS Testing Guide

## 🧪 How to Test Your System

### Prerequisites
Before testing, ensure all services are running:

```bash
# 1. Valhalla (Docker) - should be running on port 8002
docker ps | grep valhalla

# 2. Flask Backend - should be running on port 5000
curl http://localhost:5000/api/status

# 3. Frontend - should be serving on port 8080
curl http://localhost:8080
```

---

## Option 1: Automated Test Suite (Recommended)

Run the comprehensive test suite that checks ALL functionality:

```bash
cd /workspace/backend

# Install test dependencies if needed
pip install requests

# Run the full test suite
python test_system.py
```

**What it tests:**
- ✅ System health (backend + Valhalla)
- ✅ Database operations
- ✅ Sensor management (CRUD)
- ✅ Sensor data submission
- ✅ Automatic flood zone creation
- ✅ Crowdsourced reports (3-report auto-confirm)
- ✅ Route calculation
- ✅ Dynamic rerouting logic
- ✅ Admin verification
- ✅ API response times
- ✅ Concurrent request handling

**Expected Output:**
```
╔═══════════════════════════════════════════════════════════╗
║           BAHACKS - Complete System Test Suite            ║
╚═══════════════════════════════════════════════════════════╝

PHASE 1: System Health Check
Testing: Backend API is running... ✓ PASSED
Testing: Valhalla routing engine is running... ✓ PASSED

PHASE 2: Database & Sensor Management
Testing: Create admin user... ✓ PASSED
Testing: Add test sensor... ✓ PASSED
...

TEST SUMMARY
Total Tests: 25
Passed: 25
Failed: 0

🎉 ALL TESTS PASSED! System ready for thesis demo!
```

---

## Option 2: Quick Manual Tests

Run individual API tests with formatted output:

```bash
cd /workspace/backend
./test_manual.sh
```

**What it does:**
1. Checks backend health
2. Tests Valhalla routing
3. Creates a test sensor
4. Sends normal reading (15cm)
5. Sends flood reading (55cm) → creates zone
6. Lists active flood zones
7. Submits crowd report
8. Calculates route
9. Lists all sensors
10. Shows flood levels with color coding

---

## Option 3: Individual curl Commands

Test specific endpoints manually:

### 1. Backend Health Check
```bash
curl http://localhost:5000/api/status | python3 -m json.tool
```

**Expected Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "valhalla": "http://localhost:8002",
  "timestamp": "2024-..."
}
```

### 2. Valhalla Route Test
```bash
curl -X POST http://localhost:8002/route \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      {"lat": 14.5995, "lon": 120.9842},
      {"lat": 14.5500, "lon": 121.0500}
    ],
    "costing": "auto"
  }' | python3 -m json.tool | head -30
```

**Expected:** JSON with `trip` object containing route geometry and legs

### 3. Add a Sensor
```bash
curl -X POST http://localhost:5000/api/sensors \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "TEST_SENSOR_01",
    "name": "Test Sensor Manila",
    "lat": 14.5995,
    "lon": 120.9842,
    "location_name": "Manila Bay",
    "status": "active"
  }' | python3 -m json.tool
```

### 4. Send Sensor Data (Creates Flood Zone if >30cm)
```bash
curl -X POST http://localhost:5000/api/sensor-data \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "TEST_SENSOR_01",
    "flood_level_cm": 55,
    "rain_detected": true,
    "battery_voltage": 3.6
  }' | python3 -m json.tool
```

**Expected Response:**
```json
{
  "success": true,
  "reading_id": 1,
  "flood_zone_created": true,
  "zone_id": 1,
  "message": "Flood level 55cm exceeds threshold. Zone created."
}
```

### 5. Get Active Flood Zones
```bash
curl http://localhost:5000/api/active-flood-zones | python3 -m json.tool
```

**Expected:** List of active flood zones with polygons

### 6. Submit Crowd Report
```bash
curl -X POST http://localhost:5000/api/reports \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 14.5800,
    "lon": 121.0200,
    "description": "Flooding in our street!",
    "reporter_id": "user123"
  }' | python3 -m json.tool
```

### 7. Calculate Route with Flood Avoidance
```bash
curl -X POST http://localhost:5000/api/route \
  -H "Content-Type: application/json" \
  -d '{
    "start_lat": 14.5995,
    "start_lon": 120.9842,
    "end_lat": 14.5500,
    "end_lon": 121.0500,
    "session_id": "demo_session_001"
  }' | python3 -m json.tool
```

**Expected:** Route with turn-by-turn instructions avoiding flood zones

---

## Option 4: Browser-Based Testing (Frontend)

### Step 1: Open the Application
```bash
# In one terminal, start frontend server
cd /workspace/frontend
python -m http.server 8080

# Open browser to:
# http://localhost:8080
```

### Step 2: Visual Tests

#### Test Map Display
- [ ] Map loads centered on Philippines
- [ ] Can pan and zoom
- [ ] Max bounds restrict to Philippines area

#### Test Sensor Display
- [ ] Sensors appear as colored circles
- [ ] Colors match MMDA legend (Green/Yellow/Orange/Red)
- [ ] Clicking sensor shows popup with details

#### Test Routing
1. Click "Set Start Point" button
2. Click anywhere on map
3. Click "Set End Point" button
4. Click another location
5. **Verify:**
   - [ ] Route line appears on map
   - [ ] Turn-by-turn instructions show in sidebar
   - [ ] Distance and time displayed

#### Test Flood Reporting
1. Click "Report Flood" button
2. Fill in form:
   - Location (auto-filled from map click)
   - Description: "Test flood report"
   - Upload photo (optional)
3. Submit
4. **Verify:**
   - [ ] Report appears on map as marker
   - [ ] Status shows as "Pending"
   - [ ] Report count increments

#### Test Dynamic Rerouting (KEY FEATURE!)
1. Calculate a route first
2. In new terminal, submit flood report ON the route:
   ```bash
   curl -X POST http://localhost:5000/api/reports \
     -H "Content-Type: application/json" \
     -d '{
       "lat": 14.5750,
       "lon": 121.0150,
       "description": "Emergency flood on route!",
       "reporter_id": "admin",
       "force_verify": true
     }'
   ```
3. **Watch the browser within 15 seconds:**
   - [ ] Banner appears: "🌊 New flood detected - Finding safe alternative route..."
   - [ ] Banner flashes yellow
   - [ ] Audio beep plays (if enabled)
   - [ ] Route recalculates automatically
   - [ ] New route avoids flood zone
   - [ ] Turn-by-turn instructions update
   - [ ] Banner changes to green: "✓ Route updated"

#### Test Real-Time Updates
- [ ] Sensor data refreshes every 30 seconds (watch timestamp)
- [ ] Flood zones update without page reload
- [ ] New reports appear automatically

---

## 🐛 Troubleshooting Common Issues

### Issue: "Backend not responding"
```bash
# Check if Flask is running
ps aux | grep python

# Check port 5000
netstat -tlnp | grep 5000

# Restart backend
cd /workspace/backend
source venv/bin/activate
python app.py
```

### Issue: "Valhalla not responding"
```bash
# Check Docker container
docker ps | grep valhalla

# Check port 8002
netstat -tlnp | grep 8002

# Restart Valhalla
docker stop valhalla
docker rm valhalla

cd /workspace/valhalla_data
docker run -d --name valhalla -p 8002:8002 \
  -v ${PWD}/valhalla_tiles.tar:/data/valhalla_tiles.tar \
  ghcr.io/valhalla/valhalla:3.4.0
```

### Issue: "Database locked" or "no such table"
```bash
# Reinitialize database
cd /workspace/backend
rm ../database/bahacks.db
python init_db.py

# Verify tables
sqlite3 ../database/bahacks.db ".tables"
```

### Issue: "Route calculation fails"
```bash
# Test Valhalla directly
curl -X POST http://localhost:8002/route \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      {"lat": 14.5995, "lon": 120.9842},
      {"lat": 14.5500, "lon": 121.0500}
    ],
    "costing": "auto"
  }'

# If this fails, tiles may not be built correctly
# Rebuild tiles (takes 60-90 min):
cd /workspace/valhalla_data
# Follow Phase 1 instructions in README.md
```

### Issue: "Reroute not triggering"
1. Check flood zone has `triggered_reroute=1`:
   ```bash
   sqlite3 ../database/bahacks.db "SELECT id, name, triggered_reroute FROM flood_zones;"
   ```

2. Check frontend console for errors (F12 → Console)

3. Verify polling is working:
   - Open browser DevTools → Network tab
   - Look for `/api/active-flood-zones` requests every 15s
   - Check response contains zones

4. Manually trigger reroute by adding verified report on route path

---

## 📊 Performance Benchmarks

| Operation | Expected Time | Acceptable |
|-----------|--------------|------------|
| API Health Check | <100ms | <500ms |
| Sensor List | <200ms | <1s |
| Submit Sensor Data | <300ms | <1s |
| Route Calculation | 1-3s | <5s |
| Route with Flood Avoidance | 2-5s | <10s |
| Flood Zone Polling | <200ms | <1s |
| Valhalla Direct | 500ms-2s | <5s |

Run performance tests:
```bash
python test_system.py  # Includes timing tests
```

---

## ✅ Pre-Demo Checklist

Before your thesis presentation:

- [ ] All services running (Valhalla, Flask, Frontend)
- [ ] Database initialized with test data
- [ ] At least 3 sensors added with different flood levels
- [ ] At least 2 active flood zones
- [ ] Test route calculated and saved
- [ ] Browser open at http://localhost:8080
- [ ] DevTools Console open (to show no errors)
- [ ] Test script passes: `python test_system.py`
- [ ] Backup plan: Screenshots/video if live demo fails

---

## 🎬 Demo Script (5-7 minutes)

### Minute 1: Introduction
- Show map centered on Philippines
- Explain sensor network (point to colored circles)
- Show legend (MMDA color coding)

### Minute 2: Live Sensor Data
- Show real-time readings
- Explain ESP32 hardware setup
- Submit new sensor reading via curl:
  ```bash
  curl -X POST http://localhost:5000/api/sensor-data \
    -d '{"device_id":"DEMO_SENSOR","flood_level_cm":45,...}'
  ```
- Watch map update within 30 seconds

### Minute 3: Crowdsourcing
- Click "Report Flood" button
- Submit report with photo
- Show pending status
- Submit 2 more nearby reports
- **Demo:** Auto-confirmation on 3rd report
- Show flood zone created automatically

### Minute 4: Routing
- Set start point (e.g., home)
- Set end point (e.g., school/office)
- Show calculated route
- Display turn-by-turn instructions
- Explain Valhalla integration

### Minute 5: DYNAMIC REROUTING (KEY FEATURE!)
- **While route is displayed**, submit emergency flood report ON the route:
  ```bash
  curl -X POST http://localhost:5000/api/reports \
    -d '{"lat":<route_lat>,"lon":<route_lon>,"description":"Emergency!","force_verify":true}'
  ```
- **Point to screen:** Watch for reroute banner (within 15s)
- Show route automatically recalculating
- Highlight new path avoiding flood
- Show updated turn-by-turn instructions

### Minute 6: Admin Features
- Show admin panel
- Verify pending report
- Add new sensor via UI
- Deactivate flood zone
- Show route returning to optimal path

### Minute 7: Q&A
- Show code structure
- Explain architecture decisions
- Discuss scalability improvements
- Answer questions

---

## 📝 Test Results Template

Save this for your thesis documentation:

```
BAHACKS System Test Results
Date: _______________
Tester: _____________

Automated Tests:
- Total: ___ / 25 passed
- Failed: ___ (list issues)

Manual Tests:
[ ] Backend responds to /api/status
[ ] Valhalla calculates routes
[ ] Sensors display on map
[ ] Flood zones render correctly
[ ] Route calculation works
[ ] Turn-by-turn instructions clear
[ ] Crowd reports submit successfully
[ ] Auto-confirmation triggers on 3rd report
[ ] Admin verification works
[ ] Dynamic rerouting activates
[ ] Reroute banner displays
[ ] Route updates within 15 seconds
[ ] Real-time polling functional
[ ] No console errors

Performance:
- Avg API response: _____ ms
- Avg route calc: _____ s
- Reroute trigger time: _____ s

Issues Found:
1. ________________________________
2. ________________________________
3. ________________________________

Overall Status: □ READY FOR DEMO  □ NEEDS FIXES
```

---

**Good luck with your thesis presentation! 🎓**
