#!/bin/bash
# BAHACKS - Quick Manual Testing Script
# Run individual tests without the full test suite

BASE_URL="http://localhost:5000"
VALHALLA_URL="http://localhost:8002"

echo "=========================================="
echo "BAHACKS - Quick Manual Tests"
echo "=========================================="
echo ""

# Test 1: Backend Health
echo "1. Testing Backend Health..."
curl -s "$BASE_URL/api/status" | python3 -m json.tool || echo "❌ Backend not responding"
echo ""

# Test 2: Valhalla Routing
echo "2. Testing Valhalla Routing..."
curl -s -X POST "$VALHALLA_URL/route" \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      {"lat": 14.5995, "lon": 120.9842},
      {"lat": 14.5500, "lon": 121.0500}
    ],
    "costing": "auto",
    "directions_options": {"units": "km"}
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✓ Route found!' if 'trip' in d else '❌ No route')" 2>/dev/null || echo "❌ Valhalla not responding"
echo ""

# Test 3: Add Sensor
echo "3. Adding Test Sensor..."
SENSOR_RESPONSE=$(curl -s -X POST "$BASE_URL/api/sensors" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "MANUAL_TEST_001",
    "name": "Manual Test Sensor",
    "lat": 14.5995,
    "lon": 120.9842,
    "location_name": "Test Location",
    "status": "active"
  }')
echo "$SENSOR_RESPONSE" | python3 -m json.tool
SENSOR_ID=$(echo "$SENSOR_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
echo "Sensor ID: $SENSOR_ID"
echo ""

# Test 4: Send Sensor Data (Normal)
echo "4. Sending Normal Sensor Reading (15cm)..."
curl -s -X POST "$BASE_URL/api/sensor-data" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "MANUAL_TEST_001",
    "flood_level_cm": 15,
    "rain_detected": false,
    "battery_voltage": 3.7
  }' | python3 -m json.tool
echo ""

# Test 5: Send Sensor Data (Flood)
echo "5. Sending Flood Sensor Reading (55cm) - Should Create Zone..."
curl -s -X POST "$BASE_URL/api/sensor-data" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "MANUAL_TEST_001",
    "flood_level_cm": 55,
    "rain_detected": true,
    "battery_voltage": 3.6
  }' | python3 -m json.tool
echo ""

# Test 6: Get Active Flood Zones
echo "6. Getting Active Flood Zones..."
curl -s "$BASE_URL/api/active-flood-zones" | python3 -m json.tool
echo ""

# Test 7: Submit Crowd Report
echo "7. Submitting Crowd Report..."
REPORT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/reports" \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 14.5800,
    "lon": 121.0200,
    "description": "Manual test flood report",
    "reporter_id": "manual_tester"
  }')
echo "$REPORT_RESPONSE" | python3 -m json.tool
REPORT_ID=$(echo "$REPORT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
echo "Report ID: $REPORT_ID"
echo ""

# Test 8: Calculate Route
echo "8. Calculating Route (Manila to Marikina)..."
ROUTE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/route" \
  -H "Content-Type: application/json" \
  -d '{
    "start_lat": 14.5995,
    "start_lon": 120.9842,
    "end_lat": 14.5500,
    "end_lon": 121.0500,
    "session_id": "manual_test_session"
  }')
echo "$ROUTE_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'route' in data:
    print(f\"✓ Route calculated!\")
    print(f\"  Distance: {data.get('distance_km', 'N/A')} km\")
    print(f\"  Instructions: {len(data.get('instructions', []))} steps\")
    if data.get('instructions'):
        print(f\"  First instruction: {data['instructions'][0].get('instruction', '')}\")
else:
    print('❌ No route found')
    print(json.dumps(data, indent=2))
" 2>/dev/null
echo ""

# Test 9: List All Sensors
echo "9. Listing All Sensors..."
curl -s "$BASE_URL/api/sensors" | python3 -c "
import sys, json
data = json.load(sys.stdin)
sensors = data.get('sensors', [])
print(f'Total sensors: {len(sensors)}')
for s in sensors:
    status_icon = '🟢' if s.get('status') == 'active' else '🔴'
    print(f\"  {status_icon} {s.get('name', 'Unknown')} - {s.get('location_name', '')}\")
" 2>/dev/null
echo ""

# Test 10: Get Flood Levels
echo "10. Getting Current Flood Levels..."
curl -s "$BASE_URL/api/flood-levels" | python3 -c "
import sys, json
data = json.load(sys.stdin)
readings = data.get('readings', [])
print(f'Total readings: {len(readings)}')
for r in readings[-5:]:  # Last 5 readings
    level = r.get('level_cm', 0)
    if level < 30:
        color = '🟢 Green'
    elif level < 60:
        color = '🟡 Yellow'
    elif level < 100:
        color = '🟠 Orange'
    else:
        color = '🔴 Red'
    print(f\"  {color}: {level}cm at {r.get('location_name', 'Unknown')}\")
" 2>/dev/null
echo ""

echo "=========================================="
echo "Manual Tests Complete!"
echo "=========================================="
echo ""
echo "Next Steps:"
echo "  - Open http://localhost:8080 in browser"
echo "  - Click on map to set start/end points"
echo "  - Watch real-time updates every 30 seconds"
echo "  - Try submitting flood reports"
echo ""
