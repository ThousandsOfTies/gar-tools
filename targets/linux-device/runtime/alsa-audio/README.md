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
node --test targets/linux-device/runtime/alsa-audio/duplex.test.cjs
```

`duplex.cjs` provides continuous raw PCM via `AlsaDuplex`: `start()` captures
16 kHz mono S16_LE in aligned 100 ms `input` events, while `playPcm(bytes)` streams
24 kHz mono S16_LE to aplay. Call `endTurn()` on generation completion; `playback`
stays true until the aplay process drains and exits. `stopPlayback()` drops the
old queue and terminates playback before a later turn starts. `close()` stops
both children, escalating TERM to KILL if necessary. Queues are bounded to 60
seconds of raw output. `failure` reports unplug/process errors. No shell,
temporary audio file, default-device fallback, cloud transport, VAD or automatic
recording is implemented here. The caller explicitly starts capture and owns
echo policy, mute, provider credentials and session lifetime.

`probe.py` provides bounded Linux observations for a Product's GAR Target probe
adapter. Pass a JSON object with `action`, stable ALSA `card` ID and systemd
`service` binding. `status` / `audio-status` only inspect mixer, endpoints,
capture processes, service and sanitized Live error/status log lines. They do
not record audio or measure microphone signal levels. A successful process or
mixer observation does not prove audible output or intelligible input.

Explicit `speaker-test` plays a quiet 0.4-second 660 Hz tone; `restore-speaker`
sets PCM playback to the supplied `volume` (limited to 1..50 percent) and
unmutes it. These actions do not stop/restart services or persist mixer state.
Neither a reported ALSA 0% nor successful aplay alone establishes that a speaker
is silent; some USB device controls do not reflect its actual audible gain.
