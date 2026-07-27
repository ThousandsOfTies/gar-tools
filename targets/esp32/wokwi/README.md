# ESP32 Wokwi Backend

GAR-owned Wokwi simulation templates for ESP32/M5Stack-class targets.

The orchestration provider lives in `GaplessAgentRuntime`. This directory keeps
target-specific wiring, build templates, local simulator shims, and smoke
scenarios. It does not own application source code.

## Ownership Model

```text
gar-tools/
  targets/esp32/wokwi/m5stackc/      # template source of truth

gar-vibe-ui/
  vibe-remote/m5stickc-client/src/   # app source of truth

GaplessAgentRuntime/
  .gar/wokwi/m5stackc/               # generated Wokwi workspace
```

GAR renders the template and the app source path into the generated Wokwi
workspace. The workspace can then be opened by the VS Code Wokwi extension or
run with `wokwi-cli`.

## M5StackC Template

`m5stackc/` is copied into `GaplessAgentRuntime/.gar/wokwi/m5stackc` by
`gar setup` / `gar sim runtime start`.

It contains:

- `diagram.json` — Wokwi wiring for ESP32 DevKit, SPI LCD, BtnA/BtnB/BtnP, LED.
- `platformio.ini.template` — rendered by GAR with `src_dir` pointing at the app repository.
- `wokwi.toml.template` — rendered by GAR so firmware/ELF paths can be overridden.
- `lib/M5Unified/src/M5Unified.h` — Wokwi-side M5Unified compatibility shim.
- `scripts/env_flags.py` — local `.env.local` to PlatformIO build flags bridge.
- `button.test.yaml` — Wokwi scenario for button press smoke tests.

Generated artifacts such as `platformio.ini`, `wokwi.toml`, `.pio/`,
screenshots, and serial logs stay in the workspace under `.gar/` and are not
committed here.
