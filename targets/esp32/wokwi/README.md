# ESP32 Wokwi Backend

Reusable Wokwi simulation templates for ESP32/M5Stack-class targets.

The orchestration provider lives in `GaplessAgentRuntime`. This directory keeps
target-specific wiring, build templates, and local simulator shims. It owns
neither application source nor built firmware.

## Ownership Model

```text
gar-tools/
  targets/esp32/wokwi/m5stackc/      # template source of truth

product workspace/
  <application>/src/                 # app source of truth
  scripts/product-sim-build.sh       # generate, build, and package

selected runtime workspace/
  .gar/wokwi/<project>/               # deployed runnable project
```

The product build hook combines this template with the product's application
source, builds the firmware, and writes a `deploy.app` artifact. `gar sim app
deploy` materializes that artifact into the selected runtime workspace. The
deployed project can then be opened by the VS Code Wokwi extension or run with
`gar sim runtime start`.

`gar setup` only selects and installs the backend. `gar sim runtime start` only
launches an already deployed project; neither command invokes the workspace
generator.

## M5StackC Template

`m5stackc/` is consumed by a product build hook such as
`scripts/product-sim-build.sh`.

It contains:

- `diagram.json` — Wokwi wiring for ESP32 DevKit, SPI LCD, BtnA/BtnB/BtnP, LED.
- `platformio.ini.template` — rendered by the generator with `src_dir` pointing at the app repository.
- `wokwi.toml.template` — rendered by the generator so firmware/ELF paths can be overridden.
- `lib/M5Unified/src/M5Unified.h` — Wokwi-side M5Unified compatibility shim.
- `scripts/env_flags.py` — local `.env.local` to PlatformIO build flags bridge.

Generated files such as `platformio.ini`, `wokwi.toml`, `.pio/`, screenshots,
and serial logs are not committed here. This template currently ships no Wokwi
CLI scenario; a product that needs automated interaction owns and packages its
scenario explicitly.
