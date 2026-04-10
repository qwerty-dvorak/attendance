#include "config.h"
#include <Arduino.h>
#include <HTTPClient.h>
#include <MFRC522.h>
#include <SPI.h>
#include <WiFi.h>
#include <esp_camera.h>
#include <string.h>

// RFID
#define RST_PIN RFID_RST_PIN
#define SS_PIN RFID_SS_PIN
MFRC522 rfid (SS_PIN, RST_PIN);

// Session state
bool sessionActive = false;
String currentSessionId = "";
unsigned long sessionStartTime = 0;
unsigned long sessionEndTime = 0;
unsigned long lastCaptureTime = 0;

String teacherName = "";

// WiFi credentials
const char *ssid = WIFI_SSID;
const char *password = WIFI_PASSWORD;
const char *serverUrl = SERVER_URL;
const char *deviceId = DEVICE_ID;

unsigned long captureInterval = PHOTO_CAPTURE_INTERVAL;
unsigned long sessionDuration
    = DEFAULT_SESSION_DURATION * 60 * 1000; // Convert to ms

void
setup ()
{
    Serial.begin (115200);
    delay (1000);

    pinMode (STATUS_LED_PIN, OUTPUT);
    pinMode (FLASH_LED_PIN, OUTPUT);
    digitalWrite (STATUS_LED_PIN, LOW);
    digitalWrite (FLASH_LED_PIN, LOW);

    Serial.println ("Starting Smart Attendance System...");

    SPI.begin ();
    rfid.PCD_Init ();
    Serial.println ("RFID initialized");

    connectWiFi ();

    if (!initCamera ())
        {
            Serial.println ("Camera init failed!");
        }
    else
        {
            Serial.println ("Camera initialized");
        }

    Serial.println ("System ready. Scan teacher RFID to start session.");
    blinkLED (3);
}

void
loop ()
{
    if (!sessionActive)
        {
            checkRFID ();
        }
    else
        {
            checkSessionTimeout ();
            captureAndSendImages ();
        }

    delay (100);
}

void
connectWiFi ()
{
    Serial.print ("Connecting to WiFi");
    WiFi.begin (ssid, password);

    int attempts = 0;
    while (WiFi.status () != WL_CONNECTED && attempts < 20)
        {
            delay (500);
            Serial.print (".");
            attempts++;
        }

    if (WiFi.status () == WL_CONNECTED)
        {
            Serial.println ("\nWiFi connected");
            Serial.print ("IP: ");
            Serial.println (WiFi.localIP ());
            digitalWrite (STATUS_LED_PIN, HIGH);
        }
    else
        {
            Serial.println ("\nWiFi connection failed!");
        }
}

void
checkRFID ()
{
    if (!rfid.PICC_IsNewCardPresent ())
        {
            return;
        }

    if (!rfid.PICC_ReadCardSerial ())
        {
            return;
        }

    String rfidUID = "";
    for (byte i = 0; i < rfid.uid.size; i++)
        {
            if (rfid.uid.uidByte[i] < 0x10)
                {
                    rfidUID += "0";
                }
            rfidUID += String (rfid.uid.uidByte[i], HEX);
        }
    rfidUID.toUpperCase ();

    Serial.print ("RFID UID: ");
    Serial.println (rfidUID);

    if (startSession (rfidUID))
        {
            Serial.println ("Session started successfully!");
            blinkLED (5);
        }
    else
        {
            Serial.println ("Failed to start session. Invalid teacher RFID.");
            blinkLED (10);
        }

    rfid.PICC_HaltA ();
    rfid.PCD_StopCrypto1 ();
}

bool
startSession (String teacherRFID)
{
    HTTPClient http;
    String url = String (serverUrl) + "/api/session/start";

    http.begin (url);
    http.addHeader ("Content-Type", "application/json");
    http.addHeader ("X-Device-ID", deviceId);

    String payload = "{\"teacher_rfid\": \"" + teacherRFID
                     + "\", \"duration_minutes\": "
                     + String (DEFAULT_SESSION_DURATION) + "}";

    int httpCode = http.POST (payload);

    if (httpCode == 200)
        {
            String response = http.getString ();
            Serial.println ("Server response: " + response);

            if (response.indexOf ("\"success\":true") != -1
                || response.indexOf ("\"success\": true") != -1)
                {
                    int sessionIdStart
                        = response.indexOf ("\"session_id\": \"") + 15;
                    int sessionIdEnd = response.indexOf ("\"", sessionIdStart);
                    currentSessionId
                        = response.substring (sessionIdStart, sessionIdEnd);

                    int nameStart
                        = response.indexOf ("\"teacher_name\": \"") + 16;
                    int nameEnd = response.indexOf ("\"", nameStart);
                    teacherName = response.substring (nameStart, nameEnd);

                    sessionActive = true;
                    sessionStartTime = millis ();
                    sessionEndTime = sessionStartTime + sessionDuration;
                    lastCaptureTime = 0;

                    Serial.println ("Session ID: " + currentSessionId);
                    Serial.println ("Teacher: " + teacherName);
                    Serial.println ("Session ends in "
                                    + String (DEFAULT_SESSION_DURATION)
                                    + " minutes");

                    http.end ();
                    return true;
                }
        }

    Serial.println ("HTTP Error: " + String (httpCode));
    http.end ();
    return false;
}

void
checkSessionTimeout ()
{
    unsigned long currentTime = millis ();

    if (currentTime >= sessionEndTime)
        {
            endSession ();
        }

    unsigned long remaining = (sessionEndTime > currentTime)
                                  ? (sessionEndTime - currentTime) / 1000
                                  : 0;

    if (remaining % 60 == 0 && remaining > 0)
        {
            Serial.print ("Time remaining: ");
            Serial.print (remaining / 60);
            Serial.println (" minutes");
        }
}

void
endSession ()
{
    if (!sessionActive)
        return;

    Serial.println ("Ending session...");

    HTTPClient http;
    String url = String (serverUrl) + "/api/session/stop";

    http.begin (url);
    http.addHeader ("Content-Type", "application/json");
    http.addHeader ("X-Device-ID", deviceId);

    String payload = "{\"session_id\": \"" + currentSessionId + "\"}";
    int httpCode = http.POST (payload);

    if (httpCode == 200)
        {
            String response = http.getString ();
            Serial.println ("Session ended. Server response: " + response);
        }
    else
        {
            Serial.println ("Failed to end session. HTTP: "
                            + String (httpCode));
        }

    http.end ();

    sessionActive = false;
    currentSessionId = "";
    teacherName = "";

    Serial.println ("Session complete. Ready for next session.");
    blinkLED (3);
}

void
captureAndSendImages ()
{
    unsigned long currentTime = millis ();

    if (currentTime - lastCaptureTime < captureInterval)
        {
            return;
        }

    lastCaptureTime = currentTime;

    digitalWrite (FLASH_LED_PIN, HIGH);
    delay (100);

    camera_fb_t *fb = esp_camera_fb_get ();

    digitalWrite (FLASH_LED_PIN, LOW);

    if (!fb)
        {
            Serial.println ("Camera capture failed!");
            return;
        }

    Serial.print ("Captured image: ");
    Serial.print (fb->len);
    Serial.println (" bytes");

    bool sendSuccess = sendImageToServer (fb->buf, fb->len);

    if (sendSuccess)
        {
            Serial.println ("Image sent successfully");
        }
    else
        {
            Serial.println ("Failed to send image");
        }

    esp_camera_fb_return (fb);
}

bool
sendImageToServer (uint8_t *imageData, size_t imageLen)
{
    HTTPClient http;
    String url = String (serverUrl) + "/api/attendance/upload";

    http.begin (url);
    String boundary = "----ESP32Boundary7MA4YWxkTrZu0gW";
    http.addHeader (
        "Content-Type",
        String ("multipart/form-data; boundary=") + boundary);
    http.addHeader ("X-Device-ID", deviceId);
    http.addHeader ("X-Session-ID", currentSessionId);
    http.addHeader ("X-Timestamp", String (millis ()));

    String head = "--" + boundary + "\r\n";
    head += "Content-Disposition: form-data; name=\"session_id\"\r\n\r\n";
    head += currentSessionId + "\r\n";
    head += "--" + boundary + "\r\n";
    head += "Content-Disposition: form-data; name=\"image\"; "
            "filename=\"capture.jpg\"\r\n";
    head += "Content-Type: image/jpeg\r\n\r\n";

    String tail = "\r\n--" + boundary + "--\r\n";

    int totalLen = head.length () + imageLen + tail.length ();
    uint8_t *body = (uint8_t *)malloc (totalLen);
    if (body == nullptr)
        {
            Serial.println ("Failed to allocate multipart body buffer");
            http.end ();
            return false;
        }

    memcpy (body, head.c_str (), head.length ());
    memcpy (body + head.length (), imageData, imageLen);
    memcpy (body + head.length () + imageLen, tail.c_str (), tail.length ());

    int httpCode = http.POST (body, totalLen);

    free (body);
    http.end ();

    return (httpCode == 200);
}

bool
initCamera ()
{
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = 5;
    config.pin_d1 = 18;
    config.pin_d2 = 19;
    config.pin_d3 = 21;
    config.pin_d4 = 36;
    config.pin_d5 = 39;
    config.pin_d6 = 34;
    config.pin_d7 = 35;
    config.pin_xclk = 0;
    config.pin_pclk = 22;
    config.pin_vsync = 25;
    config.pin_href = 23;
    config.pin_sscb_sda = 26;
    config.pin_sscb_scl = 27;
    config.pin_reset = 32;
    config.xclk_freq_hz = 20000000;
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = 2;

    esp_err_t err = esp_camera_init (&config);
    if (err != ESP_OK)
        {
            Serial.printf ("Camera init failed with error 0x%x", err);
            return false;
        }

    sensor_t *s = esp_camera_sensor_get ();
    if (s != NULL)
        {
            s->set_brightness (s, 0);
            s->set_contrast (s, 0);
            s->set_saturation (s, 0);
            s->set_whitebal (s, 1);
            s->set_awb_gain (s, 1);
            s->set_wb_mode (s, 0);
            s->set_exposure_ctrl (s, 1);
            s->set_aec2 (s, 0);
            s->set_ae_level (s, 0);
            s->set_aec_value (s, 300);
            s->set_gain_ctrl (s, 1);
            s->set_agc_gain (s, 0);
            s->set_gainceiling (s, (gainceiling_t)0);
            s->set_bpc (s, 0);
            s->set_wpc (s, 1);
            s->set_raw_gma (s, 1);
            s->set_lenc (s, 1);
            s->set_hmirror (s, 0);
            s->set_vflip (s, 0);
            s->set_dcw (s, 1);
            s->set_colorbar (s, 0);
        }

    return true;
}

void
blinkLED (int times)
{
    for (int i = 0; i < times; i++)
        {
            digitalWrite (STATUS_LED_PIN, HIGH);
            delay (200);
            digitalWrite (STATUS_LED_PIN, LOW);
            delay (200);
        }
}
