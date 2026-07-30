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

#ifndef M5STICK_BATTERY_PERCENT
#define M5STICK_BATTERY_PERCENT 95
#endif

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
  uint16_t color565(uint8_t red, uint8_t green, uint8_t blue) const {
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3);
  }

  void setBrightness(uint8_t brightness) { brightness_ = brightness; }
  void fillScreen(uint16_t color) {
    tft_.fillRect(VIEW_X, VIEW_Y, scaleSize(LOGICAL_WIDTH), scaleSize(LOGICAL_HEIGHT), color);
  }
  void setTextColor(uint16_t color, uint16_t background) { tft_.setTextColor(color, background); }
  void setTextSize(uint8_t size) {
    textSize_ = size;
    tft_.setTextSize(size);
  }
  void setCursor(int16_t x, int16_t y) { tft_.setCursor(mapX(x), mapY(y)); }
  void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) {
    tft_.fillRect(mapX(x), mapY(y), scaleSpan(x, w), scaleSpan(y, h), color);
  }
  void drawPixel(int16_t x, int16_t y, uint16_t color) { tft_.fillRect(mapX(x), mapY(y), 1, 1, color); }
  void drawFastHLine(int16_t x, int16_t y, int16_t w, uint16_t color) { fillRect(x, y, w, 1, color); }
  void drawFastVLine(int16_t x, int16_t y, int16_t h, uint16_t color) { fillRect(x, y, 1, h, color); }
  void drawRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) {
    drawFastHLine(x, y, w, color);
    drawFastHLine(x, y + h - 1, w, color);
    drawFastVLine(x, y, h, color);
    drawFastVLine(x + w - 1, y, h, color);
  }
  void drawRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t radius, uint16_t color) {
    tft_.drawRoundRect(mapX(x), mapY(y), scaleSpan(x, w), scaleSpan(y, h), scaleSize(radius), color);
  }
  void fillRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t radius, uint16_t color) {
    tft_.fillRoundRect(mapX(x), mapY(y), scaleSpan(x, w), scaleSpan(y, h), scaleSize(radius), color);
  }
  void fillCircle(int16_t x, int16_t y, int16_t radius, uint16_t color) {
    tft_.fillCircle(mapX(x), mapY(y), scaleSize(radius), color);
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
  static constexpr int16_t LOGICAL_WIDTH = 135;
  static constexpr int16_t LOGICAL_HEIGHT = 240;
  static constexpr int16_t SCALE_NUM = 4;
  static constexpr int16_t SCALE_DEN = 3;
  static constexpr int16_t VIEW_X = 30;
  static constexpr int16_t VIEW_Y = 0;

  int16_t atLeastOne(int16_t value) const { return value > 0 ? value : 1; }
  int16_t scaleValue(int16_t value) const { return (value * SCALE_NUM) / SCALE_DEN; }
  int16_t scaleSize(int16_t value) const { return atLeastOne((value * SCALE_NUM + SCALE_DEN - 1) / SCALE_DEN); }
  int16_t scaleSpan(int16_t start, int16_t length) const {
    return atLeastOne(scaleValue(start + length) - scaleValue(start));
  }
  int16_t mapX(int16_t x) const { return VIEW_X + scaleValue(x); }
  int16_t mapY(int16_t y) const { return VIEW_Y + scaleValue(y); }

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

class PowerShim {
 public:
  int32_t getBatteryLevel() const {
    int32_t percent = M5STICK_BATTERY_PERCENT;
    if (percent < 0) {
      return 0;
    }
    if (percent > 100) {
      return 100;
    }
    return percent;
  }
};

struct Config {};

class M5UnifiedShim {
 public:
  DisplayShim Display;
  PowerShim Power;
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
