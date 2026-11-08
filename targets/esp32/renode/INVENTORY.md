# ESP32 / M5StickC Plus2 Renode Inventory

This inventory records what GAR can reuse, what needs a small stub, and what
requires new modeling before Renode can boot an ESP32/M5StickC Plus2 firmware.

Decision words:

- `reuse`: use an existing Renode feature or GAR tool.
- `stub`: implement only enough behavior to unblock firmware execution.
- `write`: add a platform description, model, or bridge.
- `defer`: keep it out of the first bootable milestone.
- `unknown`: verify with a focused experiment first.

## Source references

- [Renode Xtensa ISA support](https://renode.io/news/xtensa-isa-in-renode-for-sof-project/)
  establishes CPU translation support, but does not claim a complete ESP32 board.
- [Supported boards](https://renode.readthedocs.io/en/latest/introduction/supported-boards.html)
  includes `XTENSA / xtensa-sample-controller`, not ESP32/M5Stack.
- [Renode testing](https://renode.readthedocs.io/en/latest/introduction/testing.html)
  documents its Robot Framework integration.
- [Renode wireless support](https://renode.readthedocs.io/en/latest/networking/wireless.html)
  does not provide an ESP32 Wi-Fi or Bluetooth controller model by itself.
- [Renode issue #704](https://github.com/renode/renode/issues/704) tracks the
  distinction between ESP32 translation support and a usable ESP32 platform.

## Current GAR assets

| Asset | Location | Decision | Notes |
|---|---|---:|---|
| ESP32 QEMU flash merger | `targets/esp32/qemu/bin/gar-esp32-flash-image` | reuse | Reference for artifact layout and flash offsets. |
| ESP32 QEMU runner | `targets/esp32/qemu/bin/gar-esp32-qemu-run` | reuse | Boot smoke-test oracle while Renode support grows. |
| M5Stack Renode sketch | `targets/esp32/renode/m5stack-core2-sketch.repl` | write | Loadable contract sketch, not a bootable platform. |
| M5Stack Renode script | `targets/esp32/renode/run-m5stack-core2-sketch.resc` | write | Loads the sketch and reports its current limitation. |
| M5Status Tiny smoke | `targets/esp32/renode/m5status-tiny/` | reuse | Verified Xtensa ELF execution and UART Robot assertion. |
| Protocol-level virtual device | selected product workspace | reuse | Fast fallback that does not execute firmware. |

## Target priority

Immediate target:

- M5StickC Plus2 running the selected product firmware.
- ESP32-PICO-V3-02 / Xtensa LX6-class execution.
- UART/SPP-style JSON Lines or IP/WebSocket as the first useful host boundary.

Deferred target:

- BugC2 actuator base and its STM32F030F4P6.
- Treat the base later as an I2C peripheral at address `0x38`; do not change the
  current Renode CPU target to Cortex-M0.

## Firmware touch surface

The exact product source is selected through the GAR workspace. A typical
M5StickC client uses the following surfaces:

| Firmware dependency | Used for | Decision | First-pass approach |
|---|---|---:|---|
| Arduino `setup()` / `loop()` | Main runtime | unknown | Prove a minimal non-M5 UART firmware first. |
| `Serial` | Logs and first observable output | reuse/stub | Connect a Renode UART analyzer. |
| FreeRTOS timers | Scheduler and delay | write | Add only the timer/interrupt behavior required by boot logs. |
| `M5Unified` | Display, buttons, and power | defer | Enable after Arduino hello-world runs. |
| Display API | Dashboard rendering | stub | Capture text or framebuffer activity later. |
| Buttons | Hardware command input | stub | Model controllable GPIO inputs after boot. |
| Wi-Fi/WebSocket | Network transport | defer | Keep QEMU or real hardware for this path initially. |
| Bluetooth SPP | JSON Lines transport | stub/write | Prefer a UART-backed firmware test mode before radio modeling. |
| ArduinoJson | Protocol encoding | reuse | Pure firmware library; no Renode model required. |
| eFuse MAC | Device identity | stub | Return a deterministic value when firmware first reads it. |

## Renode / ESP32 blocks

| Block | Decision | Current gap | First experiment |
|---|---:|---|---|
| Xtensa CPU execution | reuse | Verified for `sample_controller`, not ESP32 LX6 boot. | Replace the upstream sample with a GAR-built tiny UART ELF. |
| Dual-core behavior | defer | True SMP is unnecessary for the first proof. | Force single-core where supported. |
| RAM map | write | ESP32 memory regions are absent. | Derive the minimum map from firmware and QEMU logs. |
| Boot ROM / reset vector | write | No ESP32 boot platform exists here. | Try direct ELF load before ROM fidelity. |
| SPI flash | write | The sketch has no flash model. | Use the QEMU artifact offsets as the contract. |
| eFuse / system registers | stub | ESP-IDF may read them during startup. | Stub only accesses observed in logs. |
| Interrupt controller | write | FreeRTOS requires interrupt behavior. | Add after direct UART execution works. |
| Timers / watchdogs | write/stub | Scheduler startup may block. | Stub watchdogs and add the minimum timer. |
| UART0 | reuse/write | Analyzer exists; ESP32 UART mapping does not. | Map a minimal UART or use semihosting first. |
| GPIO buttons | stub | Three controllable inputs are needed. | Add after the main loop runs. |
| SPI LCD | stub/defer | Visual fidelity is not needed for first boot. | Observe transfers before modeling pixels. |
| PMIC / battery | stub/defer | M5Unified may probe power hardware. | Avoid M5Unified initially. |
| Wi-Fi / Bluetooth | defer | Controller modeling cost is high. | Use a simpler host transport first. |
| Robot tests | reuse | M5Status Tiny already proves the loop. | Keep adding assertions with each modeled surface. |

## Verified baseline

The reproducible baseline is Renode `1.16.1` with the upstream Xtensa Zephyr
hello-world sample. `m5status-tiny/run.py` pins both the Renode release and sample
ELF checksum, downloads the ELF into a temporary directory, and then runs either
the console smoke test or Robot assertion:

```bash
python3 targets/esp32/renode/m5status-tiny/run.py
python3 targets/esp32/renode/m5status-tiny/run.py --test
```

Verified behavior:

- the M5Stack skeleton loads with `$ORIGIN`-relative platform references;
- the Xtensa ELF loads and starts at `0x50000000`;
- UART emits `Booting Zephyr OS` and `Hello World! qemu_xtensa`;
- the Robot test observes both lines.

This proves the GAR/Renode headless execution loop only. It does not prove ESP32
LX6, ESP-IDF, Arduino, M5Unified, LCD, Wi-Fi, or Bluetooth compatibility.

## Immediate next tasks

1. Add a GAR-built tiny UART firmware, or identify an ESP32 direct-load ELF that
   Renode can start.
2. Emit a project-owned line such as `GAR_RENODE_HELLO`.
3. Use that target for ESP32 memory-map and boot experiments.
4. Defer button, LCD, and transport models until user code is reachable.

The primary risk is reaching user code in ESP32 Arduino output. Board-surface
work remains secondary until that boot path is demonstrated.
