# Luckfox RV1106 Linux Simulation Runtime

This runtime is designed for a remote Linux simulation host where application
code should stay as close to real device execution as possible. EC2 Graviton is
the default host for this target, but the runtime contract is not EC2-specific.

Goal:

- Replace hardware dependencies at the lowest practical layer.
- Keep application binary and high-level flow unchanged.
- Reuse existing Linux `/dev` simulation assets where possible.

Standard policy for this target:

- Do not use `LD_PRELOAD` for normal EC2 simulation flow.
- Prefer replacing `/dev/*` providers directly, same style as linux-device/RasPi flow.
- Keep one application source and one device-path contract for real + sim (zero-diff target).
- GAR primary path is system-level substitution using CUSE/gpio-sim, not HAL replacement.
- The normal path is the GAR-generated systemd runtime. The launchers in
  `runtime/bin` are direct diagnostics for runtime development only.

## Layer strategy

### L0: Device node replacement (preferred)

Replace hardware via `/dev` providers first.

- GPIO: use an existing kernel-backed gpio-sim device at `/dev/gpiochip0`.
- SPI display: reuse the ILI9341 CUSE provider from
  `targets/linux-device/runtime/ili9341-stub`.
- I2C: disabled by default. The generic I2C stub does not model the SC3336
  camera sensor and must not be presented as its replacement.
- Camera path: target CUSE-based virtual video device at `/dev/video0`.
- Display path: provide framebuffer-compatible sink for `/dev/fb0` (or redirected file sink).

This layer gives the highest fidelity with least app change.

### L1: Vendor API shim (last resort)

When RKMedia/rkaiq binaries are unavailable on EC2, provide minimal symbol shim
libraries that keep control flow alive while returning deterministic states.

Use only for API availability testing, not quality/performance validation.

## Normal GAR flow

Run these commands from the `GaplessAgentRuntime` root after `gar setup`:

```bash
scripts/gar sim host start
scripts/gar sim runtime build
scripts/gar sim runtime deploy
scripts/gar sim runtime start
scripts/gar sim app build
scripts/gar sim app deploy
scripts/gar sim runtime diag --json
```

GAR chooses the build architecture, transports immutable artifacts, starts the
device providers and bridge, and records the selected workspace. The target app
runs without an `LD_PRELOAD` simulation branch.

## Direct launcher diagnostics

The commands below bypass GAR orchestration. Use them only while developing the
Luckfox runtime itself, from the `gar-tools` repository root.

Build the SPI display provider used by the direct launcher:

```bash
make -C targets/linux-device/runtime/ili9341-stub
```

The direct launcher expects gpio-sim to have already created `/dev/gpiochip0`;
it does not create the GPIO device. I2C simulation is intentionally off because
the generic provider does not emulate SC3336 behavior. To run an explicit
generic-I2C experiment, build `targets/linux-device/runtime/i2c-stub` and start
the launcher with `GAR_LUCKFOX_ENABLE_I2C_SIM=1`.

Start device-file runtime:

```bash
targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-devfs-start
```

Run app without source changes:

```bash
targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-run \
  path/to/application-binary
```

Stop runtime:

```bash
targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-devfs-stop
```

## Node mapping on the simulation host

- GPIO: use the existing gpio-sim device at `/dev/gpiochip0`.
- SPI: expose `/dev/spidev0.0` with the ILI9341 CUSE provider
  (`cuse_spi_ili9341 -f --devname=spidev0.0`).
- I2C: leave disabled by default. `GAR_LUCKFOX_ENABLE_I2C_SIM=1` exposes the
  generic `/dev/i2c-3` provider for explicit experiments only; it is not an
  SC3336 model.
- Camera: CUSE virtual camera for `/dev/video0` is the target architecture
- FB: optional and environment-specific (`/dev/fb0`)

## Camera simulation note

Implementing V4L2 camera behavior through CUSE is technically possible but
high-cost and fragile because camera apps rely on many ioctls and buffer models
(`mmap`, `VIDIOC_REQBUFS`, `VIDIOC_QBUF`, `VIDIOC_DQBUF`, etc.).

Current status:

- Long-term primary: CUSE-backed camera simulation.
- Transitional fallback: `v4l2loopback` + ffmpeg feeder.

The fallback exists to keep delivery speed while CUSE camera coverage is being
built for key V4L2 ioctl paths.

Start camera feed:

```bash
targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-camera-start
```

Stop camera feed:

```bash
targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-camera-stop
```

Optional file-backed source:

```bash
GAR_CAMERA_SOURCE=path/to/sample.mp4 \
targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-camera-start
```

See `docs/03_CAMERA_CUSE_ROADMAP.md` for CUSE camera milestones.

## What this validates

- App startup and lifecycle behavior.
- GPIO menu interaction and parameter state transitions.
- I/O error handling and reconnect logic.
- RTSP server control flow (session start/stop/status).

## What must stay on real Luckfox hardware

- RKMedia + MPP encoder quality/latency.
- ISP tuning and image quality via rkaiq.
- CSI camera timings and sensor-specific edge cases.
- SPI LCD draw bandwidth and visible UX smoothness.

## Acceptance criteria for low-layer simulation

1. App binary runs on EC2 without source-level simulation ifdefs.
2. Hardware-facing file paths remain unchanged in app code.
3. Scenario injection changes app state deterministically.
4. Unsupported hardware ioctls fail with explicit logs, not silent success.
