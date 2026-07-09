# GAR Wokwi M5StackC Template

This directory is the source template for the generated Wokwi workspace at
`GaplessAgentRuntime/.gar/wokwi/m5stackc`.

When the Wokwi simulation backend is selected, `gar setup` or
`gar sim env start` copies this template, renders the `*.template` files, and
points the generated `platformio.ini` at the application repository.

Build:

```bash
pio run
```

The app source is not stored in this simulator template. GAR renders
`platformio.ini.template` with `src_dir` pointing to the Vibe Remote app
repository:

```text
gar-vibe-ui/vibe-remote/m5stickc-client/src
```

The app repository owns the firmware entry point at `src/main.cpp`. If your
checkout lives elsewhere, set `GAR_VIBE_REMOTE_M5_SRC_DIR` before running
`gar setup` or `gar sim env start`. The Wokwi workspace only swaps the linked
library surface: real builds link the real M5Unified package, while Wokwi builds
link `lib/M5Unified` from this template.

Simulator settings can be placed in `.env.local`. The app reads battery level
through `M5.Power.getBatteryLevel()`. In Wokwi, the local M5Unified shim returns
the simulated value from `VIBE_BATTERY_PERCENT`:

```dotenv
VIBE_BATTERY_PERCENT=95
```

Run with Wokwi CLI:

```bash
export WOKWI_CLI_TOKEN=...
wokwi-cli .
```

Run the button smoke scenario:

```bash
wokwi-cli . --scenario button.test.yaml --timeout 60000 --timeout-exit-code 1
```

Override paths with `GAR_WOKWI_PROJECT_DIR`, `GAR_WOKWI_TEMPLATE_DIR`,
`GAR_WOKWI_FIRMWARE`, `GAR_WOKWI_ELF`, and `GAR_WOKWI_TIMEOUT_MS`.
