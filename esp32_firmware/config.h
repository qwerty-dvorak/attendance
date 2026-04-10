#ifndef CONFIG_H
#define CONFIG_H

#define WIFI_SSID "YourWiFiSSID"
#define WIFI_PASSWORD "YourWiFiPassword"

#define SERVER_URL "http://192.168.1.100:5000"
#define DEVICE_ID "esp32_001"

#define RFID_SS_PIN 4
#define RFID_RST_PIN 0

#define DEFAULT_SESSION_DURATION 15 // minutes
#define PHOTO_CAPTURE_INTERVAL 5000 // milliseconds
#define MAX_RETRY_ATTEMPTS 3
#define RETRY_DELAY_MS 1000

#define FLASH_LED_PIN 4
#define STATUS_LED_PIN 33

#define CAMERA_MODEL_ESP32CAM

#endif
