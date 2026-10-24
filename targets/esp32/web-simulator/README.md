# T-Watch 2020 V3 Web simulator tools

The shared server, RGB565 decoder, LVGL builder/surface, controls and event log
now live in [`web-simulator/`](../../../web-simulator/README.md). This target
directory owns the T-Watch hardware shell and keeps compatibility entrypoints.
New Products should import `/gar-components/` and compose the common parts;
they do not need to copy the T-Watch panel or its application protocol.

Reusable browser peripherals for the ESP32 T-Watch 2020 V3. The generic peripheral
bench requires no npm packages, build step, external CDN or account. Python 3.10+
runs the local HTTP tool; the exported panel only needs a static web server.
Products can additionally compile their shared LVGL 7 UI with Emscripten.

```bash
python targets/esp32/web-simulator/serve.py
# Open http://127.0.0.1:8765 for the generic peripheral bench.
python targets/esp32/web-simulator/serve.py --panel /path/to/product/simulation
python targets/esp32/web-simulator/serve.py --panel /path/to/product/simulation --export /path/to/empty-output
```

`make web-simulator PANEL=/path/to/product/simulation` is the equivalent development
entrypoint. `--host` and `--port` select the listener (default `127.0.0.1:8765`).
Only public asset types are served/exported; hidden files and paths outside the
selected roots are excluded. Existing export output is never removed.

## Component API

```html
<gar-twatch-2020 battery="82" brightness="85" powered="true"></gar-twatch-2020>
<script type="module" src="./components/twatch-2020.mjs"></script>
```

- `displayContext`: Canvas 2D context with a fixed 240 × 240 backing buffer.
- `writeFrame(Uint8Array, {littleEndian: false})`: draw exactly 115200 RGB565 bytes.
- `setScreenLabel(text)`: accessible description for the display.
- `battery`, `brightness`: numeric properties/attributes clamped to 0–100.
- `powered`: boolean property; the `powered="false"` attribute turns the display off.
- `charging`: boolean attribute reported with the hardware state.
- `screen` slot: supply ordinary HTML elements for an interactive display.
  While populated, it replaces the canvas and left/right touch regions. Buttons,
  scrolling and keyboard focus use native DOM behavior; attach application event
  handlers to those elements. Brightness affects the whole display, and power-off
  hides it and makes the slotted subtree inert. The side button remains available.
  The slot's container supports `cqw` sizing relative to the actual screen width.

```html
<gar-twatch-2020>
  <div slot="screen" style="height:100%;background:#10261d;padding:5cqw">
    <button type="button" id="start">Start</button>
  </div>
</gar-twatch-2020>
```

Use `document.querySelector("#start").addEventListener("click", handler)` to
handle that element directly. Slotted elements do not emit `gar-touch`; that
event belongs to the default canvas surface.

Events bubble across the Shadow DOM boundary:

| Event | Detail |
| --- | --- |
| `gar-touch` | `phase`: start/move/end/cancel; `x`, `y`: 0–239; end includes `durationMs` |
| `gar-button` | `button: "power"`; `phase`: down/up/cancel; release includes `durationMs`, `held` |
| `gar-hardware-change` | `battery`, `brightness`, `powered`, `charging` |

Touch input uses pointer capture and a single active contact. Cancellation,
window blur, power-off and removing the element release active input. Focus the
left/right screen half or side button and use Space/Enter for keyboard operation.
A six-second side-button hold toggles power; an ordinary release is left to the
Product adapter. Each component has independent state and removes its listeners
on disconnect, so reconnecting it does not duplicate gestures.

Products compose shared controls and event logs with their display drawing,
input mapping, state, scenarios and authentication. `/gar-components/` provides
the shared assets. The original three `/components/` module URLs remain aliases.
Relative imports work in static exports too.

This is a peripheral/UI simulation surface, not an Xtensa CPU emulator. It does
not boot firmware.bin or model Bluetooth radio, I2C timings, electrical behavior,
battery discharge or sensor accuracy. Use the existing firmware runners and
physical-device checks for those verification layers.

## Shared LVGL application port

`build_lvgl.py` compiles a Product-supplied LVGL 7 application and fonts into
`lvgl-ui.mjs` and `lvgl-ui.wasm`. Use the same pinned LVGL sources and configuration
as the physical build. Requires Emscripten (validated with 4.0.15):

```bash
python build_lvgl.py --library /path/to/lilygo-library \
  --json-library /path/to/ArduinoJson --app /path/to/shared-ui \
  --config /path/to/shared-ui/lv_conf.h \
  --output /path/to/product/simulation/runtime --cache /path/to/object-cache
```

`lvgl/web-port.c` supplies a 240 × 240 RGBA display and pointer driver. The Product's
`web-entry.cpp` supplies the `gar_app_*` C ABI declared in `EXPORTS` in the builder:
initialization, JSON receive, device state, refresh/reset, side button, scroll,
snapshot and action dequeue. Snapshot nodes contain `id`, `actionId`, `label`,
`x`, `y`, `width`, `height`; coordinates must come from actual LVGL objects.
No Product screens or actions belong in this tool directory.

`LvglSurface` in `components/lvgl-surface.mjs` connects this compiled module to a
slotted display containing a 240 × 240 canvas and a `[data-lvgl-controls]` layer.
It copies the LVGL framebuffer and mirrors accessible button bounds/names.
All pointer and keyboard input goes back through LVGL's input driver. Application
callbacks determine actions and hold behavior. It emits `action` with the outgoing
JSON, and exposes `receive`, `hardware`, `reset`, `sideButton` and `destroy`.
The Product styles the canvas and overlay with matching dimensions and calls
`destroy` when disposing the surface. The server serves/exports `.wasm` with
`application/wasm` for browser streaming compilation.

## Checks

```bash
python -m unittest discover -s tests -p test_web_simulator.py -v
node --test targets/esp32/web-simulator/tests/*.test.mjs
```

Both checks are included in the repository's existing `make check` flow.

The dependency-free browser regression page covers real Canvas output, keyboard
gestures, cancellation, component removal/reconnection, independent instances,
and six-second power hold behavior:

```bash
python targets/esp32/web-simulator/serve.py --panel targets/esp32/web-simulator/tests/browser --port 8768
```

Open `http://127.0.0.1:8768` and wait for the visible pass/fail report.
