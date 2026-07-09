# Camera CUSE Roadmap (Primary Path)

This document defines the primary GAR path for camera simulation on EC2:
system-level substitution with a CUSE-backed virtual camera device.

## Objective

- Provide `/dev/video0` via userspace CUSE runtime.
- Keep application code unchanged between real Luckfox and EC2 simulation.
- Avoid HAL adapter branches in app layer.

## Milestone plan

### M0: Contract and observability

- Fix expected app contract for `/dev/video0` open/ioctl sequence.
- Capture required V4L2 ioctl set from real-device traces.
- Define explicit error behavior for unsupported ioctls.

Use template and helper script:

- `docs/04_CAMERA_IOCTL_CAPTURE_TEMPLATE.md`
- `runtime/bin/gar-luckfox-camera-ioctl-trace`

Done criteria:

1. Trace log of real sequence exists.
2. Required ioctl matrix is documented.

### M1: Minimal CUSE camera bring-up

- Implement CUSE node creation for `video0`.
- Support capability/format query ioctls used at startup.
- Return deterministic frame timing metadata.

Done criteria:

1. App opens `/dev/video0` without code changes.
2. Startup handshake passes to streaming setup stage.

### M2: Buffer lifecycle support

- Implement `VIDIOC_REQBUFS`, `VIDIOC_QUERYBUF`, `VIDIOC_QBUF`, `VIDIOC_DQBUF`.
- Provide stable ring buffer model with deterministic frame source.
- Validate basic mmap/read path used by target app.

Done criteria:

1. Continuous frame acquisition works on EC2.
2. No app-level simulation code is introduced.

### M3: Scenario-driven camera behavior

- Add controllable scene profiles (brightness change, noise, blur, motion).
- Integrate controls with web-bridge scenario injection.
- Emit timing and frame-drop metrics for regression checks.

Done criteria:

1. Scenario commands affect stream deterministically.
2. Metrics are exported and comparable across runs.

### M4: Compatibility hardening

- Expand ioctl compatibility for common V4L2 tools.
- Add failure-injection modes for reconnect/error handling tests.
- Integrate into GAR simulation startup scripts.

Done criteria:

1. Stable runs across repeated start/stop cycles.
2. Accepted as default camera simulation path.

## Transitional fallback policy

`v4l2loopback` is allowed only as a temporary bridge until M2 is completed.
It must not become the long-term architecture for this target.
