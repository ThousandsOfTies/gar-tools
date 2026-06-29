# Rotary ISP + Local Mini UI + RasPi View

This guide defines a practical first implementation that satisfies:

1. Local quick status/menu on the board display.
2. Live stream view on a Raspberry Pi over Ethernet.
3. Zero-diff app policy (same app behavior and device path contract).

## Scope

- Input: KY-040 rotary encoder
- ISP control: brightness/contrast/saturation/sharpness/exposure compensation
- Local display: compact menu + current values
- Network output: H.264 stream to Raspberry Pi

## Control model

Menu pages:

1. `BRIGHTNESS`
2. `CONTRAST`
3. `SATURATION`
4. `SHARPNESS`
5. `EXPOSURE_COMP`
6. `FPS`
7. `BITRATE`

Encoder actions:

- Rotate: increment/decrement current value
- Short press: next menu item
- Long press: toggle edit mode / lock mode

## Data flow

1. Encoder event -> control state machine
2. State machine -> ISP update (rkaiq API call)
3. State machine -> stream profile update (fps/bitrate)
4. State machine -> local mini UI refresh
5. Stream output -> Raspberry Pi viewer

## Raspberry Pi viewing path

Recommended first path:

1. Raspberry Pi runs RTSP server (MediaMTX).
2. Luckfox pushes H.264 stream to Pi RTSP URL.
3. Raspberry Pi opens local preview window (GStreamer).

This avoids opening inbound ports on Luckfox and is simple to operate.

## Runtime split

- Luckfox side:
  - app core (camera + encoder + control)
  - local mini UI renderer
  - RTSP push client
- Raspberry Pi side:
  - RTSP server (mediamtx)
  - viewer script

## Latency target (initial)

- Dial action to local UI update: under 100 ms
- Dial action to Raspberry Pi stream-visible change: under 500 ms

## Bring-up checklist

1. Verify local display update loop without camera.
2. Verify encoder event parsing with synthetic input.
3. Verify ISP update API roundtrip with log confirmation.
4. Verify RTSP push to Raspberry Pi.
5. Verify end-to-end latency logging.

## Scripts in this target

- `scripts/luckfox_push_rtsp.sh`: Luckfox side stream push helper.
- `scripts/raspi_run_mediatx.sh`: Raspberry Pi side RTSP server helper.
- `scripts/raspi_view_rtsp.sh`: Raspberry Pi side viewer helper.

## Notes

- Real image quality validation must still be done on actual Luckfox hardware.
- For EC2 simulation, keep the same app control flow and substitute only device providers.
