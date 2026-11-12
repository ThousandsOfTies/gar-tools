"""Save a selected USB card's ALSA state and restore it on enumeration.

No microphone recording, Linux password changes, network settings or App
deployment. The existing ALSA service continues to store user volume changes.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError("audio_command_failed")
    return result.stdout


def values(settings):
    card = settings["card"]
    usb = settings["usbId"]
    volume = settings["playbackPercent"]
    if not isinstance(card, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", card):
        raise ValueError("invalid_card")
    if not isinstance(usb, str) or not re.fullmatch(r"[a-f0-9]{4}:[a-f0-9]{4}", usb):
        raise ValueError("invalid_usb_identity")
    if isinstance(volume, bool) or not isinstance(volume, int) or not 1 <= volume <= 50:
        raise ValueError("invalid_volume")
    return card, usb, volume


def restore_rule(usb):
    vendor, product = usb.split(":")
    return "# Selected USB audio only; restore standard ALSA saved state.\n" + (
        'ACTION=="add", SUBSYSTEM=="sound", KERNEL=="controlC[0-9]*", '
        'ATTRS{idVendor}=="' + vendor + '", ATTRS{idProduct}=="' + product + '", '
        'RUN+="/usr/sbin/alsactl -E HOME=/run/alsa -E XDG_RUNTIME_DIR=/run/alsa/runtime restore $attr{device/number}"\n'
    )


def configure(settings):
    card, usb, volume = values(settings)
    if os.geteuid() != 0:
        raise RuntimeError("root_required")
    for tool in ("amixer", "alsactl", "udevadm"):
        if not shutil.which(tool):
            raise RuntimeError("missing_audio_dependency")
    matches = []
    for path in Path("/proc/asound").glob("card[0-9]*"):
        if (path / "id").read_text().strip() == card:
            if not (path / "usbid").is_file() or (path / "usbid").read_text().strip() != usb:
                raise RuntimeError("usb_audio_identity_mismatch")
            matches.append(path)
    if len(matches) != 1:
        raise RuntimeError("usb_audio_not_found")
    state = Path("/var/lib/alsa/asound.state")
    rule = Path("/etc/udev/rules.d/91-gar-usb-audio-state.rules")
    backup = Path("/var/lib/gar-alsa")
    backup.mkdir(mode=0o700, exist_ok=True)
    os.chmod(backup, 0o700)
    for source in (state, rule):
        if source.is_symlink():
            raise RuntimeError("unexpected_audio_config_link")
        if source.is_file():
            shutil.copyfile(source, backup / (source.name + ".before"))
            os.chmod(backup / (source.name + ".before"), 0o600)
    run(["amixer", "-c", card, "sset", "PCM", str(volume) + "%", "unmute"])
    # Capture/mute controls are retained exactly as they currently are.
    run(["alsactl", "store", card])
    if not state.is_file() or state.stat().st_size == 0:
        raise RuntimeError("audio_state_not_saved")
    rule.write_text(restore_rule(usb), encoding="utf-8")
    os.chmod(rule, 0o644)
    run(["udevadm", "control", "--reload-rules"])
    try:
        run(["amixer", "-c", card, "sset", "PCM", "0%"])
    finally:
        # Use the same restoration operation as boot and USB enumeration.
        run(["alsactl", "restore", card])
    mixer = run(["amixer", "-c", card, "sget", "PCM"])
    levels = re.findall(r"Playback\s+[0-9]+\s+\[([0-9]+)%\]", mixer)
    if not levels or any(int(value) != volume for value in levels):
        raise RuntimeError("audio_restore_verification_failed")
    return {
        "ok": True,
        "state": "saved",
        "card": card,
        "playbackPercent": volume,
        "saved": True,
        "restoreVerified": True,
        "hotplugRule": str(rule),
    }


if __name__ == "__main__":
    print("__GAR_WIFI_INPUT__", flush=True)  # Shared private SSH recipe protocol.
    try:
        result = configure(json.loads(sys.stdin.readline()))
    except Exception as error:
        message = str(error)
        result = {
            "ok": False,
            "state": "failed",
            "error": message if re.fullmatch("[a-z_]+", message) else "audio_setup_failed",
        }
    print("__GAR_WIFI_RESULT__" + json.dumps(result), flush=True)
