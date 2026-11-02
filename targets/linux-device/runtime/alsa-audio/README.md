# ALSA audio adapter

`audio.cjs` provides Linux PCM inventory, explicit ALSA device validation, bounded
WAV validation, and `arecord` / `aplay` argument construction. It owns no Product
configuration, microphone polling, speech synthesis, recognition or networking.

The caller injects a `job(command, args, {timeoutMs})` runner returning
`{promise, cancel()}`. That runner must use argument arrays without a shell,
enforce the timeout, and wait for child termination on cancellation.

Use `devices()` to inspect `/proc/asound`. `usb` is the kernel's USB vendor/product
identity when present. Endpoints include playback/capture and stable card-name
selectors such as `plughw:CARD=Device,DEV=0`. Select explicitly; this module never
falls back to HDMI or the OS default. Identical devices may need additional ALSA
configuration because card names can be suffixed.

Capture is mono signed 16-bit PCM, 16 kHz, 1–15 seconds. `plughw` allows ALSA to
convert a supported hardware format. The caller owns private temporary files,
publication/cleanup, recording consent, and microphone/playback sequencing.
Playback is limited to 30 seconds by the runner. Call `checkWave` before replay.
USB hotplug can race enumeration or a command; report failures and enumerate
again rather than silently switching devices.

Independent tests (no ALSA device required):

```sh
node --test targets/linux-device/runtime/alsa-audio/audio.test.cjs
```
