#pragma once

#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <SPI.h>

#define TFT_BLACK ILI9341_BLACK
#define TFT_GREEN ILI9341_GREEN
#define TFT_YELLOW ILI9341_YELLOW
#define TFT_ORANGE ILI9341_ORANGE
#define TFT_CYAN ILI9341_CYAN
#define TFT_RED ILI9341_RED
#define TFT_WHITE ILI9341_WHITE
#define TFT_NAVY ILI9341_NAVY
#define TFT_DARKGREY 0x7BEF
#define TFT_LIGHTGREY 0xC618

namespace gar_wokwi_m5 {

constexpr int TFT_SCK_PIN = 13;
constexpr int TFT_MOSI_PIN = 15;
constexpr int TFT_CS_PIN = 5;
constexpr int TFT_DC_PIN = 23;
constexpr int TFT_RST_PIN = 18;
constexpr int BUTTON_A_PIN = 32;
constexpr int BUTTON_B_PIN = 33;

class DisplayShim {
 public:
  DisplayShim() : tft_(TFT_CS_PIN, TFT_DC_PIN, TFT_RST_PIN) {}

  void begin() {
    SPI.begin(TFT_SCK_PIN, -1, TFT_MOSI_PIN, TFT_CS_PIN);
    tft_.begin();
  }

  void setRotation(uint8_t rotation) {
    rotation_ = rotation;
    tft_.setRotation(rotation);
  }

  int16_t width() const { return LOGICAL_WIDTH; }
  int16_t height() const { return LOGICAL_HEIGHT; }

  void setBrightness(uint8_t brightness) { brightness_ = brightness; }
  void fillScreen(uint16_t color) { tft_.fillRect(VIEW_X, VIEW_Y, LOGICAL_WIDTH * SCALE, LOGICAL_HEIGHT * SCALE, color); }
  void setTextColor(uint16_t color, uint16_t background) { tft_.setTextColor(color, background); }
  void setTextSize(uint8_t size) {
    textSize_ = size;
    tft_.setTextSize(size * SCALE);
  }
  void setCursor(int16_t x, int16_t y) { tft_.setCursor(mapX(x), mapY(y)); }
  void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) {
    tft_.fillRect(mapX(x), mapY(y), w * SCALE, h * SCALE, color);
  }
  void drawPixel(int16_t x, int16_t y, uint16_t color) { tft_.fillRect(mapX(x), mapY(y), SCALE, SCALE, color); }
  void drawFastHLine(int16_t x, int16_t y, int16_t w, uint16_t color) { fillRect(x, y, w, 1, color); }
  void drawFastVLine(int16_t x, int16_t y, int16_t h, uint16_t color) { fillRect(x, y, 1, h, color); }
  void drawRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) {
    drawFastHLine(x, y, w, color);
    drawFastHLine(x, y + h - 1, w, color);
    drawFastVLine(x, y, h, color);
    drawFastVLine(x + w - 1, y, h, color);
  }
  void drawRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t radius, uint16_t color) {
    tft_.drawRoundRect(mapX(x), mapY(y), w * SCALE, h * SCALE, radius * SCALE, color);
  }
  void fillRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t radius, uint16_t color) {
    tft_.fillRoundRect(mapX(x), mapY(y), w * SCALE, h * SCALE, radius * SCALE, color);
  }
  void fillCircle(int16_t x, int16_t y, int16_t radius, uint16_t color) {
    tft_.fillCircle(mapX(x), mapY(y), radius * SCALE, color);
  }
  void drawString(const String &text, int16_t x, int16_t y) {
    tft_.setCursor(mapX(x), mapY(y));
    tft_.print(text);
  }
  void drawString(const char *text, int16_t x, int16_t y) {
    tft_.setCursor(mapX(x), mapY(y));
    tft_.print(text);
  }

  template <typename T>
  size_t print(const T &value) {
    return tft_.print(value);
  }

  template <typename T>
  size_t println(const T &value) {
    return tft_.println(value);
  }

 private:
  static constexpr int16_t LOGICAL_WIDTH = 160;
  static constexpr int16_t LOGICAL_HEIGHT = 80;
  static constexpr int16_t SCALE = 2;
  static constexpr int16_t VIEW_X = 0;
  static constexpr int16_t VIEW_Y = 40;

  int16_t mapX(int16_t x) const { return VIEW_X + x * SCALE; }
  int16_t mapY(int16_t y) const { return VIEW_Y + y * SCALE; }

  Adafruit_ILI9341 tft_;
  uint8_t rotation_ = 1;
  uint8_t textSize_ = 1;
  uint8_t brightness_ = 255;
};

class ButtonShim {
 public:
  explicit ButtonShim(int pin) : pin_(pin) {}

  void begin() {
    pinMode(pin_, INPUT_PULLUP);
    current_ = digitalRead(pin_);
  }

  void update() {
    bool previous = current_;
    current_ = digitalRead(pin_);
    pressed_ = previous == HIGH && current_ == LOW;
  }

  bool wasPressed() {
    bool result = pressed_;
    pressed_ = false;
    return result;
  }

 private:
  int pin_;
  bool current_ = HIGH;
  bool pressed_ = false;
};

struct Config {};

class M5UnifiedShim {
 public:
  DisplayShim Display;
  ButtonShim BtnA{BUTTON_A_PIN};
  ButtonShim BtnB{BUTTON_B_PIN};

  Config config() { return Config{}; }

  void begin(const Config &) {
    Display.begin();
    BtnA.begin();
    BtnB.begin();
  }

  void update() {
    BtnA.update();
    BtnB.update();
  }
};

}  // namespace gar_wokwi_m5

static gar_wokwi_m5::M5UnifiedShim M5;
