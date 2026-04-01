/**
 * BAHACKS Frontend Application
 * Flood Detection & Safe Route Navigation with Dynamic Rerouting
 */

// ==================== CONFIGURATION ====================
const API_BASE_URL = 'http://localhost:5000/api';
const MAP_CENTER = [12.8797, 121.7740]; // Philippines center
const MAP_ZOOM = 7;
const POLL_INTERVAL = 15000; // 15 seconds for flood zone polling
const SENSOR_REFRESH_INTERVAL = 30000; // 30 seconds for sensor data

// ==================== GLOBAL STATE ====================
let map;
let markers = {};
let floodZones = {};
let crowdReports = [];
let currentRoute = null;
let routingControl = null;
let startMarker = null;
let endMarker = null;
let clickMode = 'start'; // 'start' or 'end'
let lastZoneHash = null;
let sessionID = generateSessionID();
let selectedReportLocation = null;

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadSensors();
    loadFloodZones();
    loadReports();
    startPolling();
    updateStatus();
});

// ==================== MAP INITIALIZATION ====================
function initMap() {
    // Initialize map centered on Philippines
    map = L.map('map').setView(MAP_CENTER, MAP_ZOOM);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);
    
    // Restrict bounds to Philippines area
    map.setMaxBounds([
        [4.0, 116.0], // Southwest corner
        [21.0, 127.0]  // Northeast corner
    ]);
    
    // Map click handler for setting route points
    map.on('click', (e) => {
        handleMapClick(e.latlng);
    });
}

function handleMapClick(latlng) {
    if (clickMode === 'start') {
        setStartPoint(latlng);
    } else {
        setEndPoint(latlng);
    }
}

function setStartPoint(latlng) {
    if (startMarker) {
        map.removeLayer(startMarker);
    }
    
    startMarker = L.marker(latlng, {
        draggable: true,
        title: 'Start Point'
    }).addTo(map);
    
    startMarker.on('dragend', (e) => {
        const newPos = e.target.getLatLng();
        document.getElementById('start-coords').value = `${newPos.lat.toFixed(6)}, ${newPos.lng.toFixed(6)}`;
    });
    
    document.getElementById('start-coords').value = `${latlng.lat.toFixed(6)}, ${latlng.lng.toFixed(6)}`;
    clickMode = 'end';
}

function setEndPoint(latlng) {
    if (endMarker) {
        map.removeLayer(endMarker);
    }
    
    endMarker = L.marker(latlng, {
        draggable: true,
        title: 'End Point'
    }).addTo(map);
    
    endMarker.on('dragend', (e) => {
        const newPos = e.target.getLatLng();
        document.getElementById('end-coords').value = `${newPos.lat.toFixed(6)}, ${newPos.lng.toFixed(6)}`;
    });
    
    document.getElementById('end-coords').value = `${latlng.lat.toFixed(6)}, ${latlng.lng.toFixed(6)}`;
    clickMode = 'start';
}

// ==================== ROUTING FUNCTIONS ====================
async function calculateRoute() {
    const startInput = document.getElementById('start-coords').value;
    const endInput = document.getElementById('end-coords').value;
    
    if (!startInput || !endInput) {
        alert('Please set both start and destination points');
        return;
    }
    
    try {
        const startCoords = parseCoordinates(startInput);
        const endCoords = parseCoordinates(endInput);
        
        if (!startCoords || !endCoords) {
            alert('Invalid coordinates format');
            return;
        }
        
        // Show loading state
        const banner = document.getElementById('reroute-banner');
        banner.textContent = '🔄 Calculating safe route...';
        banner.classList.add('active');
        
        const response = await fetch(`${API_BASE_URL}/route`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                start_lat: startCoords.lat,
                start_lon: startCoords.lon,
                end_lat: endCoords.lat,
                end_lon: endCoords.lon,
                session_id: sessionID
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayRoute(data);
            banner.textContent = '✓ Route calculated successfully';
            setTimeout(() => banner.classList.remove('active'), 2000);
        } else {
            alert('Route calculation failed: ' + (data.error || 'Unknown error'));
            banner.classList.remove('active');
        }
    } catch (error) {
        console.error('Route calculation error:', error);
        alert('Error calculating route: ' + error.message);
        document.getElementById('reroute-banner').classList.remove('active');
    }
}

function displayRoute(routeData) {
    // Clear existing route
    clearRoute();
    
    // Store current route for reroute tracking
    currentRoute = routeData;
    
    // Extract geometry and decode polyline
    const geometry = routeData.geometry;
    const latlngs = decodePolyline(geometry);
    
    // Draw route on map
    const routeLine = L.polyline(latlngs, {
        color: '#667eea',
        weight: 5,
        opacity: 0.7
    }).addTo(map);
    
    // Fit map to route
    map.fitBounds(routeLine.getBounds(), { padding: [50, 50] });
    
    // Display turn-by-turn instructions
    displayTurnByTurn(routeData.instructions);
    
    // Show route summary
    if (routeData.summary) {
        const summary = routeData.summary;
        const distance = (summary.length * 1000).toFixed(1);
        const time = Math.round(summary.time / 60);
        console.log(`Route: ${distance}m, ${time}min`);
    }
}

function displayTurnByTurn(instructions) {
    const container = document.getElementById('turn-by-turn');
    const section = document.getElementById('directions-section');
    
    if (!instructions || instructions.length === 0) {
        section.style.display = 'none';
        return;
    }
    
    section.style.display = 'block';
    container.innerHTML = '';
    
    instructions.forEach((instruction, index) => {
        const div = document.createElement('div');
        div.className = 'instruction';
        
        const type = instruction.type || 'Continue';
        const text = instruction.instruction || instruction.street || 'Continue';
        const distance = instruction.length ? (instruction.length * 1000).toFixed(0) + 'm' : '';
        
        div.innerHTML = `<strong>${index + 1}.</strong> ${text} ${distance ? `(${distance})` : ''}`;
        container.appendChild(div);
    });
}

function clearRoute() {
    if (routingControl) {
        map.removeControl(routingControl);
        routingControl = null;
    }
    
    if (startMarker) {
        map.removeLayer(startMarker);
        startMarker = null;
    }
    
    if (endMarker) {
        map.removeLayer(endMarker);
        endMarker = null;
    }
    
    currentRoute = null;
    document.getElementById('start-coords').value = '';
    document.getElementById('end-coords').value = '';
    document.getElementById('turn-by-turn').innerHTML = '';
    document.getElementById('directions-section').style.display = 'none';
}

// ==================== DYNAMIC REROUTING ====================
function startPolling() {
    setInterval(async () => {
        await checkForFloodZoneChanges();
    }, POLL_INTERVAL);
}

async function checkForFloodZoneChanges() {
    try {
        const response = await fetch(`${API_BASE_URL}/active-flood-zones`);
        const data = await response.json();
        
        // Create hash of current zones for comparison
        const zoneHash = hashZones(data.zones);
        
        // Check if zones have changed
        if (currentRoute && zoneHash !== lastZoneHash) {
            // Zones changed - trigger reroute!
            await triggerReroute(data.zones);
        }
        
        // Update displayed zones
        updateFloodZonesDisplay(data.zones);
        
        // Update hash
        lastZoneHash = zoneHash;
        
        // Update timestamp
        document.getElementById('last-update').textContent = `Last update: ${new Date().toLocaleTimeString()}`;
        
    } catch (error) {
        console.error('Polling error:', error);
    }
}

async function triggerReroute(zones) {
    console.log('🌊 Flood zones changed - triggering reroute!');
    
    // Show reroute banner
    const banner = document.getElementById('reroute-banner');
    banner.textContent = '🌊 New flood detected - Finding safe alternative route...';
    banner.classList.add('active');
    
    // Play alert sound
    playRerouteAlert();
    
    // Recalculate route with new exclusions
    await calculateRoute();
    
    // Hide banner after completion
    setTimeout(() => {
        banner.textContent = '✓ Route updated to avoid flooded area';
        setTimeout(() => banner.classList.remove('active'), 3000);
    }, 1000);
}

function playRerouteAlert() {
    // Generate a simple beep using Web Audio API
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    } catch (error) {
        console.log('Audio alert not supported');
    }
}

function hashZones(zones) {
    // Create a simple hash from zone IDs and timestamps
    return zones.map(z => `${z.id}-${z.created_at}`).join('|');
}

// ==================== SENSOR FUNCTIONS ====================
async function loadSensors() {
    try {
        const response = await fetch(`${API_BASE_URL}/sensors`);
        const data = await response.json();
        
        // Clear existing markers
        Object.values(markers).forEach(marker => map.removeLayer(marker));
        markers = {};
        
        // Add markers for each sensor
        data.sensors.forEach(sensor => {
            const color = getFloodColor(sensor.flood_category || 'green');
            
            const circle = L.circle([sensor.lat, sensor.lon], {
                radius: 500,
                fillColor: color,
                color: '#333',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.4
            }).addTo(map);
            
            circle.bindPopup(`
                <strong>${sensor.name}</strong><br>
                Location: ${sensor.location_name || 'N/A'}<br>
                Flood Level: ${sensor.level_cm ? sensor.level_cm.toFixed(1) + ' cm' : 'No data'}<br>
                Status: ${sensor.status}<br>
                Battery: ${sensor.battery_level ? sensor.battery_level.toFixed(2) + 'V' : 'N/A'}<br>
                Last Reading: ${sensor.reading_timestamp || 'Never'}
            `);
            
            markers[sensor.id] = circle;
        });
        
        // Update admin panel sensor list
        updateAdminSensorList(data.sensors);
        
    } catch (error) {
        console.error('Error loading sensors:', error);
    }
}

async function loadFloodZones() {
    try {
        const response = await fetch(`${API_BASE_URL}/active-flood-zones`);
        const data = await response.json();
        updateFloodZonesDisplay(data.zones);
        lastZoneHash = hashZones(data.zones);
    } catch (error) {
        console.error('Error loading flood zones:', error);
    }
}

function updateFloodZonesDisplay(zones) {
    // Remove old zones
    Object.values(floodZones).forEach(zone => map.removeLayer(zone));
    floodZones = {};
    
    // Add new zones
    zones.forEach(zone => {
        if (zone.polygon) {
            const polygon = L.geoJSON(zone.polygon, {
                style: {
                    fillColor: getFloodColor(zone.flood_level),
                    color: '#333',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.3
                }
            }).addTo(map);
            
            polygon.bindPopup(`
                <strong>${zone.name || 'Flood Zone'}</strong><br>
                Level: ${zone.flood_level}<br>
                Source: ${zone.source}<br>
                Created: ${new Date(zone.created_at).toLocaleString()}<br>
                Expires: ${zone.expires_at ? new Date(zone.expires_at).toLocaleString() : 'N/A'}
            `);
            
            floodZones[zone.id] = polygon;
        }
    });
}

function getFloodColor(level) {
    switch (level) {
        case 'green': return '#48bb78';
        case 'yellow': return '#ecc94b';
        case 'orange': return '#ed8936';
        case 'red': return '#f56565';
        default: return '#48bb78';
    }
}

// Start auto-refresh for sensors
setInterval(loadSensors, SENSOR_REFRESH_INTERVAL);

// ==================== CROWD REPORTS ====================
async function loadReports() {
    try {
        const response = await fetch(`${API_BASE_URL}/reports`);
        const data = await response.json();
        crowdReports = data.reports;
        displayReports(crowdReports);
    } catch (error) {
        console.error('Error loading reports:', error);
    }
}

function displayReports(reports) {
    const container = document.getElementById('reports-list');
    
    if (!reports || reports.length === 0) {
        container.innerHTML = '<p style="color: #999; font-size: 12px;">No reports yet</p>';
        return;
    }
    
    container.innerHTML = '';
    
    // Show only recent reports (last 10)
    reports.slice(0, 10).forEach(report => {
        const div = document.createElement('div');
        div.className = `report-item ${report.status}`;
        div.innerHTML = `
            <h4>${report.status.toUpperCase()}</h4>
            <p>${report.description || 'No description'}</p>
            <p style="font-size: 10px; color: #999;">
                ${new Date(report.created_at).toLocaleString()}
            </p>
        `;
        container.appendChild(div);
    });
}

// ==================== REPORT MODAL ====================
function openReportModal() {
    const modal = document.getElementById('report-modal');
    
    // Get location from map center or last clicked point
    const center = map.getCenter();
    selectedReportLocation = {
        lat: center.lat,
        lon: center.lng
    };
    
    document.getElementById('report-location').value = 
        `${selectedReportLocation.lat.toFixed(6)}, ${selectedReportLocation.lon.toFixed(6)}`;
    
    modal.classList.add('active');
}

function closeReportModal() {
    document.getElementById('report-modal').classList.remove('active');
    document.getElementById('report-description').value = '';
    document.getElementById('reporter-name').value = '';
}

async function submitReport() {
    const description = document.getElementById('report-description').value;
    const reporterName = document.getElementById('reporter-name').value || 'anonymous';
    
    if (!selectedReportLocation) {
        alert('Please select a location first');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/reports`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                lat: selectedReportLocation.lat,
                lon: selectedReportLocation.lon,
                description: description,
                reporter_id: reporterName
            })
        });
        
        const data = await response.json();
        
        if (data.report_id) {
            alert(`Report submitted successfully!\nStatus: ${data.status}\n${data.zone_created ? 'Flood zone created!' : ''}`);
            closeReportModal();
            loadReports();
            loadFloodZones();
        } else {
            alert('Error submitting report: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Submit report error:', error);
        alert('Error submitting report: ' + error.message);
    }
}

// ==================== ADMIN FUNCTIONS ====================
function toggleAdminPanel() {
    const panel = document.getElementById('admin-panel');
    panel.classList.toggle('active');
    
    if (panel.classList.contains('active')) {
        loadSensors(); // Refresh sensor list
    }
}

async function addSensor() {
    const deviceId = document.getElementById('admin-device-id').value;
    const name = document.getElementById('admin-sensor-name').value;
    const lat = document.getElementById('admin-sensor-lat').value;
    const lon = document.getElementById('admin-sensor-lon').value;
    const locationName = document.getElementById('admin-location-name').value;
    
    if (!deviceId || !name || !lat || !lon) {
        alert('Please fill in all required fields');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/sensors`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'bahacks_admin_key_2024'
            },
            body: JSON.stringify({
                device_id: deviceId,
                name: name,
                lat: parseFloat(lat),
                lon: parseFloat(lon),
                location_name: locationName
            })
        });
        
        const data = await response.json();
        
        if (data.sensor_id) {
            alert('Sensor added successfully!');
            document.getElementById('admin-device-id').value = '';
            document.getElementById('admin-sensor-name').value = '';
            document.getElementById('admin-sensor-lat').value = '';
            document.getElementById('admin-sensor-lon').value = '';
            document.getElementById('admin-location-name').value = '';
            loadSensors();
        } else {
            alert('Error adding sensor: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Add sensor error:', error);
        alert('Error adding sensor: ' + error.message);
    }
}

async function deleteSensor(sensorId) {
    if (!confirm('Are you sure you want to delete this sensor?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/sensors/${sensorId}`, {
            method: 'DELETE',
            headers: {
                'X-API-Key': 'bahacks_admin_key_2024'
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('Sensor deleted successfully');
            loadSensors();
        } else {
            alert('Error deleting sensor: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Delete sensor error:', error);
        alert('Error deleting sensor: ' + error.message);
    }
}

function updateAdminSensorList(sensors) {
    const container = document.getElementById('admin-sensor-list');
    
    if (!sensors || sensors.length === 0) {
        container.innerHTML = '<p style="color: #999; font-size: 12px;">No sensors registered</p>';
        return;
    }
    
    container.innerHTML = '';
    
    sensors.forEach(sensor => {
        const div = document.createElement('div');
        div.className = 'sensor-item';
        div.innerHTML = `
            <span>${sensor.name} (${sensor.device_id})</span>
            <button class="btn-danger" onclick="deleteSensor(${sensor.id})">Delete</button>
        `;
        container.appendChild(div);
    });
}

// ==================== SYSTEM STATUS ====================
async function updateStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/status`);
        const data = await response.json();
        
        const statusEl = document.getElementById('system-status');
        
        if (data.status === 'healthy') {
            statusEl.textContent = '● System Online';
            statusEl.style.color = '#48bb78';
        } else {
            statusEl.textContent = '● System Warning';
            statusEl.style.color = '#ecc94b';
        }
    } catch (error) {
        const statusEl = document.getElementById('system-status');
        statusEl.textContent = '● System Offline';
        statusEl.style.color = '#f56565';
    }
}

// Update status every 30 seconds
setInterval(updateStatus, 30000);

// ==================== UTILITY FUNCTIONS ====================
function parseCoordinates(input) {
    const parts = input.split(',').map(s => s.trim());
    if (parts.length !== 2) return null;
    
    const lat = parseFloat(parts[0]);
    const lon = parseFloat(parts[1]);
    
    if (isNaN(lat) || isNaN(lon)) return null;
    
    return { lat, lon };
}

function generateSessionID() {
    return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
}

function decodePolyline(encoded, precision = 5) {
    const points = [];
    let index = 0;
    let lat = 0;
    let lng = 0;
    
    while (index < encoded.length) {
        // Latitude
        let shift = 0;
        let result = 0;
        while (true) {
            const b = encoded.charCodeAt(index) - 63;
            index++;
            result |= (b & 0x1f) << shift;
            shift += 5;
            if (!(b >= 0x20)) break;
        }
        const dlat = (result & 1) ? ~(result >> 1) : (result >> 1);
        lat += dlat;
        
        // Longitude
        shift = 0;
        result = 0;
        while (true) {
            const b = encoded.charCodeAt(index) - 63;
            index++;
            result |= (b & 0x1f) << shift;
            shift += 5;
            if (!(b >= 0x20)) break;
        }
        const dlng = (result & 1) ? ~(result >> 1) : (result >> 1);
        lng += dlng;
        
        points.push([lat / Math.pow(10, precision), lng / Math.pow(10, precision)]);
    }
    
    return points;
}

console.log('BAHACKS Frontend initialized');
console.log('Session ID:', sessionID);
console.log('Polling interval:', POLL_INTERVAL / 1000, 'seconds');
