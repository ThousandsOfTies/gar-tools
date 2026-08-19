# Luckfox RV1106 Target Tools

This target scaffold is for Luckfox Pico Plus/Pro/Max boards based on RV1106
running Buildroot Linux.

Setup guides:

- `docs/00_FIRST_BOOT_USB_SERIAL.md`: first-boot checklist and copy-paste command flow.
- `docs/01_PERSISTENT_USB_SSH.md`: persistent usb0 + SSH boot configuration examples.
- `docs/03_CAMERA_CUSE_ROADMAP.md`: camera CUSE-first implementation milestones.
- `docs/04_CAMERA_IOCTL_CAPTURE_TEMPLATE.md`: M0 ioctl capture and diff template for `/dev/video0`.
- `runtime/README.md`: remote Linux low-layer substitution and launcher usage.

Target hardware surfaces:

- Camera capture from SC3336 (`/dev/video0`) with Rockchip media pipeline.
- H.264 encoding via hardware encoder (RKMedia / MPP).
- Display output through framebuffer or SPI.
- GPIO input suitable for external controls.

Simulation policy:

- EC2 Graviton over `ssh_remote` is the default simulation model (aligned with Linux/RasPi-compatible target workflow).
- For Linux `/dev` surface simulation on EC2, use device-file substitution (CUSE/gpio-sim) with runtime assets under `targets/linux-device/runtime`.
- Standard Luckfox EC2 flow uses the GAR-generated systemd runtime. The scripts
  under `runtime/bin/` are direct diagnostics for runtime development, not the
  normal orchestration path.
- GAR primary simulation strategy is AI-driven system substitution with CUSE/gpio-sim, not HAL replacement.
- Camera simulation target is CUSE-based `/dev/video0`; `v4l2loopback` remains transitional fallback.
- Hardware-specific camera ISP/encoder behavior (RKMedia/MPP/rkaiq) must be validated on real Luckfox hardware.
- Product behavior and UI/control policy stay in the selected Product workspace.

## Directory map

- `toolchain/`: CMake toolchain template for Buildroot SDK.
- `scripts/`: direct SSH/USB-network helpers for target bring-up and diagnostics.

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

The selected Product workspace owns application source, build hooks, UI,
protocols, scenarios, and its hardware assignments. `gar-tools` provides only
the reusable target definition, toolchain, provisioning/bring-up helpers, and
low-layer runtime providers.

For no-Ethernet operation, install the sample init scripts in `initd/` to bring up
usb0 and SSH automatically at boot.

For host-side USB NIC setup, use `scripts/host_usbnet_up.sh` (default host
address: `10.42.0.2/24`).
