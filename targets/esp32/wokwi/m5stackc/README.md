# GAR Wokwi M5StackC Template

This directory is the source template for an M5StackC Wokwi build workspace.

The product's `scripts/product-sim-build.sh` invokes
`scripts/prepare_workspace.py`, builds the firmware, and packages a GAR
simulation-app artifact. `gar sim app deploy` materializes the runnable files
from that artifact into the selected runtime workspace. `gar setup` only
selects and installs Wokwi, while `gar sim runtime start` only launches the
deployed project.

For direct template development, run the product-owned Make target and choose a
generated workspace outside the application source and this template:

```bash
cd /path/to/product/m5stickc-client
make wokwi-build \
  GAR_TOOLS_ROOT=/path/to/gar-tools \
  WOKWI_WORKSPACE=/tmp/gar-wokwi-m5stackc
```

The workspace must be empty on its first generation. Subsequent updates require
its `.gar-generated` marker. Generated files are refreshed while build output
such as `.pio/` is preserved. The application source directory, template, and
generated workspace must not overlap.

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

The shared template currently provides no Wokwi CLI scenario. Automated
scenarios are product behavior and must be supplied and packaged by the product
that owns them.

The workspace generator uses these variables:

- Required when calling the generator directly: `GAR_WOKWI_PROJECT_DIR` and
  `GAR_WOKWI_APP_SRC_DIR`.
- Optional: `GAR_WOKWI_TEMPLATE_DIR` and `GAR_WOKWI_APP_CONFIG`.
- `GAR_WOKWI_FIRMWARE` and `GAR_WOKWI_ELF` override the paths rendered into
  `wokwi.toml`.

At runtime, GaplessAgentRuntime reads `GAR_WOKWI_PROJECT_DIR`,
`GAR_WOKWI_FIRMWARE`, `GAR_WOKWI_ELF`, and `GAR_WOKWI_TIMEOUT_MS`.
