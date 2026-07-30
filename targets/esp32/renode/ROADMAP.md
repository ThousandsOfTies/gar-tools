# M5Stack / ESP32 Renode roadmap

This is the long-term GAR path for running M5Stack firmware on an AI-maintained
virtual board.

QEMU is useful as a short-term boot smoke test. Renode is the target shape for
GAR because it lets us grow a board description, peripheral models, analyzers,
and CI tests as first-class project assets.

## Goal

Create a firmware-level equivalent of the existing GAR device compatibility
runtime:

```text
Linux app today:
  same ARM64 binary
  -> EC2 Graviton
  -> fake /dev/i2c-1, /dev/spidev0.0, /dev/gpiochip0
  -> RasPi5 real hardware

M5Stack target:
  same ESP32 firmware image
  -> Renode virtual M5StickC Plus2-class board
  -> virtual UART/GPIO/LCD/network-or-SPP boundary
  -> M5Stack real hardware
```

The important property is not a perfect visual simulator. It is repeatable,
scriptable firmware execution that AI agents and CI can observe and drive.

## Non-goals for the first pass

- Do not claim M5StickC Plus2 is bootable in Renode until it actually is.
- Do not model every ESP32 peripheral up front.
- Do not block firmware work on a perfect LCD, Wi-Fi, or Bluetooth radio model.
- Do not replace QEMU until Renode can boot at least a minimal firmware.
- Do not detour into BugC2 base / STM32F030F4P6 boot yet. The actuator dock is
  a later I2C peripheral from the M5StickC Plus2 firmware point of view.

## Milestones

### M0: Repository contract

Status: done.

- Keep Renode files under `targets/esp32/renode/`.
- Keep QEMU tools under `targets/esp32/qemu/bin/` as a reference
  runner and smoke-test path.
- Document the difference between protocol-level virtual device, QEMU runner,
  and Renode virtual board.

Done when:

- `README.md` points here.
- `.repl` and `.resc` clearly say they are a platform skeleton.

### M1: Inventory

Status: done. See [`INVENTORY.md`](INVENTORY.md).

Build a factual inventory of reusable parts.

- Renode upstream:
  - supported Xtensa status
  - available CPU hooks
  - SPI flash examples
  - UART/GPIO/SPI/I2C examples
  - Robot Framework test examples
- Espressif:
  - boot image layout
  - ROM/bootloader expectations
  - QEMU ESP32 device behavior worth mirroring
- M5Stack / M5StickC Plus2:
  - ESP32-PICO-V3-02 / Xtensa LX6 boot assumptions
  - button GPIO mapping
  - LCD controller and SPI wiring
  - power-management IC behavior that firmware touches
  - StickC Plus2 vs Core/Core2 differences
  - BugC2 base I2C command surface, later only
- Our firmware:
  - which Arduino/M5 APIs are used
  - which ESP-IDF/Arduino subsystems initialize before `setup()`
  - minimal boot log expectations

Done when:

- `INVENTORY.md` lists each required block, source links, and reuse decision:
  `reuse`, `stub`, `write`, or `defer`.

### M2: Minimal Renode execution target

Status: partially done.

M2a, a headless Renode/Xtensa firmware smoke target, is done under
[`m5status-tiny/`](m5status-tiny/). It loads Renode's upstream Xtensa Zephyr
hello-world ELF and verifies UART output with Robot Framework. This proves the
GAR/Renode firmware-test loop, but it is not ESP32 LX6 boot yet.

Do not start with the full Vibe Remote firmware. Start with the smallest
firmware that proves the CPU/boot path.

Candidate firmware:

- ESP32 app that writes a fixed line to UART.
- No Wi-Fi.
- No LCD.
- No M5Stack library if avoidable.

Done when:

- A Renode script can load/start the minimal target.
- A Robot test can wait for a UART line.
- The test can run headlessly.

Remaining for full M2:

- Replace the upstream Xtensa sample ELF with a GAR-built tiny UART firmware, or
  an ESP32 direct-load hello target if the Renode platform supports it.
- Make the expected UART line project-owned, e.g. `GAR_RENODE_HELLO`.

### M3: ESP32 boot compatibility

Grow the platform until a realistic ESP32 app can reach `app_main()`/Arduino
`setup()`.

Likely work:

- Flash mapping and image offsets.
- Reset vector / boot ROM behavior or a practical bypass.
- Timers needed by FreeRTOS.
- Interrupt controller behavior used during scheduler start.
- UART0 output.
- Enough eFuse/system registers to satisfy boot code.

Done when:

- A FreeRTOS/Arduino hello-world target reaches user code in Renode.
- Boot blockers are documented with logs and commit references.

### M4: M5StickC Plus2 board surface

Add the hardware surface used by the Vibe Remote client.

Initial scope:

- StickC Plus2 buttons as controllable GPIO inputs.
- LCD writes captured at the SPI transaction level.
- A text or framebuffer extractor for the GAR observation path.
- Optional power/battery stubs if the M5 library reads them.
- BugC2 base / actuator dock is out of scope here except as a later I2C
  peripheral stub at address `0x38`.

Done when:

- A test can press A/B/C from Renode or Robot Framework.
- Display activity is observable without a human screen.

### M5: Vibe Remote boundary

Decide how the host/device boundary should work.

Options:

- Model enough ESP32 networking to let the firmware use Wi-Fi/WebSocket.
- Model or bridge Bluetooth Classic SPP as a serial JSON Lines transport.
- Provide a Renode external peripheral or host bridge that maps firmware I/O to
  the Vibe Remote protocol.
- Build a test firmware mode that keeps the production state machine but uses a
  simpler host transport.

Done when:

- GAR can drive a firmware-level Vibe Remote session without a physical M5Stack.
- The protocol-level virtual device remains as a fast fallback.

### M6: GAR integration

Connect the Renode backend to GAR's existing target manifest and artifact flow.

Desired command shape:

```bash
gar sim app build
gar sim app deploy
gar sim runtime start
gar sim runtime diag --json
```

Done when:

- The target manifest names the artifact, runtime, board, and observable ports.
- Logs/artifacts are captured under a GAR-owned run directory.
- CI can run at least one headless firmware test.

## Working rules

- Keep each missing peripheral documented as a small, testable gap.
- Prefer stubs for firmware-unblocking reads before full hardware fidelity.
- Add Robot tests as soon as Renode can expose a signal or UART line.
- Keep the protocol-level Vibe Remote virtual device alive as the fast test
  double.
- Use QEMU output to distinguish firmware bugs from Renode platform gaps.

## Current open questions

- Can current Renode execute enough Xtensa/ESP32 code to reach user firmware?
- Is a boot-ROM bypass practical for our Arduino/PlatformIO output?
- What is the smallest M5StickC Plus2-compatible board surface needed before
  the Vibe Remote firmware reaches useful user code?
- Should Wi-Fi/Bluetooth be modeled below the socket/radio APIs, or should GAR
  provide a host bridge at a higher boundary such as WebSocket or SPP serial?
