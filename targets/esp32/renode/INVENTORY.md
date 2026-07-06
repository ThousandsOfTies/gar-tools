# ESP32 / M5StickC Plus2 Renode Inventory

This inventory is the first concrete step toward a bootable GAR Renode target
for the Vibe Remote M5StickC Plus2 client. It records what can be reused, what
should be stubbed, what likely needs new modeling work, and what can be
deferred.

Status words:

- `reuse`: use an existing Renode feature/model or existing GAR tool.
- `stub`: implement the smallest fake needed to unblock firmware execution.
- `write`: likely needs a new platform description/model/bridge.
- `defer`: do not solve for the first bootable milestone.
- `unknown`: verify with a small experiment before deciding.

## Source References

- Renode has Xtensa ISA support, originally added with the Sound Open Firmware
  work. The official note also frames ESP32-class chips as a future-facing use
  case, not as proof that full ESP32 boards are ready out of the box:
  https://renode.io/news/xtensa-isa-in-renode-for-sof-project/
- Renode's supported boards list has an `XTENSA / xtensa-sample-controller`
  entry, but no ESP32/M5Stack board entry in the supported-board list:
  https://renode.readthedocs.io/en/latest/introduction/supported-boards.html
- Renode supports Robot Framework based tests:
  https://renode.readthedocs.io/en/latest/introduction/testing.html
- Renode has wireless/networking facilities, but these are not equivalent to an
  ESP32 Wi-Fi or Bluetooth controller model:
  https://renode.readthedocs.io/en/latest/networking/wireless.html
- Open Renode issue #704 asks whether ESP32 is supported after ESP32
  translation-support release notes. Treat full ESP32 board support as
  unproven until a local hello-world target boots:
  https://github.com/renode/renode/issues/704

## Current GAR Assets

| Asset | Location | Decision | Notes |
|---|---|---:|---|
| ESP32 QEMU flash image merger | `targets/esp32/qemu/bin/gar-esp32-flash-image` | reuse | Good reference for artifact layout and offsets. |
| ESP32 QEMU runner | `targets/esp32/qemu/bin/gar-esp32-qemu-run` | reuse | Keep as boot smoke-test oracle while Renode grows. |
| M5Stack Renode sketch | `renode/m5stack-core2-sketch.repl` | write | Loadable contract sketch only; not a bootable ESP32 platform yet. |
| M5Stack Renode script | `renode/run-m5stack-core2-sketch.resc` | write | Entry-point skeleton; loads the sketch and prints a notice. |
| M5Status Tiny Renode smoke | `renode/m5status-tiny/` | reuse | Headless Xtensa firmware smoke target with Robot UART assertion. |
| Vibe Remote virtual device | `gar-vibe-ui/vibe-remote/scripts/virtual-device.js` | reuse | Fast protocol-level fallback; does not execute firmware. |
| Bluetooth SPP probe | `targets/esp32/probes/spp-jsonl/bin/gar-spp-jsonl-probe` | reuse | Real-device transport probe; useful reference for JSON Lines framing. |

## Target Priority

Immediate target:

- M5StickC Plus2 running Vibe Remote firmware.
- Primary SoC: ESP32-PICO-V3-02, Xtensa LX6-class ESP32 target.
- First useful boundary: UART/SPP-style JSON Lines or IP/WebSocket transport.

Deferred target:

- BugC2 base / actuator dock.
- Base MCU: STM32F030F4P6, Arm Cortex-M0.
- Treat it later as an I2C peripheral at address `0x38` from the M5StickC
  Plus2 firmware point of view. Do not switch the current Renode path to
  Cortex-M0 until Vibe Remote boot/transport is proven.

## Firmware Touch Surface

Source inspected: `gar-vibe-ui/vibe-remote/m5stickc-client/src/main.cpp`.

| Firmware dependency | Used for | Decision | First-pass approach |
|---|---|---:|---|
| Arduino runtime / `setup()` / `loop()` | Main firmware framework | unknown | Start with minimal non-M5 UART firmware first, then Arduino hello-world. |
| `Serial.begin`, `Serial.println` | Logs and first observable output | reuse/stub | Use Renode UART analyzer if boot reaches user code. |
| FreeRTOS/timers via Arduino core | Scheduler, delay, millis | write | ESP32 timer/interrupt compatibility is likely needed before Arduino runs. |
| `M5Unified` | Display/buttons/power init | defer | Avoid in the first minimal boot target. Add after Arduino hello-world works. |
| `M5.Display.*` | Dashboard rendering | stub | Capture text or framebuffer later; do not block first boot. |
| StickC Plus2 buttons | Hardware command input | stub | Model controllable GPIO inputs after boot path is proven. |
| `WiFi.h`, `ESPmDNS.h`, `WebSocketsClient` | Wi-Fi/WebSocket transport | defer | Too much for first Renode milestone. Keep QEMU or real hardware for this path. |
| `BluetoothSerial` / SPP | BT Classic JSON Lines transport | stub/write | Do not model radio first. Prefer a firmware mode that maps transport to UART. |
| `ArduinoJson` | Protocol parse/serialize | reuse | Pure firmware library; no Renode model needed. |
| `ESP.getEfuseMac()` | Device naming | stub | Fake eFuse/system register value when Arduino path reaches this call. |

## Renode / ESP32 Blocks

| Block | Decision | Gap | First experiment |
|---|---:|---|---|
| Xtensa CPU execution | unknown | Xtensa exists, but ESP32 LX6 configuration and boot flow are unproven locally. | Run a minimal Xtensa/Renode sample, then an ESP32 UART hello target if possible. |
| Dual-core ESP32 behavior | defer | Vibe Remote does not need true SMP fidelity first. | Force single-core if firmware/build supports it. |
| Internal RAM map | write | Need ESP32 memory regions matching boot/user code expectations. | Extract map from ESP-IDF/QEMU docs and current flash image boot log. |
| Boot ROM / reset vector | write | No platform implementation yet. | Try a boot-ROM bypass or direct ELF load for a hello target. |
| SPI flash mapping | write | Current `.repl` has no flash peripheral or mapping. | Reuse QEMU offsets as source of truth; decide `LoadBinary` vs SPI flash model. |
| Partition table / boot_app0 | reuse/write | Layout known from QEMU merger, but Renode boot interpretation missing. | Start from merged flash image and document first failing PC/log. |
| eFuse / system registers | stub | ESP-IDF/Arduino may read chip identity/config early. | Stub only registers observed in boot failure logs. |
| Interrupt controller | write | FreeRTOS startup will require timer/interrupt behavior. | Add only after direct UART hello proves CPU/memory path. |
| Timers / watchdogs | write/stub | `delay()`/FreeRTOS ticks and watchdog init may block. | Stub watchdog; implement minimum system timer required by logs. |
| UART0 | reuse/write | Renode has UART analyzers, but ESP32 UART register model may be absent. | Map UART to a simple model or semihosting UART for hello milestone. |
| GPIO | stub | Buttons need controllable inputs. | Add three button lines after firmware reaches main loop. |
| SPI LCD | stub/defer | Display fidelity is not needed for first boot. | Capture high-level text via firmware test mode before framebuffer work. |
| PMIC / battery / I2C peripherals | stub/defer | M5Unified may probe power hardware. | Avoid M5Unified first; stub reads when enabling full firmware. |
| Wi-Fi controller | defer | High modeling cost. | Keep WebSocket path for QEMU/real hardware; use UART/SPP-style transport in Renode. |
| Bluetooth controller / SPP | defer/stub | Modeling Classic BT radio/controller is not the shortest path. | Provide host bridge at UART/JSONL boundary instead. |
| BugC2 base I2C device | defer/stub | Actuator dock is useful later but not needed for Vibe Remote boot. | After Vibe Remote transport works, add an I2C `0x38` stub. |
| Robot tests | reuse | No tests yet. | Add one test that waits for `GAR_HELLO` on UART once minimal target runs. |

## First Boot Strategy

Do not begin with the full M5Stack Vibe Remote firmware. The first useful
Renode milestone is a small, boring boot proof:

1. Build or add a minimal ESP32/Xtensa firmware that prints a fixed UART line,
   e.g. `GAR_RENODE_HELLO`.
2. Create a `.resc` that loads it with the simplest viable method.
3. Show a UART analyzer or Robot terminal tester can observe the line.
4. Record the exact Renode version, load method, and any unsupported access
   logs.

Only after that should we attempt Arduino, M5Unified, button, display, or Vibe
Remote transport behavior.

## Experiment Log

### 2026-06-18: Codespaces Renode install and Xtensa smoke test

Environment:

- Codespace: `friendly-dollop-rq94rwxrxrvfwwv4`
- Host: Linux x86_64
- Renode: `v1.16.1.17033`, build `d66b0c2a-202602160923`
- Runtime: `.NET 8.0.12`

Actions:

1. Installed Renode portable dotnet build:
   `renode-1.16.1.linux-portable-dotnet.tar.gz`.
2. Linked launchers under `~/.local/bin/renode` and
   `~/.local/bin/renode-test`.
3. Ran GAR skeleton script:
   `renode --console --disable-xwt --execute "include @run-m5stack-core2-sketch.resc; quit"`.
4. Ran Renode's bundled Xtensa sample script:
   `scripts/single-node/xtensa.resc`.
5. Created a Python venv for Renode test dependencies and ran:
   `renode-test tests/platforms/xtensa.robot`.

Results:

- GAR M5Stack skeleton loads in Renode and prints the expected skeleton notice.
- Renode bundled Xtensa Zephyr sample prints:
  - `Booting Zephyr OS`
  - `Hello World! qemu_xtensa`
- Renode bundled `tests/platforms/xtensa.robot` passes both tests:
  - `Test Division`
  - `Test Zephyr hello_world sample`

Decision update:

- `Xtensa CPU execution` moves from pure unknown to **verified for Renode's
  `sample_controller` CPU type**.
- ESP32/LX6 boot remains **unverified**. The next experiment must target ESP32
  memory map/boot behavior, not generic Xtensa alone.

### 2026-06-18: WSL Renode install and Xtensa smoke test

Environment:

- Host: WSL2 Linux x86_64 (`DESKTOP-1S52NGH`)
- Renode: `v1.16.1.17033`, build `d66b0c2a-202602160923`
- Runtime: `.NET 8.0.12`
- Python: `3.14.4`

Notes:

- The Renode dotnet portable build required ICU (`libicu`) to be available on
  WSL before `renode --version` could run.
- Renode's pinned test dependency `psutil==5.9.3` does not have a Python 3.14
  wheel and would require local C build tools. The WSL test venv uses
  `psutil>=6.1` instead; `psutil 7.2.2` installed from a prebuilt wheel.

Results:

- `renode --version` succeeds.
- `renode-test tests/platforms/xtensa.robot` succeeds:
  - `Test Division`: OK
  - `Test Zephyr hello_world sample`: OK
  - total: `pass=2`, `fail=0`

### 2026-06-18: M5Stack skeleton path fix

Environment:

- Host: WSL2 Linux x86_64 (`DESKTOP-1S52NGH`)
- Renode: `v1.16.1.17033`, build `d66b0c2a-202602160923`

Action:

```bash
renode --console --disable-xwt --execute \
  "include @targets/esp32/renode/run-m5stack-core2-sketch.resc; quit"
```

Result:

- Initial run failed because `run-m5stack-core2-sketch.resc` loaded
  `@m5stack-core2-sketch.repl` relative to the current working directory.
- Changed the platform reference to `$ORIGIN/m5stack-core2-sketch.repl`.
- The skeleton now loads from the repository root and prints the expected
  "M5Stack Core2 Renode platform is a skeleton" notice.

Decision update:

- M0 repository contract is stronger: the Renode entry script is now a
  loadable skeleton, not merely a note file.
- This still does not prove ESP32/LX6 boot. M2 remains the next boot milestone.

### 2026-06-18: M5Status Tiny Renode firmware smoke

Environment:

- Host: WSL2 Linux x86_64 (`DESKTOP-1S52NGH`)
- Renode: `v1.16.1.17033`, build `d66b0c2a-202602160923`

Added:

- `m5status-tiny/run.resc`
- `m5status-tiny/m5status-tiny.robot`
- `m5status-tiny/README.md`

Actions:

```bash
renode --console --disable-xwt --execute \
  "include @targets/esp32/renode/m5status-tiny/run.resc; start; quit"

renode-test targets/esp32/renode/m5status-tiny/m5status-tiny.robot
```

Results:

- Renode can load and start the target.
- Robot test passes and observes UART output:
  - `Booting Zephyr OS`
  - `Hello World! qemu_xtensa`

Decision update:

- The GAR/Renode headless firmware-test loop is now proven.
- This target uses Renode's upstream Xtensa sample-controller ELF. It is an
  executable firmware smoke target, not an ESP32 LX6/M5Unified boot proof.
- Next step is replacing the upstream ELF with a GAR-built tiny UART firmware
  that prints a project-owned line such as `GAR_RENODE_HELLO`.

## Immediate Next Tasks

1. Add a GAR-built tiny UART firmware source/build path, or identify an ESP32
   direct-load hello target that Renode can start.
2. Replace the upstream sample ELF in `m5status-tiny` or add a sibling target
   that prints `GAR_RENODE_HELLO`.
3. Use the new UART target as the base for Arduino/FreeRTOS boot experiments.

## Current Risk Summary

The highest risk is not button/LCD/SPP. The highest risk is reaching user code
at all with ESP32 Arduino output. Treat all board-surface work as secondary
until a UART hello target runs in Renode.
