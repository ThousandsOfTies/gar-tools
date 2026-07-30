# Luckfox RV1106 Target Tools

This target scaffold is for Luckfox Pico Plus/Pro/Max boards based on RV1106
running Buildroot Linux.

Setup guides:

- `docs/00_FIRST_BOOT_USB_SERIAL.md`: first-boot checklist and copy-paste command flow.
- `docs/01_PERSISTENT_USB_SSH.md`: persistent usb0 + SSH boot configuration examples.
- `docs/02_ZERO_DIFF_POLICY.md`: zero-modification policy between real device and EC2 simulation.
- `docs/03_CAMERA_CUSE_ROADMAP.md`: camera CUSE-first implementation milestones.
- `docs/04_CAMERA_IOCTL_CAPTURE_TEMPLATE.md`: M0 ioctl capture and diff template for `/dev/video0`.
- `docs/05_RV1106_FEATURE_MENU.md`: RV1106-specific feature ideas with implementation priority.
- `docs/06_ROTARY_ISP_RASPI_VIEW.md`: rotary ISP + local mini UI + RasPi remote view implementation guide.
- `docs/07_SIM_FIRST_ROTARY_UI.md`: simulator-first rotary UI with \u25c0 \u25cf \u25b6 controls.
- `docs/08_SIM_MONITOR_OUTPUT.md`: simulator-first monitor output dummy.
- `runtime/README.md`: remote Linux low-layer substitution and launcher usage.

Focus:

- Camera capture from SC3336 (`/dev/video0`) with Rockchip media pipeline.
- H.264 encoding via hardware encoder (RKMedia / MPP).
- RTSP streaming.
- Local menu UI on ILI9341.
- Rotary encoder (KY-040) based real-time parameter control.

Simulation policy:

- EC2 Graviton over `ssh_remote` is the default simulation model (aligned with Linux/RasPi-compatible target workflow).
- For Linux `/dev` surface simulation on EC2, use device-file substitution (CUSE/gpio-sim) with runtime assets under `targets/linux-device/runtime`.
- Standard Luckfox EC2 flow uses the GAR-generated systemd runtime. The scripts
  under `runtime/bin/` are direct diagnostics for runtime development, not the
  normal orchestration path.
- GAR primary simulation strategy is AI-driven system substitution with CUSE/gpio-sim, not HAL replacement.
- Camera simulation target is CUSE-based `/dev/video0`; `v4l2loopback` remains transitional fallback.
- Hardware-specific camera ISP/encoder behavior (RKMedia/MPP/rkaiq) must be validated on real Luckfox hardware.
- App policy is zero-diff: keep one app source and one device-path contract for real + sim.

## Directory map

- `hardware/`: default hardware CSV template used by `gar hw init`.
- `app-template/`: lightweight C/C++ project skeleton for cross build.
- `toolchain/`: CMake toolchain template for Buildroot SDK.
- `scripts/`: direct SSH/USB-network helpers for target bring-up and diagnostics.

Simulator-first control loop entrypoint:

- `runtime/bin/gar-luckfox-sim-control-loop`: rotary UI + ISP state machine simulation.
- `runtime/bin/gar-luckfox-sim-monitor`: monitor output dummy renderer.

## First-step proposal: library/tool selection

1. Camera/encode/ISP
   - Primary: Rockchip `RKMedia (MPI)` + `librkaiq` + MPP-backed encoder.
   - Fallback: GStreamer stack if BSP already ships stable Rockchip plugins.
2. RTSP
   - Primary: RKMedia-integrated RTSP sample server pattern.
   - Fallback: `live555` for explicit session control.
3. UI
   - Primary: framebuffer direct draw for minimum footprint.
   - Optional: LVGL with fbdev backend when menu complexity increases.
4. Rotary encoder and keys
   - `libgpiod` for line event handling and debounced edge processing.

## GAR workflow

The manifest selects `ssh_scp` for a real Luckfox target and `ssh_remote` for
its Linux simulation host. From the `GaplessAgentRuntime` root, use the common
artifact flow:

```bash
scripts/gar setup
scripts/gar hw init --dir path/to/product/hardware

# simulation
scripts/gar sim host start
scripts/gar sim runtime build
scripts/gar sim runtime deploy
scripts/gar sim runtime start
scripts/gar sim runtime diag --json

# physical target
scripts/gar target build
scripts/gar target deploy
```

The selected product workspace owns the build hooks and artifact manifest.
`gar-tools` provides the target definition, hardware template, runtime, and the
following standalone application scaffold.

## Develop the standalone cross-build scaffold

Set these environment variables before build:

- `RV1106_TOOLCHAIN_BIN`: directory containing cross compiler binaries.
- `RV1106_SYSROOT`: Buildroot SDK sysroot path.
- `RV1106_TRIPLE`: compiler triple prefix (example: `arm-linux-gnueabihf`).
- `LUCKFOX_HOST`: target host (USB default example: `root@10.42.0.1`).

Then run from the `gar-tools` repository root:

```bash
make -C targets/luckfox-rv1106/app-template
make -C targets/luckfox-rv1106/app-template deploy
```

The standalone `deploy` target copies the built binary to the configured
`LUCKFOX_DEPLOY_DIR` on the target. Normal GAR operation should use
`gar target build/deploy` instead.

For no-Ethernet operation, install the sample init scripts in `initd/` to bring up
usb0 and SSH automatically at boot.

For host-side USB NIC setup, use `scripts/host_usbnet_up.sh` (default host
address: `10.42.0.2/24`).
