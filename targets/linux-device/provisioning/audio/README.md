# Persisting a selected USB audio card's working state

The Product binds a stable ALSA card ID, expected USB VID/PID and the playback
level it has verified. `configure.py` saves only that card using standard
`alsactl store`, then tests restoration by temporarily setting playback to zero
and restoring the saved card state. Capture, AGC and microphone mute controls
are not deliberately changed. No recording or App restart is performed.

An exact VID/PID udev add rule invokes `alsactl restore` for that newly detected
control device. This covers USB hotplug and boot enumeration without depending
on a card number or the App's connection/retry loop. It reuses the standard
ALSA state file, so later user volume changes saved by alsa-restore.service are
respected. Existing state and any prior rule are backed up under root-only
`/var/lib/gar-alsa/`. No vendor udev rules are edited.

The Windows input form uses the same pinned-key, non-TTY SSH transport as the
Wi-Fi recipe. Linux sudo authentication is prompted in a masked field, sent
only after sudo asks, retained only in memory and excluded from result JSON.
No Wi-Fi key, cloud key or conversation text is read or saved. The shared
transport's `recipeSource` selects this nonsecret script; the legacy
`__GAR_WIFI_INPUT__`/`__GAR_WIFI_RESULT__` markers are its framing protocol.

`gar target audio --workspace Local/Product --json` invokes the Product's
`gar-target-audio.json` Python binding. This is OS configuration, not an App
artifact deployment. A passing save/restore test does not itself prove audible
speech or cold boot; verify physical replug and power-cycle behavior separately.
