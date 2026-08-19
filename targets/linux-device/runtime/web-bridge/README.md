# Hardware web bridge

`bridge.py` connects the Linux CUSE simulator stubs to a browser control panel.
One aiohttp server provides all browser-facing endpoints:

- `http://HOST:8080/` — control panel
- `http://HOST:8080/api/state` — current state and resolved hardware mapping
- `http://HOST:8080/api/metrics/{application}` — read-only application metric JSON
- `ws://HOST:8080/ws` — live events and panel commands
- `GAR_HW_SIM_SOCK` — newline-delimited JSON Unix socket used by C stubs

The panel derives `ws://` or `wss://` and the port from its own URL. Therefore
only the HTTP port has to be published by Docker or forwarded over SSH.

`/api/metrics/{application}` reads `${GAR_METRICS_DIR:-/run/gar/metrics}/<application>.json`.
Application names are restricted to safe filename characters; the bridge accepts only a regular,
non-symlink file of at most 1 MiB whose JSON root is an object. Missing and invalid files return
a structured JSON error and never execute application code.

## Hardware mapping

Set `GAR_HARDWARE_DIR` to the directory containing GAR's `gpio.csv`, `i2c.csv`,
and `spi.csv`. `gpio.csv` controls every input and output line. The following
names give GPIOs their bridge-specific meaning:

| Function | Recognised `gpio.csv` names |
|---|---|
| Rotary phase A / clock | `encoder_a`, `rotary_a`, `rotary_clk`, `ky040_a`, `ky040_clk` |
| Rotary phase B / data | `encoder_b`, `rotary_b`, `rotary_dt`, `ky040_b`, `ky040_dt` |
| Rotary switch | `encoder_sw`, `rotary_sw`, `ky040_sw` |
| Display data/command | `lcd_dc`, `display_dc`, `ili9341_dc` |

The rotary mapping is accepted only when all three rotary lines are present.
GPIO rows with role `button` or `led` become the corresponding panel controls.
The `sim` column in `i2c.csv` and `spi.csv` decides which device sections the
panel displays. An empty `sim` value means that GAR does not emulate that real
device. Older CSVs without a `sim` column fall back to `driver`.

When `GAR_HARDWARE_DIR` is unset, the bridge starts without GPIO or simulated
devices; it never invents an application profile from the selected target.
When a Product directory is explicitly configured, a missing or headers-only
`gpio.csv` means that no GPIO is configured; simulated devices from `i2c.csv`
and `spi.csv` are still loaded. A missing directory or malformed existing CSV
is an error rather than a reason to silently use unrelated line numbers.

## Running and checking

```bash
python3 -m pip install \
  -r targets/linux-device/runtime/web-bridge/requirements.txt
GAR_HARDWARE_DIR=/path/to/product/hardware \
  python3 targets/linux-device/runtime/web-bridge/bridge.py
python3 -m unittest discover \
  -s targets/linux-device/runtime/web-bridge/tests -v
python3 targets/linux-device/runtime/web-bridge/tests/smoke_bridge.py
```

The last command creates isolated test-only hardware fixtures, starts a live
bridge for each fixture, and checks HTTP state/static delivery, same-origin
WebSocket access, invalid request and framebuffer handling, traversal rejection,
Unix-socket ownership, and safe recovery from a stale socket.

The bridge listens on `127.0.0.1:8080` by default. Set `GAR_BRIDGE_HOST` or
`GAR_BRIDGE_PORT` when another bind address or port is required. In particular,
a container that publishes the bridge must explicitly set
`GAR_BRIDGE_HOST=0.0.0.0`.

Browser requests are accepted only when their `Host` hostname is allowed, and
requests carrying an `Origin` must be same-origin. The default host allowlist is
`127.0.0.1`, `localhost`, and `::1`; an explicit non-wildcard
`GAR_BRIDGE_HOST` is also included. Set `GAR_BRIDGE_ALLOWED_HOSTS` to a
comma-separated list of hostnames or IP addresses when the panel is reached by
another name. Do not include schemes or ports. This check limits browser-based
cross-origin control; it is not an authentication layer, so expose the bridge
only on trusted networks.

Browser messages are limited to 64 KiB. Unix-socket JSON lines are limited to
2 MiB so an ILI9341 frame fits without allowing an unbounded connection buffer.
The Unix socket is created with mode `0660`, accepts at most 16 concurrent stub
connections, and closes a newly connected client that sends no complete first
message within five seconds. Established C stubs may remain connected between
requests.
