# Luckfox RV1106 EC2 Runtime (Low-layer Substitution)

This runtime is designed for EC2 simulation where application code should stay
as close to real device execution as possible.

Goal:

- Replace hardware dependencies at the lowest practical layer.
- Keep application binary and high-level flow unchanged.
- Reuse existing Linux `/dev` simulation assets where possible.

Standard policy for this target:

- Do not use `LD_PRELOAD` for normal EC2 simulation flow.
- Prefer replacing `/dev/*` providers directly, same style as linux-device/RasPi flow.
- Keep one application source and one device-path contract for real + sim (zero-diff target).
- GAR primary path is system-level substitution using CUSE/gpio-sim, not HAL replacement.

## Layer strategy

### L0: Device node replacement (preferred)

Replace hardware via `/dev` providers first.

- GPIO/I2C/SPI: reuse `targets/linux-device/runtime` stubs.
- Camera path: target CUSE-based virtual video device at `/dev/video0`.
- Display path: provide framebuffer-compatible sink for `/dev/fb0` (or redirected file sink).

This layer gives the highest fidelity with least app change.

### L1: Vendor API shim (last resort)

When RKMedia/rkaiq binaries are unavailable on EC2, provide minimal symbol shim
libraries that keep control flow alive while returning deterministic states.

Use only for API availability testing, not quality/performance validation.

## Recommended stack on EC2

1. Build Linux runtime stubs from `targets/linux-device/runtime`.
2. Start devfs runtime launcher in this directory.
3. Run target app as-is (no preload shim).
4. Drive scenarios from web bridge and verify behavior.

## Minimal quick start

Build CUSE stubs:

make -C targets/linux-device/runtime/i2c-stub
make -C targets/linux-device/runtime/spi-stub

Start device-file runtime:

targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-devfs-start

Run app without source changes:

targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-run \
	/path/to/your/app/binary

Stop runtime:

targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-devfs-stop

## Node mapping for Luckfox on EC2

- I2C: expose `/dev/i2c-3` via CUSE (`cuse_i2c -f --devname=i2c-3`)
- SPI: expose `/dev/spidev0.0` via CUSE (`cuse_spi -f --devname=spidev0.0`)
- GPIO: use host gpio-sim or existing linux-device GPIO runtime path
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

targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-camera-start

Stop camera feed:

targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-camera-stop

Optional file-backed source:

GAR_CAMERA_SOURCE=/path/to/sample.mp4 \
targets/luckfox-rv1106/runtime/bin/gar-luckfox-ec2-camera-start

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
