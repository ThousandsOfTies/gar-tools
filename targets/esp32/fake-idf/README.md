# GAR Fake ESP-IDF

Minimal link-time stubs for host-side ESP32 application experiments.

This is not an ESP32 simulator and does not implement FreeRTOS scheduling,
Wi-Fi, drivers, queues, or peripheral state. It only provides a small set of
ESP-IDF / FreeRTOS headers and symbols so an application can link while GAR
grows the real simulation backend.

## Build

```bash
FAKE_IDF_BUILD_DIR="$(mktemp -d)"
cmake -S targets/esp32/fake-idf -B "$FAKE_IDF_BUILD_DIR"
cmake --build "$FAKE_IDF_BUILD_DIR"
```

## Link Shape

```bash
cc app.c \
  -Itargets/esp32/fake-idf/include \
  "$FAKE_IDF_BUILD_DIR/libgar_fake_idf.a"
```

## Current Surface

- `freertos/FreeRTOS.h`
- `freertos/task.h`
- `freertos/queue.h`
- `freertos/semphr.h`
- `freertos/event_groups.h`
- `freertos/timers.h`
- `esp_err.h`
- `esp_log.h`
- `esp_event.h`
- `esp_netif.h`
- `esp_wifi.h`
- `nvs_flash.h`
- `driver/gpio.h`
- `driver/uart.h`
- `driver/i2c.h`
- `driver/spi_master.h`
