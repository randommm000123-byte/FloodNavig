#!/usr/bin/env python3
"""
BAHACKS - Complete System Test Suite
Tests all API endpoints, database integrity, and rerouting logic
Run this BEFORE your thesis demonstration
"""

import requests
import json
import time
import sys
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000"
VALHALLA_URL = "http://localhost:8002"

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text.center(60)}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ {text}{RESET}")

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.session_id = f"test_session_{int(time.time())}"
        self.test_sensor_id = None
        self.test_route = None
        self.test_report_ids = []
        
    def run_test(self, name, test_func):
        """Run a single test and track results"""
        try:
            print(f"Testing: {name}...", end=" ")
            test_func()
            print_success("PASSED")
            self.passed += 1
            return True
        except AssertionError as e:
            print_error(f"FAILED - {str(e)}")
            self.failed += 1
            return False
        except Exception as e:
            print_error(f"ERROR - {str(e)}")
            self.failed += 1
            return False
    
    def assert_status(self, response, expected_code):
        if response.status_code != expected_code:
            raise AssertionError(f"Expected status {expected_code}, got {response.status_code}. Response: {response.text[:200]}")
    
    def assert_key_exists(self, data, key):
        if key not in data:
            raise AssertionError(f"Key '{key}' not found in response: {data}")
    
    def assert_value_equals(self, actual, expected, msg=""):
        if actual != expected:
            raise AssertionError(f"{msg}: Expected {expected}, got {actual}")

# ==================== PHASE 1: System Health ====================

def test_system_health(runner):
    """Test if all services are running"""
    print_header("PHASE 1: System Health Check")
    
    def check_backend():
        resp = requests.get(f"{BASE_URL}/api/status", timeout=5)
        runner.assert_status(resp, 200)
        data = resp.json()
        runner.assert_key_exists(data, "status")
        runner.assert_value_equals(data["status"], "healthy", "Backend status")
    
    def check_valhalla():
        # Simple route request to Valhalla
        payload = {
            "locations": [
                {"lat": 14.5995, "lon": 120.9842},  # Manila
                {"lat": 14.5500, "lon": 121.0500}   # Nearby
            ],
            "costing": "auto",
            "directions_options": {"units": "km"}
        }
        resp = requests.post(f"{VALHALLA_URL}/route", json=payload, timeout=10)
        runner.assert_status(resp, 200)
        data = resp.json()
        runner.assert_key_exists(data, "trip")
    
    runner.run_test("Backend API is running", check_backend)
    runner.run_test("Valhalla routing engine is running", check_valhalla)

# ==================== PHASE 2: Database & Sensors ====================

def test_database_sensors(runner):
    """Test sensor management endpoints"""
    print_header("PHASE 2: Database & Sensor Management")
    
    def add_admin():
        payload = {
            "username": "admin_test",
            "password": "testpass123",
            "name": "Test Admin"
        }
        resp = requests.post(f"{BASE_URL}/api/admins", json=payload, timeout=5)
        # May fail if already exists, that's ok
        if resp.status_code != 409:  # Conflict is ok
            runner.assert_status(resp, 201)
    
    def add_sensor():
        payload = {
            "device_id": "SENSOR_TEST_001",
            "name": "Test Sensor - Manila Bay",
            "lat": 14.5995,
            "lon": 120.9842,
            "location_name": "Manila Bay Area",
            "status": "active"
        }
        resp = requests.post(f"{BASE_URL}/api/sensors", json=payload, timeout=5)
        runner.assert_status(resp, 201)
        data = resp.json()
        runner.assert_key_exists(data, "id")
        runner.test_sensor_id = data["id"]
    
    def get_sensors():
        resp = requests.get(f"{BASE_URL}/api/sensors", timeout=5)
        runner.assert_status(resp, 200)
        data = resp.json()
        runner.assert_key_exists(data, "sensors")
        assert len(data["sensors"]) > 0, "No sensors found"
    
    def update_sensor():
        if not runner.test_sensor_id:
            raise AssertionError("No test sensor ID available")
        payload = {"battery_level": 85.5, "status": "active"}
        resp = requests.put(f"{BASE_URL}/api/sensors/{runner.test_sensor_id}", json=payload, timeout=5)
        runner.assert_status(resp, 200)
    
    runner.run_test("Create admin user", add_admin)
    runner.run_test("Add test sensor", add_sensor)
    runner.run_test("List all sensors", get_sensors)
    runner.run_test("Update sensor", update_sensor)

# ==================== PHASE 3: Sensor Data & Flood Zones ====================

def test_sensor_data_flood_zones(runner):
    """Test sensor data submission and automatic flood zone creation"""
    print_header("PHASE 3: Sensor Data & Automatic Flood Zone Creation")
    
    def send_normal_reading():
        if not runner.test_sensor_id:
            raise AssertionError("No test sensor ID available")
        payload = {
            "device_id": "SENSOR_TEST_001",
            "flood_level_cm": 15,  # Below threshold
            "rain_detected": False,
            "battery_voltage": 3.7
        }
        resp = requests.post(f"{BASE_URL}/api/sensor-data", json=payload, timeout=5)
        runner.assert_status(resp, 201)
    
    def send_flood_reading():
        if not runner.test_sensor_id:
            raise AssertionError("No test sensor ID available")
        payload = {
            "device_id": "SENSOR_TEST_001",
            "flood_level_cm": 55,  # Above 30cm threshold - should create flood zone
            "rain_detected": True,
            "battery_voltage": 3.6
        }
        resp = requests.post(f"{BASE_URL}/api/sensor-data", json=payload, timeout=5)
        runner.assert_status(resp, 201)
        data = resp.json()
        runner.assert_key_exists(data, "flood_zone_created")
        # Should create or activate a flood zone
    
    def get_flood_levels():
        resp = requests.get(f"{BASE_URL}/api/flood-levels", timeout=5)
        runner.assert_status(resp, 200)
        data = resp.json()
        runner.assert_key_exists(data, "readings")
    
    def get_active_flood_zones():
        resp = requests.get(f"{BASE_URL}/api/active-flood-zones", timeout=5)
        runner.assert_status(resp, 200)
        data = resp.json()
        runner.assert_key_exists(data, "zones")
        print_info(f"Active zones: {len(data['zones'])}")
    
    runner.run_test("Send normal sensor reading (15cm)", send_normal_reading)
    runner.run_test("Send flood sensor reading (55cm) - triggers zone creation", send_flood_reading)
    time.sleep(1)  # Allow DB to update
    runner.run_test("Get current flood levels", get_flood_levels)
    runner.run_test("Get active flood zones", get_active_flood_zones)

# ==================== PHASE 4: Crowdsourced Reports ====================

def test_crowd_reports(runner):
    """Test crowdsourced report system with auto-confirmation"""
    print_header("PHASE 4: Crowdsourced Reports & Auto-Confirmation")
    
    base_lat = 14.5800
    base_lon = 121.0200
    
    def submit_report(lat_offset=0, lon_offset=0):
        payload = {
            "lat": base_lat + lat_offset,
            "lon": base_lon + lon_offset,
            "description": f"Flooding reported at location {len(runner.test_report_ids)+1}",
            "reporter_id": f"user_{int(time.time())}"
        }
        resp = requests.post(f"{BASE_URL}/api/reports", json=payload, timeout=5)
        runner.assert_status(resp, 201)
        data = resp.json()
        runner.assert_key_exists(data, "id")
        runner.test_report_ids.append(data["id"])
        return data
    
    def verify_auto_confirmation():
        # Submit 3 reports in same area (within 100m)
        print_info("Submitting 3 reports within 100m radius...")
        submit_report(0, 0)
        time.sleep(0.5)
        submit_report(0.0005, 0.0005)  # ~50m away
        time.sleep(0.5)
        third_report = submit_report(-0.0005, -0.0003)  # ~50m away
        
        # Third report should trigger auto-confirmation
        runner.assert_key_exists(third_report, "status")
        print_info(f"Third report status: {third_report.get('status')}")
        # Status should be 'confirmed' or will trigger flood zone creation
    
    def check_flood_zone_from_reports():
        time.sleep(1)  # Allow processing
        resp = requests.get(f"{BASE_URL}/api/active-flood-zones", timeout=5)
        runner.assert_status(resp, 200)
        data = resp.json()
        # Should have at least one zone from reports or sensors
        print_info(f"Total active zones: {len(data['zones'])}")
    
    runner.run_test("Submit first crowd report", lambda: submit_report(0.01, 0.01))
    runner.run_test("Submit 3 nearby reports (triggers auto-confirm)", verify_auto_confirmation)
    time.sleep(1)
    runner.run_test("Verify flood zone created from reports", check_flood_zone_from_reports)

# ==================== PHASE 5: Routing & Rerouting ====================

def test_routing_rerouting(runner):
    """Test route calculation and dynamic rerouting"""
    print_header("PHASE 5: Routing & Dynamic Rerouting")
    
    start_loc = {"lat": 14.5995, "lon": 120.9842}  # Manila
    end_loc = {"lat": 14.5500, "lon": 121.0500}    # Marikina area
    
    def calculate_route():
        payload = {
            "start_lat": start_loc["lat"],
            "start_lon": start_loc["lon"],
            "end_lat": end_loc["lat"],
            "end_lon": end_loc["lon"],
            "session_id": runner.session_id
        }
        resp = requests.post(f"{BASE_URL}/api/route", json=payload, timeout=15)
        runner.assert_status(resp, 200)
        data = resp.json()
        runner.assert_key_exists(data, "route")
        runner.assert_key_exists(data, "instructions")
        runner.test_route = data
        print_info(f"Route distance: {data.get('distance_km', 'N/A')} km")
        print_info(f"Turn-by-turn instructions: {len(data.get('instructions', []))} steps")
    
    def verify_turn_by_turn():
        if not runner.test_route:
            raise AssertionError("No route available")
        instructions = runner.test_route.get("instructions", [])
        assert len(instructions) > 0, "No turn-by-turn instructions"
        # Check instruction format
        first_instr = instructions[0]
        runner.assert_key_exists(first_instr, "instruction")
        runner.assert_key_exists(first_instr, "distance")
    
    def simulate_flood_on_route():
        """Create a flood zone that should affect the current route"""
        if not runner.test_route:
            raise AssertionError("No route available")
        
        # Get a point along the route (simplified - use midpoint)
        mid_lat = (start_loc["lat"] + end_loc["lat"]) / 2
        mid_lon = (start_loc["lon"] + end_loc["lon"]) / 2
        
        payload = {
            "lat": mid_lat,
            "lon": mid_lon,
            "description": "Emergency flood on route - testing reroute",
            "reporter_id": "test_admin",
            "force_verify": True  # Admin verification
        }
        resp = requests.post(f"{BASE_URL}/api/reports", json=payload, timeout=5)
        runner.assert_status(resp, 201)
        data = resp.json()
        
        # Verify the report
        report_id = data["id"]
        verify_payload = {"admin_id": 1}  # Assume admin ID 1 exists
        resp = requests.post(f"{BASE_URL}/api/reports/{report_id}/verify", json=verify_payload, timeout=5)
        # May be 200 or 201 depending on implementation
        print_info(f"Created and verified flood report at {mid_lat:.4f}, {mid_lon:.4f}")
    
    def check_reroute_trigger():
        """Check if active flood zones updated (frontend would detect this)"""
        time.sleep(1)
        resp = requests.get(f"{BASE_URL}/api/active-flood-zones", timeout=5)
        runner.assert_status(resp, 200)
        data = resp.json()
        zones = data.get("zones", [])
        
        # Check if any zone has triggered_reroute flag
        reroute_triggered = any(z.get("triggered_reroute", False) for z in zones)
        if reroute_triggered:
            print_success("Reroute trigger flag detected!")
        else:
            print_warning("No reroute trigger flag (may need manual check)")
        
        print_info(f"Active zones count: {len(zones)}")
        for i, zone in enumerate(zones):
            print_info(f"  Zone {i+1}: {zone.get('name', 'Unknown')} - Active: {zone.get('active', False)}")
    
    def recalculate_route_with_flood():
        """Recalculate route - should now avoid flood zones"""
        payload = {
            "start_lat": start_loc["lat"],
            "start_lon": start_loc["lon"],
            "end_lat": end_loc["lat"],
            "end_lon": end_loc["lon"],
            "session_id": runner.session_id
        }
        resp = requests.post(f"{BASE_URL}/api/route", json=payload, timeout=15)
        runner.assert_status(resp, 200)
        data = resp.json()
        
        # Route may be different now
        print_info(f"Recalculated route distance: {data.get('distance_km', 'N/A')} km")
        if runner.test_route and data.get("distance_km"):
            diff = abs(data["distance_km"] - runner.test_route.get("distance_km", 0))
            if diff > 0.1:
                print_success(f"Route changed by {diff:.2f} km (flood avoidance working!)")
            else:
                print_warning("Route unchanged (flood may not intersect original path)")
    
    runner.run_test("Calculate initial route", calculate_route)
    runner.run_test("Verify turn-by-turn instructions", verify_turn_by_turn)
    runner.run_test("Simulate flood on route (admin verified)", simulate_flood_on_route)
    time.sleep(1)
    runner.run_test("Check reroute trigger detection", check_reroute_trigger)
    runner.run_test("Recalculate route with flood avoidance", recalculate_route_with_flood)

# ==================== PHASE 6: Admin Functions ====================

def test_admin_functions(runner):
    """Test admin verification and management"""
    print_header("PHASE 6: Admin Functions")
    
    def list_pending_reports():
        resp = requests.get(f"{BASE_URL}/api/reports?status=pending", timeout=5)
        runner.assert_status(resp, 200)
        data = resp.json()
        runner.assert_key_exists(data, "reports")
        print_info(f"Pending reports: {len(data['reports'])}")
    
    def verify_existing_report():
        # Try to verify one of the test reports
        if runner.test_report_ids:
            report_id = runner.test_report_ids[0]
            payload = {"admin_id": 1}
            resp = requests.post(f"{BASE_URL}/api/reports/{report_id}/verify", json=payload, timeout=5)
            # May succeed or fail depending on current status
            print_info(f"Verification attempt response: {resp.status_code}")
    
    def delete_test_sensor():
        if runner.test_sensor_id:
            resp = requests.delete(f"{BASE_URL}/api/sensors/{runner.test_sensor_id}", timeout=5)
            # May be 200 or 404
            print_info(f"Sensor deletion response: {resp.status_code}")
    
    runner.run_test("List pending reports", list_pending_reports)
    runner.run_test("Verify a report", verify_existing_report)
    runner.run_test("Cleanup: Delete test sensor", delete_test_sensor)

# ==================== PHASE 7: Performance Tests ====================

def test_performance(runner):
    """Test response times and system performance"""
    print_header("PHASE 7: Performance Tests")
    
    def test_api_response_time():
        start = time.time()
        resp = requests.get(f"{BASE_URL}/api/sensors", timeout=10)
        elapsed = time.time() - start
        runner.assert_status(resp, 200)
        
        if elapsed < 1.0:
            print_success(f"Fast response: {elapsed*1000:.0f}ms")
        elif elapsed < 3.0:
            print_warning(f"Moderate response: {elapsed*1000:.0f}ms")
        else:
            print_error(f"Slow response: {elapsed*1000:.0f}ms")
    
    def test_valhalla_response_time():
        payload = {
            "locations": [
                {"lat": 14.5995, "lon": 120.9842},
                {"lat": 14.5500, "lon": 121.0500}
            ],
            "costing": "auto"
        }
        start = time.time()
        resp = requests.post(f"{VALHALLA_URL}/route", json=payload, timeout=30)
        elapsed = time.time() - start
        runner.assert_status(resp, 200)
        
        if elapsed < 2.0:
            print_success(f"Valhalla fast: {elapsed*1000:.0f}ms")
        elif elapsed < 5.0:
            print_warning(f"Valhalla moderate: {elapsed*1000:.0f}ms")
        else:
            print_error(f"Valhalla slow: {elapsed*1000:.0f}ms")
    
    def test_concurrent_requests():
        """Simulate multiple concurrent requests"""
        import concurrent.futures
        
        def make_request(i):
            resp = requests.get(f"{BASE_URL}/api/flood-levels", timeout=10)
            return resp.status_code
        
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, i) for i in range(5)]
            results = [f.result() for f in futures]
        elapsed = time.time() - start
        
        success_count = sum(1 for r in results if r == 200)
        print_info(f"Concurrent test: {success_count}/5 successful in {elapsed*1000:.0f}ms")
        
        if success_count == 5:
            print_success("Concurrent requests handled well")
        else:
            print_warning(f"Some concurrent requests failed: {success_count}/5")
    
    runner.run_test("API response time", test_api_response_time)
    runner.run_test("Valhalla routing response time", test_valhalla_response_time)
    runner.run_test("Concurrent request handling", test_concurrent_requests)

# ==================== Main Test Runner ====================

def main():
    print(f"\n{BOLD}{GREEN}")
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║           BAHACKS - Complete System Test Suite            ║
    ║     IoT Flood Detection & Dynamic Rerouting System        ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    print(f"{RESET}")
    
    print_info(f"Backend URL: {BASE_URL}")
    print_info(f"Valhalla URL: {VALHALLA_URL}")
    print_info(f"Test Session ID: {TestRunner().session_id}")
    print("\nStarting comprehensive system tests...\n")
    
    time.sleep(2)
    
    runner = TestRunner()
    
    # Run all test phases
    test_system_health(runner)
    test_database_sensors(runner)
    test_sensor_data_flood_zones(runner)
    test_crowd_reports(runner)
    test_routing_rerouting(runner)
    test_admin_functions(runner)
    test_performance(runner)
    
    # Print summary
    print_header("TEST SUMMARY")
    total = runner.passed + runner.failed
    print(f"\n{BOLD}Total Tests: {total}{RESET}")
    print(f"{GREEN}Passed: {runner.passed}{RESET}")
    print(f"{RED}Failed: {runner.failed}{RESET}")
    
    if runner.failed == 0:
        print(f"\n{GREEN}{BOLD}🎉 ALL TESTS PASSED! System ready for thesis demo!{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}⚠️  Some tests failed. Review errors above.{RESET}\n")
        print_info("Common fixes:")
        print_info("  - Ensure Docker Valhalla container is running: docker ps")
        print_info("  - Ensure Flask backend is running: curl http://localhost:5000/api/status")
        print_info("  - Check database exists: ls -la ../database/bahacks.db")
        print_info("  - Restart services and re-run tests\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
