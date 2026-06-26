# ESP32 Wokwi Backend

GAR-owned Wokwi simulation assets for ESP32/M5Stack-class targets.

The orchestration provider lives in `GaplessAgentRuntime`. This directory keeps
the target-specific project templates, wiring, local shims, and scenarios that
make Wokwi usable as a simulation backend.

## M5StackC Template

`m5stackc/` is copied into `GaplessAgentRuntime/.gar/wokwi/m5stackc` by
`gar setup` / `gar sim env start`.

It contains:

- `diagram.json` — Wokwi wiring for ESP32 DevKit, SPI LCD, BtnA/BtnB, LED.
- `platformio.ini` — PlatformIO env for the Wokwi firmware build.
- `src/main.cpp` — Vibe Remote minimal firmware adapted for Wokwi.
- `lib/M5Unified/src/M5Unified.h` — small Wokwi-side M5Unified display shim.
- `button.test.yaml` — Wokwi scenario for button press smoke tests.
- `wokwi.toml.template` — rendered by GAR so firmware/ELF paths can be
  overridden with environment variables.

Generated artifacts such as `.pio/`, screenshots, and serial logs stay in the
runtime project under `.gar/` and are not committed here.
