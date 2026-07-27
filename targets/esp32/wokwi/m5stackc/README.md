# GAR Wokwi M5StackC Template

This directory is the source template for the generated Wokwi workspace at
`GaplessAgentRuntime/.gar/wokwi/m5stackc`.

When the Wokwi simulation backend is selected, `gar setup` or
`gar sim runtime start` copies this template, renders the `*.template` files, and
points the generated `platformio.ini` at the application repository.

Build:

```bash
pio run
```

The app source is not stored in this simulator template. The shared
`scripts/prepare_workspace.py` renders `platformio.ini.template` with `src_dir`
pointing to the selected M5Stick application repository:

```text
<application>/m5stickc-client/src
```

The app repository owns the firmware entry point at `src/main.cpp`. If your
checkout lives elsewhere, set `GAR_WOKWI_APP_SRC_DIR` before generating the
workspace. The Wokwi workspace only swaps the linked
library surface: real builds link the real M5Unified package, while Wokwi builds
link `lib/M5Unified` from this template.

An application can provide an optional Wokwi PlatformIO overlay through
`GAR_WOKWI_APP_CONFIG`. It holds application-specific libraries and build flags.
The shared M5Unified shim supports a simulated battery level through
`M5STICK_BATTERY_PERCENT`:

```dotenv
M5STICK_BATTERY_PERCENT=95
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
