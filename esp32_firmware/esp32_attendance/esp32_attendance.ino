#if __has_include("config.h")
#include "config.h"
#elif __has_include("../config.h")
#include "../config.h"
#else
#error "config.h not found"
#endif

#include <Arduino.h>
#include <HTTPClient.h>
#include <MFRC522.h>
#include <SPI.h>
#include <WiFi.h>
#include <esp_camera.h>

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);

String serverUrl = SERVER_URL;
String currentSessionId;
String currentTeacherName;

bool sessionActive = false;
bool cameraReady = false;
bool autoStartAttempted = false;
bool backendHealthy = false;

unsigned long sessionEndMs = 0;
unsigned long lastFrameSentMs = 0;
unsigned long lastWifiRetryMs = 0;
unsigned long lastHealthCheckMs = 0;

bool connectWifi(bool blocking = true);
void ensureWifiConnected();
void initRfid();
bool initCamera();
void checkRfidForSessionStart();
bool startSession(const String &teacherRfid);
bool sendFrameForCurrentSession();
bool sendDummyFrame();
bool sendCameraFrame();
bool postMultipartFrame(const uint8_t *imageData, size_t imageLen);
bool checkBackendHealth(bool verbose = true);
void stopSession();
void setStatusLed(bool on);
void blinkStatusLed(uint8_t times, uint16_t onMs = 120, uint16_t offMs = 120);
String readRfidUid();
String extractJsonString(const String &json, const char *key);

void setup()
{
  Serial.begin(115200);
  delay(1200);

  if (STATUS_LED_PIN >= 0)
  {
    pinMode(STATUS_LED_PIN, OUTPUT);
    setStatusLed(false);
  }

  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  Serial.println();
  Serial.println("[BOOT] ESP32 attendance firmware starting");
  Serial.printf("[CFG] Server URL: %s\n", serverUrl.c_str());
  Serial.printf("[CFG] Dummy frame mode: %s\n", USE_DUMMY_FRAME_DATA ? "ON" : "OFF");

  connectWifi(true);
  checkBackendHealth(true);
  initRfid();
  cameraReady = initCamera();

  if (!cameraReady)
  {
    Serial.println("[CAM] Camera not ready; RFID and dummy mode can still run");
  }

  if (AUTO_START_SESSION_WITH_TEST_RFID)
  {
    Serial.printf("[CFG] Auto-start with test RFID enabled (%s)\n", TEST_RFID_UID);
  }

  Serial.println("[READY] Scan RFID card to start session");
  blinkStatusLed(3);
}

void loop()
{
  ensureWifiConnected();

  if (WiFi.status() == WL_CONNECTED && (millis() - lastHealthCheckMs >= BACKEND_HEALTH_CHECK_INTERVAL_MS))
  {
    checkBackendHealth(true);
  }

  if (!sessionActive)
  {
    if (AUTO_START_SESSION_WITH_TEST_RFID && !autoStartAttempted)
    {
      autoStartAttempted = true;
      Serial.printf("[RFID] Auto-start attempt with test UID: %s\n", TEST_RFID_UID);
      if (startSession(String(TEST_RFID_UID)))
      {
        Serial.println("[SESSION] Auto-start succeeded");
      }
      else
      {
        Serial.println("[SESSION] Auto-start failed");
      }
    }

    checkRfidForSessionStart();
    delay(80);
    return;
  }

  if (millis() >= sessionEndMs)
  {
    Serial.println("[SESSION] Duration reached, stopping session");
    stopSession();
    delay(80);
    return;
  }

  if (millis() - lastFrameSentMs >= PHOTO_CAPTURE_INTERVAL)
  {
    lastFrameSentMs = millis();
    if (!sendFrameForCurrentSession())
    {
      Serial.println("[FRAME] Upload failed");
    }
  }

  delay(50);
}

bool connectWifi(bool blocking)
{
  if (WiFi.status() == WL_CONNECTED)
  {
    return true;
  }

  Serial.printf("[WIFI] Connecting to %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  if (!blocking)
  {
    return false;
  }

  const unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - started) < WIFI_CONNECT_TIMEOUT_MS)
  {
    delay(400);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.printf("[WIFI] Connected. IP: %s\n", WiFi.localIP().toString().c_str());
    setStatusLed(true);
    checkBackendHealth(true);
    return true;
  }

  Serial.println("[WIFI] Connection timeout");
  setStatusLed(false);
  return false;
}

void ensureWifiConnected()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    return;
  }

  setStatusLed(false);

  const unsigned long now = millis();
  if (now - lastWifiRetryMs < 5000)
  {
    return;
  }

  lastWifiRetryMs = now;
  connectWifi(true);
}

void initRfid()
{
  SPI.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, RFID_SS_PIN);
  rfid.PCD_Init();
  Serial.println("[RFID] Reader initialized");
}

bool initCamera()
{
  camera_config_t cfg;
  cfg.ledc_channel = LEDC_CHANNEL_0;
  cfg.ledc_timer = LEDC_TIMER_0;
  cfg.pin_d0 = 5;
  cfg.pin_d1 = 18;
  cfg.pin_d2 = 19;
  cfg.pin_d3 = 21;
  cfg.pin_d4 = 36;
  cfg.pin_d5 = 39;
  cfg.pin_d6 = 34;
  cfg.pin_d7 = 35;
  cfg.pin_xclk = 0;
  cfg.pin_pclk = 22;
  cfg.pin_vsync = 25;
  cfg.pin_href = 23;
  cfg.pin_sccb_sda = 26;
  cfg.pin_sccb_scl = 27;
  cfg.pin_pwdn = 32;
  cfg.pin_reset = -1;
  cfg.xclk_freq_hz = 20000000;
  cfg.pixel_format = PIXFORMAT_JPEG;
  cfg.frame_size = CAMERA_FRAME_SIZE;
  cfg.jpeg_quality = CAMERA_JPEG_QUALITY;
  cfg.fb_count = CAMERA_FB_COUNT;
  cfg.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  cfg.grab_mode = CAMERA_GRAB_LATEST;

  const esp_err_t err = esp_camera_init(&cfg);
  if (err != ESP_OK)
  {
    Serial.printf("[CAM] Init failed with error 0x%x\n", err);
    return false;
  }

  sensor_t *s = esp_camera_sensor_get();
  if (s != nullptr)
  {
    s->set_brightness(s, 0);
    s->set_contrast(s, 0);
    s->set_saturation(s, 0);
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_gain_ctrl(s, 1);
  }

  Serial.println("[CAM] Camera initialized");
  return true;
}

void checkRfidForSessionStart()
{
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial())
  {
    return;
  }

  const String uid = readRfidUid();
  Serial.printf("[RFID] Card detected: %s\n", uid.c_str());

  if (startSession(uid))
  {
    Serial.println("[SESSION] Started from RFID");
    blinkStatusLed(4);
  }
  else
  {
    Serial.println("[SESSION] Failed to start from RFID");
    blinkStatusLed(10, 60, 60);
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

bool startSession(const String &teacherRfid)
{
  if (WiFi.status() != WL_CONNECTED)
  {
    Serial.println("[SESSION] Cannot start session, WiFi disconnected");
    return false;
  }

  if (!backendHealthy && !checkBackendHealth(true))
  {
    Serial.println("[SESSION] Backend not healthy, postponing session start");
    return false;
  }

  HTTPClient http;
  const String url = serverUrl + API_RFID_START_SESSION_PATH;
  const String payload = String("{\"") + RFID_UID_FIELD_NAME + "\":\"" + teacherRfid
                         + "\",\"duration_minutes\":" + String(DEFAULT_SESSION_DURATION)
                         + "}";

  http.setTimeout(15000);
  if (!http.begin(url))
  {
    Serial.printf("[HTTP] begin() failed: %s\n", url.c_str());
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-ID", DEVICE_ID);

  const int code = http.POST(payload);
  const String response = http.getString();
  http.end();

  Serial.printf("[HTTP] %s -> %d\n", url.c_str(), code);
  if (response.length() > 0)
  {
    Serial.printf("[HTTP] Response: %s\n", response.c_str());
  }

  if (code != 200)
  {
    return false;
  }

  const bool success = response.indexOf("\"success\":true") >= 0 || response.indexOf("\"success\": true") >= 0;
  if (!success)
  {
    return false;
  }

  currentSessionId = extractJsonString(response, "session_id");
  currentTeacherName = extractJsonString(response, "teacher_name");

  if (currentSessionId.isEmpty())
  {
    Serial.println("[SESSION] Missing session_id in response");
    return false;
  }

  sessionActive = true;
  sessionEndMs = millis() + (DEFAULT_SESSION_DURATION * 60UL * 1000UL);
  lastFrameSentMs = 0;

  Serial.printf("[SESSION] ID: %s\n", currentSessionId.c_str());
  if (!currentTeacherName.isEmpty())
  {
    Serial.printf("[SESSION] Teacher: %s\n", currentTeacherName.c_str());
  }
  return true;
}

bool sendFrameForCurrentSession()
{
  if (!sessionActive || currentSessionId.isEmpty())
  {
    return false;
  }

  if (WiFi.status() != WL_CONNECTED)
  {
    Serial.println("[FRAME] Skipping upload, WiFi disconnected");
    return false;
  }

  if (!backendHealthy && !checkBackendHealth(false))
  {
    Serial.println("[FRAME] Skipping upload, backend health check failed");
    return false;
  }

  if (USE_DUMMY_FRAME_DATA)
  {
    return sendDummyFrame();
  }

  return sendCameraFrame();
}

bool sendDummyFrame()
{
  HTTPClient http;
  const String url = serverUrl + API_ESP32_FRAME_PATH;
  const String payload = String("{\"session_id\":\"") + currentSessionId
                         + "\",\"frame_base64\":\"" + DUMMY_FRAME_BASE64 + "\"}";

  http.setTimeout(20000);
  if (!http.begin(url))
  {
    Serial.printf("[HTTP] begin() failed: %s\n", url.c_str());
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-ID", DEVICE_ID);
  http.addHeader("X-Session-ID", currentSessionId);

  const int code = http.POST(payload);
  const String response = http.getString();
  http.end();

  Serial.printf("[DUMMY] %s -> %d\n", url.c_str(), code);
  if (response.length() > 0)
  {
    Serial.printf("[DUMMY] Response: %s\n", response.c_str());
  }

  return code == 200;
}

bool sendCameraFrame()
{
  if (!cameraReady)
  {
    Serial.println("[CAM] Not initialized, cannot send frame");
    return false;
  }

  digitalWrite(FLASH_LED_PIN, HIGH);
  delay(60);
  camera_fb_t *fb = esp_camera_fb_get();
  digitalWrite(FLASH_LED_PIN, LOW);

  if (fb == nullptr)
  {
    Serial.println("[CAM] Capture failed");
    return false;
  }

  Serial.printf("[CAM] Captured frame, %u bytes\n", static_cast<unsigned>(fb->len));
  const bool ok = postMultipartFrame(fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return ok;
}

bool postMultipartFrame(const uint8_t *imageData, size_t imageLen)
{
  HTTPClient http;
  const String url = serverUrl + API_ESP32_FRAME_PATH;
  const String boundary = "----ESP32Boundary7MA4YWxkTrZu0gW";

  if (!http.begin(url))
  {
    Serial.printf("[HTTP] begin() failed: %s\n", url.c_str());
    return false;
  }

  http.setTimeout(25000);
  http.addHeader("Content-Type", String("multipart/form-data; boundary=") + boundary);
  http.addHeader("X-Device-ID", DEVICE_ID);
  http.addHeader("X-Session-ID", currentSessionId);

  String head = "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"session_id\"\r\n\r\n";
  head += currentSessionId + "\r\n";
  head += "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"" + String(ESP32_FRAME_FIELD_NAME) + "\"; filename=\"frame.jpg\"\r\n";
  head += "Content-Type: image/jpeg\r\n\r\n";

  const String tail = "\r\n--" + boundary + "--\r\n";

  const size_t totalLen = head.length() + imageLen + tail.length();
  uint8_t *body = static_cast<uint8_t *>(malloc(totalLen));
  if (body == nullptr)
  {
    Serial.printf("[FRAME] Out of memory for multipart body (%u bytes)\n", static_cast<unsigned>(totalLen));
    http.end();
    return false;
  }

  memcpy(body, head.c_str(), head.length());
  memcpy(body + head.length(), imageData, imageLen);
  memcpy(body + head.length() + imageLen, tail.c_str(), tail.length());

  const int code = http.POST(body, totalLen);
  const String response = http.getString();

  free(body);
  http.end();

  Serial.printf("[FRAME] %s -> %d\n", url.c_str(), code);
  if (response.length() > 0)
  {
    Serial.printf("[FRAME] Response: %s\n", response.c_str());
  }

  return code == 200;
}

bool checkBackendHealth(bool verbose)
{
  if (WiFi.status() != WL_CONNECTED)
  {
    backendHealthy = false;
    return false;
  }

  HTTPClient http;
  const String url = serverUrl + API_HEALTH_PATH;
  http.setTimeout(8000);

  lastHealthCheckMs = millis();

  if (!http.begin(url))
  {
    backendHealthy = false;
    if (verbose)
    {
      Serial.printf("[HEALTH] begin() failed: %s\n", url.c_str());
    }
    return false;
  }

  const int code = http.GET();
  const String response = http.getString();
  http.end();

  const bool ok = (code == 200);
  backendHealthy = ok;

  if (verbose)
  {
    Serial.printf("[HEALTH] %s -> %d\n", url.c_str(), code);
    if (response.length() > 0)
    {
      Serial.printf("[HEALTH] Response: %s\n", response.c_str());
    }
  }

  return ok;
}

void stopSession()
{
  if (!sessionActive || currentSessionId.isEmpty())
  {
    sessionActive = false;
    currentSessionId = "";
    currentTeacherName = "";
    return;
  }

  HTTPClient http;
  const String url = serverUrl + API_SESSION_STOP_PATH;
  const String payload = String("{\"session_id\":\"") + currentSessionId + "\"}";

  http.setTimeout(15000);
  if (http.begin(url))
  {
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-ID", DEVICE_ID);
    const int code = http.POST(payload);
    const String response = http.getString();
    Serial.printf("[SESSION] stop -> %d\n", code);
    if (response.length() > 0)
    {
      Serial.printf("[SESSION] stop response: %s\n", response.c_str());
    }
    http.end();
  }
  else
  {
    Serial.printf("[SESSION] Failed to call stop endpoint: %s\n", url.c_str());
  }

  sessionActive = false;
  currentSessionId = "";
  currentTeacherName = "";
  Serial.println("[SESSION] Cleared local session state");
}

void setStatusLed(bool on)
{
  if (STATUS_LED_PIN >= 0)
  {
    digitalWrite(STATUS_LED_PIN, on ? HIGH : LOW);
  }
}

void blinkStatusLed(uint8_t times, uint16_t onMs, uint16_t offMs)
{
  if (STATUS_LED_PIN < 0)
  {
    return;
  }

  for (uint8_t i = 0; i < times; i++)
  {
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(onMs);
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(offMs);
  }
}

String readRfidUid()
{
  String uid;
  uid.reserve(rfid.uid.size * 2);
  for (byte i = 0; i < rfid.uid.size; i++)
  {
    if (rfid.uid.uidByte[i] < 0x10)
    {
      uid += '0';
    }
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

String extractJsonString(const String &json, const char *key)
{
  const String keyToken = String("\"") + key + "\"";
  const int keyPos = json.indexOf(keyToken);
  if (keyPos < 0)
  {
    return "";
  }

  const int colonPos = json.indexOf(':', keyPos + keyToken.length());
  if (colonPos < 0)
  {
    return "";
  }

  int startQuote = json.indexOf('"', colonPos + 1);
  if (startQuote < 0)
  {
    return "";
  }

  int endQuote = startQuote + 1;
  while (true)
  {
    endQuote = json.indexOf('"', endQuote);
    if (endQuote < 0)
    {
      return "";
    }
    if (json[endQuote - 1] != '\\')
    {
      break;
    }
    endQuote++;
  }

  return json.substring(startQuote + 1, endQuote);
}
