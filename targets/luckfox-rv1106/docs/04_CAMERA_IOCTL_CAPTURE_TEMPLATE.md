# Camera IOCTL Capture Template (M0)

This template standardizes `/dev/video0` trace capture for CUSE camera design.

## Goal

- Capture real-device V4L2 ioctl sequence used by the app.
- Capture simulation-side sequence with the same app binary.
- Produce diff inputs for CUSE implementation scope.

## Required tools

- `strace`
- target app binary
- `runtime/bin/gar-luckfox-camera-ioctl-trace`

## A) Capture on real Luckfox

Run on real target:

GAR_TRACE_TAG=real \
GAR_TRACE_DEV=/dev/video0 \
GAR_TRACE_DURATION=20 \
targets/luckfox-rv1106/runtime/bin/gar-luckfox-camera-ioctl-trace \
  /path/to/app-binary --your --args

Result directory example:

- `/tmp/gar-camera-trace-real-YYYYmmdd-HHMMSS/`

## B) Capture on EC2 simulation

Start runtime first (devfs substitution), then run:

GAR_TRACE_TAG=sim \
GAR_TRACE_DEV=/dev/video0 \
GAR_TRACE_DURATION=20 \
targets/luckfox-rv1106/runtime/bin/gar-luckfox-camera-ioctl-trace \
  /path/to/app-binary --your --args

## C) Compare ioctl sets

Assume two output dirs:

- `REAL_DIR=/tmp/gar-camera-trace-real-...`
- `SIM_DIR=/tmp/gar-camera-trace-sim-...`

Compare frequency:

diff -u "$REAL_DIR/ioctl_counts.txt" "$SIM_DIR/ioctl_counts.txt" || true

Compare raw sequence (order-sensitive):

diff -u "$REAL_DIR/ioctl_sequence.txt" "$SIM_DIR/ioctl_sequence.txt" || true

## D) Feed into CUSE milestone M0

Use these as M0 outputs:

1. `ioctl_counts.txt` from real and sim
2. `ioctl_sequence.txt` from real and sim
3. `video0_lines.txt` for context around open/ioctl/mmap/poll

Document which ioctls are:

- required for startup
- required for streaming loop
- optional or negotiable
- unsupported in first implementation

## Notes

- Keep capture duration short (10-30s) to avoid huge traces.
- Use the same app binary and argument set on both sides.
- Do not change app code for this step.
