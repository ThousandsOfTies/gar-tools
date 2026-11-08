"""Linux ALSA observations and explicit speaker tests; never records user audio.

Bindings are supplied by a Product adapter. This script does not access cloud
credentials, change services, move actuators, or save captured microphone data.
"""

import array
import json
import math
import re
import subprocess
import sys


def run(args, *, data=None, timeout=8):
    try:
        result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
        return {
            "exit": result.returncode,
            "output": result.stdout.decode("utf-8", "replace").strip(),
            "error": result.stderr.decode("utf-8", "replace").strip(),
        }
    except (OSError, subprocess.TimeoutExpired):
        return {"exit": 1, "error": "Command unavailable or timed out"}


def sanitize(value):
    value = re.sub(r"https?://[^\s]+", "[URL]", value)
    return re.sub(
        r"(?i)(token|api[_-]?key|authorization|secret)\s*[:=]\s*\S+",
        r"\1=[redacted]",
        value,
    )


def probe(settings):
    card, service, action = settings["card"], settings["service"], settings["action"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", card) or not re.fullmatch(
        r"[A-Za-z0-9_.@-]{1,128}\.service", service
    ):
        raise ValueError("Invalid card or service binding")
    if action not in ["status", "audio-status", "speaker-test", "restore-speaker"]:
        raise ValueError("Unknown probe")
    report = {"ok": True, "action": action, "card": card}
    if action == "restore-speaker":
        volume = settings["volume"]
        if (
            not isinstance(volume, int)
            or isinstance(volume, bool)
            or not 1 <= volume <= 50
        ):
            raise ValueError("Speaker restoration is limited to 1..50 percent")
        report["restore"] = run(
            ["amixer", "-c", card, "sset", "PCM", str(volume) + "%", "unmute"]
        )
        report["ok"] = report["restore"]["exit"] == 0
    if action == "speaker-test":
        # Quiet 0.4 s, 660 Hz cue with 20 ms fades. No microphone access.
        pcm = array.array(
            "h",
            (
                round(
                    3276
                    * min(1, i / 960, (19199 - i) / 960)
                    * math.sin(2 * math.pi * 660 * i / 48000)
                )
                for i in range(19200)
            ),
        )
        if sys.byteorder != "little":
            pcm.byteswap()
        report["tone"] = run(
            [
                "aplay",
                "-q",
                "-D",
                "plughw:CARD=" + card + ",DEV=0",
                "-t",
                "raw",
                "-f",
                "S16_LE",
                "-r",
                "48000",
                "-c",
                "1",
            ],
            data=pcm.tobytes(),
        )
        report["ok"] = report["tone"]["exit"] == 0
    report["mixer"] = run(["amixer", "-c", card, "scontents"])
    report["capture"] = run(["arecord", "-l"])
    report["processes"] = run(
        ["pgrep", "-a", "-f", r"^(/usr/bin/)?(arecord|aplay)( |$)"]
    )
    report["service"] = run(
        [
            "systemctl",
            "show",
            service,
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "MainPID",
            "-p",
            "NRestarts",
            "-p",
            "UnitFileState",
        ]
    )
    report["ok"] = (
        report["ok"]
        and report["mixer"]["exit"] == 0
        and report["capture"]["exit"] == 0
        and report["service"]["exit"] == 0
    )
    journal = run(
        ["journalctl", "-u", service, "-n", "60", "--no-pager", "-o", "short-iso"]
    )
    report["events"] = [
        sanitize(line)
        for line in journal.get("output", "").splitlines()
        if re.search(r"Live audio|error|failed|ALSA|denied", line, re.I)
    ]
    return report


if __name__ == "__main__":
    try:
        result = probe(json.loads(sys.argv[1]))
    except (KeyError, ValueError, TypeError, IndexError):
        result = {"ok": False, "error": "Invalid audio probe settings"}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)
