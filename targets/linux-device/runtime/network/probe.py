"""Read-only Linux route/DNS/TLS observations; no credentials or config content."""

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


def run(args, timeout=10):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"exit": result.returncode, "output": result.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired):
        return {"exit": 1, "error": "unavailable_or_timeout"}


def probe(settings):
    interface = settings["interface"]
    url = settings["checkUrl"]
    parsed = urlsplit(url)
    if (
        not re.fullmatch(r"[a-zA-Z0-9_.-]{1,32}", interface)
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid network binding")
    report = {"ok": True, "interface": interface}
    report["addresses"] = run(["ip", "-j", "-4", "addr", "show", "dev", interface])
    report["defaultRoutes"] = run(["ip", "-j", "route", "show", "default"])
    report["dns"] = run(["getent", "ahostsv4", parsed.hostname], 8)
    report["https"] = run(
        [
            "curl",
            "--interface",
            interface,
            "--silent",
            "--output",
            "/dev/null",
            "--write-out",
            "%{http_code}",
            "--connect-timeout",
            "5",
            "--max-time",
            "12",
            url,
        ],
        15,
    )
    report["configuration"] = {"present": False}
    path = Path("/etc/netplan/60-gar-wifi.yaml")
    if path.exists():
        stat = path.stat()
        report["configuration"] = {
            "present": True,
            "mode": oct(stat.st_mode & 0o777),
            "uid": stat.st_uid,
            "regular": path.is_file() and not path.is_symlink(),
        }
    if settings.get("usbNetworkFile"):
        usb = Path(settings["usbNetworkFile"])
        if usb.parent == Path("/etc/systemd/network") and usb.is_file() and not usb.is_symlink():
            stat = usb.stat()
            report["usbConfiguration"] = {"mode": oct(stat.st_mode & 0o777), "uid": stat.st_uid}
    report["ok"] = (
        report["addresses"]["exit"] == 0
        and report["dns"]["exit"] == 0
        and report["https"]["exit"] == 0
        and report["https"]["output"].isdigit()
        and 100 <= int(report["https"]["output"]) <= 599
    )
    return report


if __name__ == "__main__":
    try:
        result = probe(json.loads(sys.argv[1]))
    except (KeyError, ValueError, TypeError):
        result = {"ok": False, "error": "invalid_network_settings"}
    print(json.dumps(result))
    sys.exit(0 if result["ok"] else 1)
