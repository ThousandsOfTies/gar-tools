# ESP32 Target Tools

This directory is the GAR-owned home for tools that make ESP32/M5StickC Plus2
usable as a GAR target.

The long-term GAR direction is Renode: an AI-maintained virtual board with
scriptable peripherals, analyzers, and CI tests. See
[`renode/ROADMAP.md`](renode/ROADMAP.md).

The practical short-term path for `firmware.bin` smoke tests is Espressif QEMU,
plus Bluetooth Classic SPP probes for M5StickC Plus2-class real hardware.

These are optional target tools. The default GAR setup path for ESP32/M5Stack is
Wokwi; QEMU, Renode, fake-idf, and probes should be pulled into the workflow only
when a specific verification task needs them.

1. Build or collect a flash bundle:
   - `bootloader.bin`
   - `partitions.bin`
   - `boot_app0.bin`
   - `firmware.bin`
2. Merge it into one flash image with the same offsets used for flashing.
3. Run the image with `qemu-system-xtensa` from Espressif's QEMU fork.

Renode files in `renode/` are intentionally a growing platform skeleton. The
immediate target is M5StickC Plus2 Vibe Remote firmware. BugC2 base / actuator
dock support is deferred and should be treated later as an I2C peripheral from
the StickC firmware's point of view.

## Run the smallest Renode firmware smoke test

`renode/m5status-tiny/` is the first headless firmware execution target in this
tree. It uses Renode's verified Xtensa sample-controller platform and upstream
Zephyr hello-world ELF, then checks UART output with Robot Framework.

```bash
python3 targets/esp32/renode/m5status-tiny/run.py --test
```

The runner verifies its pinned ELF checksum before starting Renode. This proves
the GAR/Renode firmware-test loop: load ELF, start emulation, and wait for UART
output. It does not yet prove ESP32 LX6, Arduino, M5Unified, LCD, buttons, Wi-Fi,
or Bluetooth.

## Build and deploy a target artifact

The normal physical-device path uses the selected product build hook and the
`esp32_esptool` target backend:

```bash
gar target build
gar target deploy
```

GAR stores the resulting immutable artifact snapshot under its `.gar/artifacts`
directory and verifies the ESP32 flash bundle before writing it. The lower-level
QEMU helper can consume the same four-file artifact directory for an optional
boot smoke test.

## Build a QEMU flash image manually

```bash
FLASH_IMAGE="$(mktemp)"
targets/esp32/qemu/bin/gar-esp32-flash-image \
  --artifact path/to/esp32-artifact \
  --output "$FLASH_IMAGE"
```

Default offsets:

| offset | file |
|---:|---|
| `0x1000` | `bootloader.bin` |
| `0x8000` | `partitions.bin` |
| `0xe000` | `boot_app0.bin` |
| `0x10000` | `firmware.bin` |

## Run with QEMU

```bash
targets/esp32/qemu/bin/gar-esp32-qemu-run "$FLASH_IMAGE"
```

The runner expects `qemu-system-xtensa` on `PATH`. ESP-IDF can install
Espressif QEMU with:

```bash
python "$IDF_PATH/tools/idf_tools.py" install qemu-xtensa
. "$IDF_PATH/export.sh"
```

## Probe Bluetooth SPP

For M5StickC Plus2-class firmware built with `VIBE_TRANSPORT_SPP=1`, Bluetooth
Classic SPP appears to the host OS as a serial port. GAR treats that port as a
newline-delimited JSON transport using the same payloads as Vibe Remote's
WebSocket channel.

On Linux/WSL hosts, bind the paired device to an RFCOMM device first. The exact
pairing flow is host-specific; after pairing, the smoke probe shape is:

```bash
targets/esp32/probes/spp-jsonl/bin/gar-spp-jsonl-probe \
  /dev/rfcomm0 \
  --token YOUR_TOKEN \
  --status running
```

The probe sends `hello`, optional `agentStatus`, and `ping`, then prints inbound
JSON lines such as `ack` and `state`. It is intentionally a protocol/transport
smoke test: it does not emulate Bluetooth radio behavior or boot firmware.

## Runtime layers

| Layer | Location | Purpose |
|---|---|---|
| Protocol-level virtual device | selected product workspace | Fast protocol test double; does not boot firmware |
| Fake ESP-IDF / FreeRTOS link stubs | `targets/esp32/fake-idf/` | Minimal host-side headers and static library for apps to link before real simulation exists |
| Bluetooth SPP probe | `targets/esp32/probes/spp-jsonl/bin/gar-spp-jsonl-probe` | Real StickC Plus2-class device smoke test over OS serial/RFCOMM |
| QEMU firmware runner | `targets/esp32/qemu/bin/` | Short-term ESP32 boot smoke test for built artifacts |
| Wokwi backend assets | `targets/esp32/wokwi/` | Runnable workspace template, wiring, and M5Unified compatibility shim |
| M5Status Tiny Renode smoke | `targets/esp32/renode/m5status-tiny/` | First headless Renode firmware execution + UART Robot test |
| Renode virtual board | `targets/esp32/renode/` | Long-term GAR ideal: scriptable M5Stack board model |

## Scope

This runner targets firmware-level execution. It is different from the Vibe
Remote virtual device, which simulates the protocol/device boundary without
booting the ESP32 binary.
