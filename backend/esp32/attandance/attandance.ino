
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ---------- RFID ----------
#define SS_PIN 5
#define RST_PIN 22

MFRC522 rfid(SS_PIN, RST_PIN);

// ---------- OLED ----------
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

Adafruit_SSD1306 display(
  SCREEN_WIDTH,
  SCREEN_HEIGHT,
  &Wire,
  OLED_RESET
);

// ---------- OUTPUTS ----------
#define GREEN_LED 25
#define RED_LED 26
#define BUZZER 32

// ---------- WIFI ----------
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Use your computer's IPv4 address
const char* SERVER_URL =
  "http://192.168.1.105:8000/api/attendance";

const char* DEVICE_ID = "ESP32_CLASSROOM_01";

// ---------- DISPLAY ----------
void showMessage(
  String line1,
  String line2 = "",
  String line3 = ""
) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 5);
  display.println(line1);

  display.setCursor(0, 25);
  display.println(line2);

  display.setCursor(0, 45);
  display.println(line3);

  display.display();
}

// ---------- READ UID ----------
String getCardUID() {
  String uid = "";

  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) {
      uid += "0";
    }

    uid += String(rfid.uid.uidByte[i], HEX);
  }

  uid.toUpperCase();
  return uid;
}

// ---------- WIFI CONNECTION ----------
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  showMessage(
    "SMART ATTENDANCE",
    "Connecting WiFi..."
  );

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting WiFi");

  unsigned long startTime = millis();

  while (
    WiFi.status() != WL_CONNECTED &&
    millis() - startTime < 15000
  ) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected");
    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi connection failed");
  }
}

// ---------- INDICATORS ----------
void resetIndicators() {
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(RED_LED, LOW);
  digitalWrite(BUZZER, LOW);
}

void successSignal() {
  digitalWrite(GREEN_LED, HIGH);
  digitalWrite(BUZZER, HIGH);
  delay(150);
  digitalWrite(BUZZER, LOW);
}

void errorSignal() {
  digitalWrite(RED_LED, HIGH);

  for (int i = 0; i < 2; i++) {
    digitalWrite(BUZZER, HIGH);
    delay(120);
    digitalWrite(BUZZER, LOW);
    delay(120);
  }
}

// ---------- SEND ATTENDANCE ----------
void sendAttendance(String uid) {

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (WiFi.status() != WL_CONNECTED) {
    showMessage(
      "NETWORK ERROR",
      "WiFi disconnected",
      "Attendance not saved"
    );

    errorSignal();
    return;
  }

  HTTPClient http;

  http.begin(SERVER_URL);
  http.setTimeout(7000);

  http.addHeader(
    "Content-Type",
    "application/json"
  );

  JsonDocument request;

  request["uid"] = uid;
  request["device_id"] = DEVICE_ID;

  String payload;
  serializeJson(request, payload);

  Serial.println("Sending:");
  Serial.println(payload);

  int httpCode = http.POST(payload);

  Serial.print("HTTP status: ");
  Serial.println(httpCode);

  if (httpCode == 200) {

    String response = http.getString();

    Serial.println("Server response:");
    Serial.println(response);

    JsonDocument result;

    DeserializationError error =
      deserializeJson(result, response);

    if (error) {
      showMessage(
        "SERVER ERROR",
        "Invalid JSON"
      );

      errorSignal();
      http.end();
      return;
    }

    String status =
      result["status"].as<String>();

    String name =
      result["name"] | "";

    String roll =
      result["roll"] | "";

    if (status == "present") {

      showMessage(
        "ATTENDANCE SAVED",
        name,
        roll
      );

      Serial.println("Saved in PostgreSQL");
      successSignal();

    } else if (status == "duplicate") {

      showMessage(
        "ALREADY MARKED",
        name,
        roll
      );

      Serial.println("Duplicate attendance");
      errorSignal();

    } else if (status == "unknown") {

      showMessage(
        "UNKNOWN CARD",
        uid,
        "Not registered"
      );

      errorSignal();

    } else if (status == "no_session") {

      showMessage(
        "NO ACTIVE SESSION",
        "Contact faculty"
      );

      errorSignal();

    } else {

      showMessage(
        "SERVER RESPONSE",
        status
      );

      errorSignal();
    }

  } else {

    Serial.print("Request failed: ");
    Serial.println(http.errorToString(httpCode));

    showMessage(
      "SERVER ERROR",
      "Attendance not",
      "confirmed"
    );

    errorSignal();
  }

  http.end();
}

// ---------- SETUP ----------
void setup() {

  Serial.begin(115200);

  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);

  resetIndicators();

  // Initialize RFID
  SPI.begin(18, 19, 23, SS_PIN);
  rfid.PCD_Init();

  // Initialize OLED
  Wire.begin(21, 22);

  if (!display.begin(
    SSD1306_SWITCHCAPVCC,
    0x3C
  )) {
    Serial.println("OLED initialization failed");

    while (true) {
      delay(100);
    }
  }

  showMessage(
    "RFID ATTENDANCE",
    "Starting system..."
  );

  connectWiFi();

  showMessage(
    "SMART ATTENDANCE",
    "Scan your card"
  );

  Serial.println("RFID system ready");
}

// ---------- LOOP ----------
void loop() {

  if (!rfid.PICC_IsNewCardPresent()) {
    delay(50);
    return;
  }

  if (!rfid.PICC_ReadCardSerial()) {
    return;
  }

  String uid = getCardUID();

  Serial.println("--------------------");
  Serial.print("Card UID: ");
  Serial.println(uid);

  showMessage(
    "CARD DETECTED",
    uid,
    "Sending to server"
  );

  sendAttendance(uid);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  delay(2000);

  resetIndicators();

  showMessage(
    "SMART ATTENDANCE",
    "Scan your card"
  );
}
