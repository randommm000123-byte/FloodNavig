/*
 * BAHACKS - ESP32 Flood Sensor Firmware
 * IoT-based Real-time Flood Level Detection
 * 
 * Hardware:
 * - ESP32 DevKit
 * - HC-SR04 Ultrasonic Sensor (with voltage divider for ECHO)
 * - Rain Sensor Module
 * - LoRa SX1278 (optional for long-range)
 * - Solar Charger + 3.7V Battery
 * 
 * Pins:
 * - TRIG: GPIO 12
 * - ECHO: GPIO 13 (via voltage divider)
 * - RAIN: GPIO 14 (A0 analog)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <esp_task_wdt.h>

// ==================== CONFIGURATION ====================
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Backend API endpoint
const char* API_HOST = "192.168.1.100";  // Your laptop IP
const int API_PORT = 5000;
const String API_ENDPOINT = "/api/sensor-data";

// Device identification
const String DEVICE_ID = "ESP32_FLOOD_001";
const String SENSOR_NAME = "Main Street Sensor";
const float SENSOR_LAT = 14.5995;      // Manila coordinates (example)
const float SENSOR_LON = 120.9842;
const String LOCATION_NAME = "Main Street, Manila";

// Sensor mounting height (cm) - distance from sensor to ground when dry
const float SENSOR_MOUNT_HEIGHT = 100.0;

// Pins
#define TRIG_PIN 12
#define ECHO_PIN 13
#define RAIN_PIN 14

// Timing
const unsigned long MEASURE_INTERVAL = 5000;    // Measure every 5 seconds
const unsigned long SEND_INTERVAL = 30000;      // Send every 30 seconds
const float RAPID_RISE_THRESHOLD = 20.0;        // Rapid rise threshold (cm)

// ==================== GLOBAL VARIABLES ====================
unsigned long lastMeasureTime = 0;
unsigned long lastSendTime = 0;
float lastFloodLevel = 0;
float currentFloodLevel = 0;
float batteryVoltage = 3.7;
bool wifiConnected = false;
int rapidRiseCount = 0;

// ==================== SETUP ====================
void setup() {
    Serial.begin(115200);
    Serial.println("\n\n=== BAHACKS Flood Sensor Starting ===");
    
    // Configure pins
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(RAIN_PIN, INPUT);
    
    // Initial WiFi connection
    connectWiFi();
    
    // Disable watchdog
    esp_task_wdt_init(10, false);
    
    Serial.println("=== Sensor Ready ===\n");
}

// ==================== MAIN LOOP ====================
void loop() {
    // Maintain WiFi connection
    if (!wifiConnected || WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi disconnected, reconnecting...");
        connectWiFi();
        delay(1000);
        return;
    }
    
    unsigned long currentTime = millis();
    
    // Measure distance every 5 seconds
    if (currentTime - lastMeasureTime >= MEASURE_INTERVAL) {
        lastMeasureTime = currentTime;
        measureSensor();
    }
    
    // Send data every 30 seconds OR on rapid rise
    if (currentTime - lastSendTime >= SEND_INTERVAL) {
        sendSensorData();
        lastSendTime = currentTime;
    }
    
    // Small delay to prevent watchdog trigger
    delay(100);
}

// ==================== WIFI CONNECTION ====================
void connectWiFi() {
    Serial.print("Connecting to WiFi: ");
    Serial.println(WIFI_SSID);
    
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi connected!");
        Serial.print("IP Address: ");
        Serial.println(WiFi.localIP());
        wifiConnected = true;
    } else {
        Serial.println("\nWiFi connection failed!");
        wifiConnected = false;
        delay(2000);
    }
}

// ==================== SENSOR MEASUREMENT ====================
void measureSensor() {
    // Measure ultrasonic distance
    float distance = readUltrasonic();
    
    // Read rain sensor
    bool rainDetected = readRainSensor();
    
    // Calculate flood level
    // Flood level = mount height - measured distance
    // If distance > mount height, flood level is 0 (no flood)
    if (distance > 0 && distance < SENSOR_MOUNT_HEIGHT) {
        currentFloodLevel = SENSOR_MOUNT_HEIGHT - distance;
    } else {
        currentFloodLevel = 0;
    }
    
    // Check for rapid rise (potential flash flood)
    float riseAmount = currentFloodLevel - lastFloodLevel;
    if (riseAmount > RAPID_RISE_THRESHOLD && currentFloodLevel > 30) {
        rapidRiseCount++;
        Serial.println("⚠️ RAPID FLOOD RISE DETECTED!");
        
        // Send immediately if rapid rise detected twice
        if (rapidRiseCount >= 2 && wifiConnected) {
            Serial.println("🚨 Sending emergency alert due to rapid rise!");
            sendSensorData();
            lastSendTime = millis();
            rapidRiseCount = 0;
        }
    } else {
        rapidRiseCount = 0;
    }
    
    // Print readings
    Serial.print("Distance: ");
    Serial.print(distance);
    Serial.print(" cm | Flood Level: ");
    Serial.print(currentFloodLevel);
    Serial.print(" cm | Rain: ");
    Serial.println(rainDetected ? "YES" : "NO");
    
    lastFloodLevel = currentFloodLevel;
}

float readUltrasonic() {
    // Clear TRIG pin
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    
    // Send 10us pulse
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    
    // Read ECHO pin with timeout
    unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000);
    
    // Calculate distance (speed of sound = 343 m/s = 0.0343 cm/us)
    // Distance = (duration * 0.0343) / 2 (round trip)
    if (duration == 0) {
        return -1; // Timeout
    }
    
    float distance = (duration * 0.0343) / 2.0;
    return distance;
}

bool readRainSensor() {
    // Read analog value from rain sensor
    int rainValue = analogRead(RAIN_PIN);
    
    // Threshold may need adjustment based on your sensor
    // Lower values = more water = rain detected
    const int RAIN_THRESHOLD = 2000;
    
    return rainValue < RAIN_THRESHOLD;
}

// ==================== DATA TRANSMISSION ====================
void sendSensorData() {
    if (!wifiConnected) {
        Serial.println("Cannot send: WiFi not connected");
        return;
    }
    
    // Build JSON payload
    StaticJsonDocument<256> doc;
    doc["device_id"] = DEVICE_ID;
    doc["flood_level_cm"] = currentFloodLevel;
    doc["rain_detected"] = readRainSensor();
    doc["battery_voltage"] = batteryVoltage;
    
    // Serialize JSON
    String jsonPayload;
    serializeJson(doc, jsonPayload);
    
    // Send HTTP POST
    String url = String("http://") + API_HOST + ":" + String(API_PORT) + API_ENDPOINT;
    
    Serial.print("Sending to: ");
    Serial.println(url);
    Serial.print("Payload: ");
    Serial.println(jsonPayload);
    
    HTTPClient http;
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    
    int httpResponseCode = http.POST(jsonPayload);
    
    if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.print("HTTP Response Code: ");
        Serial.println(httpResponseCode);
        Serial.print("Response: ");
        Serial.println(response);
        
        // Check if zone was created
        if (httpResponseCode == 200 || httpResponseCode == 201) {
            StaticJsonDocument<256> responseDoc;
            DeserializationError error = deserializeJson(responseDoc, response);
            
            if (!error && responseDoc.containsKey("zone_created")) {
                bool zoneCreated = responseDoc["zone_created"];
                if (zoneCreated) {
                    Serial.println("🌊 FLOOD ZONE CREATED - Reroute triggered!");
                }
            }
        }
    } else {
        Serial.print("HTTP Error: ");
        Serial.println(httpResponseCode);
        Serial.println(http.errorToString(httpResponseCode));
    }
    
    http.end();
}

// ==================== POWER MANAGEMENT ====================
void enterDeepSleep() {
    Serial.println("Entering deep sleep...");
    
    // Configure wake-up timer (e.g., 1 minute)
    esp_sleep_enable_timer_wakeup(60 * 1000000); // microseconds
    
    // Go to sleep
    esp_deep_sleep_start();
}

// ==================== UTILITY FUNCTIONS ====================
float readBatteryVoltage() {
    // If you have a battery voltage sensor connected to an ADC pin
    // Uncomment and modify this function
    
    // Example for ESP32 internal ADC (not recommended for accurate readings)
    // int adcValue = analogRead(BATTERY_PIN);
    // float voltage = adcValue * (3.3 / 4095.0) * VOLTAGE_DIVIDER_RATIO;
    // return voltage;
    
    return batteryVoltage; // Placeholder
}

void blinkLED(int times, int interval) {
    // Use built-in LED for status indication
    for (int i = 0; i < times; i++) {
        digitalWrite(LED_BUILTIN, HIGH);
        delay(interval);
        digitalWrite(LED_BUILTIN, LOW);
        delay(interval);
    }
}
