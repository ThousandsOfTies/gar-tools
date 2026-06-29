# RV1106 Feature Menu (for GAR)

This menu proposes practical but interesting features that fit RV1106 strengths
and the GAR zero-diff policy.

## Assumption

- Board: Luckfox Pico Plus/Pro/Max (RV1106)
- Camera: SC3336 (`/dev/video0`)
- Display: ILI9341 (`/dev/fb0` or SPI draw path)
- Input: KY-040 rotary encoder
- Simulation policy: device-layer substitution (CUSE/gpio-sim/v4l2loopback fallback)

## Recommended picks

### 1) Rotary ISP live tuning + instant stream reflection (Priority: S)

What is fun:

- Turn physical dial and immediately see brightness/contrast/fps changes on RTSP and local display.

Why RV1106-specific value is high:

- RV1106 camera + ISP + encoder path is integrated; end-to-end control latency is visible and meaningful.

Implementation shape:

1. KY-040 events -> menu state machine.
2. Menu action -> ISP parameter update (`librkaiq` path).
3. Overlay current parameter values on local display and stream metadata.

Simulation strategy:

- Input/display path simulated via gpio-sim + display sink.
- Camera controls validated as command flow; final image quality verified on real hardware.

### 2) Dual-stream mode with quality dial (Priority: S)

What is fun:

- One dial switches between low-latency preview and high-quality archive profile in real time.

Why RV1106-specific value is high:

- Hardware encode pipeline can expose practical bitrate/fps trade-offs on edge devices.

Implementation shape:

1. Profile A: low bitrate, low latency.
2. Profile B: higher bitrate, better detail.
3. Rotary press toggles profile; rotate adjusts target bitrate.

Simulation strategy:

- Verify state transitions and control API calls in EC2.
- Verify actual encode quality/latency on real board.

### 3) NPU-triggered smart capture gate (Priority: A)

What is fun:

- Run lightweight object/person detection and only boost stream/record when event is detected.

Why RV1106-specific value is high:

- Uses NPU where it matters: event gating and edge autonomy.

Implementation shape:

1. Low-rate inference loop (RKNN runtime).
2. Event -> temporary high-quality stream profile + on-screen marker.
3. Event timeout -> return to low-power profile.

Simulation strategy:

- Model inference can be stubbed for deterministic scenario tests.
- Real NPU performance and model accuracy must be validated on device.

### 4) Privacy mask dial mode (Priority: A)

What is fun:

- Dial moves/resizes mask zone to hide sensitive area while keeping stream active.

Why RV1106-specific value is high:

- Edge-side privacy processing before network output is operationally valuable.

Implementation shape:

1. Menu mode to edit ROI rectangle.
2. Apply blur/mosaic in pipeline.
3. Persist profile in config file.

### 5) Day/Night adaptive profile scene switch (Priority: B)

What is fun:

- Auto profile switch by luminance trend with manual override from encoder.

Why RV1106-specific value is high:

- Tightly coupled ISP controls and stream profiles make this visibly effective.

## Suggested first implementation set

If you want fast value with low risk, start with:

1. Feature 1 (Rotary ISP live tuning)
2. Feature 2 (Dual-stream quality dial)

Then add:

3. Feature 3 (NPU-triggered smart capture gate)

This sequence gives a visible demo early, then scales into RV1106/NPU uniqueness.

## Minimal acceptance criteria per feature

1. No app-layer sim-only branch in core logic.
2. Same app binary contract for real and EC2 simulation flow.
3. Dial action to visible output latency is measurable and logged.
4. Feature state is represented on both local UI and remote stream status.
