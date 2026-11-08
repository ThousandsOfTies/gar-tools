"""Root-side Netplan Wi-Fi recipe. Input is private stdin; output is allowlisted.

The only credential copy is the root-only network configuration on the Target.
No application artifacts, cloud credentials or actuator controls are touched.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit


def command(args, timeout=30):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("command_failed:" + args[0])
    return result.stdout


def local_only(text, interface, address):
    """Keep the existing USB address, removing its gateway and DNS ownership."""
    if not re.search(r"^Name=" + re.escape(interface) + r"\s*$", text, re.M) or "Address=" + address not in text:
        raise ValueError("unexpected_usb_profile")
    result, section = [], ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped
        if section == "[Route]":
            continue
        if section == "[Network]" and re.match(r"(DNS|Domains|DNSDefaultRoute|Gateway)\s*=", stripped):
            continue
        result.append(line)
        if stripped == "[Network]":
            result.append("DNSDefaultRoute=no")
    return "\n".join(result).rstrip() + "\n"


def wifi_configuration(interface, ssid, password):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", interface):
        raise ValueError("invalid_interface")
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode("utf-8")) <= 32 or "\x00" in ssid:
        raise ValueError("invalid_ssid")
    if (
        not isinstance(password, str)
        or not (8 <= len(password.encode("utf-8")) <= 63 or re.fullmatch("[0-9a-fA-F]{64}", password))
        or "\x00" in password
    ):
        raise ValueError("invalid_wifi_password")
    return {
        "network": {
            "version": 2,
            "renderer": "networkd",
            "wifis": {
                interface: {
                    "dhcp4": True,
                    "dhcp6": False,
                    "optional": True,
                    "dhcp4-overrides": {"route-metric": 10},
                    "access-points": {ssid: {"password": password}},
                }
            },
        }
    }


def private_write(path, text, mode=0o600):
    temporary = path.with_name(path.name + ".gar-new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, mode)
        else:
            os.chmod(temporary, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def address(interface):
    links = json.loads(command(["ip", "-j", "-4", "addr", "show", "dev", interface], 5))
    return next((a["local"] for link in links for a in link.get("addr_info", []) if a.get("scope") == "global"), None)


def wait_address(interface):
    for _ in range(40):
        found = address(interface)
        if found:
            return found
        time.sleep(1)
    raise RuntimeError("wifi_association_or_dhcp_failed")


def internet(interface, url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid_check_endpoint")
    answer = command(["getent", "ahostsv4", parsed.hostname], 8).split()
    if not answer:
        raise RuntimeError("dns_check_failed")
    resolved = answer[0]
    route = json.loads(command(["ip", "-j", "route", "get", resolved], 5))
    if not route or route[0].get("dev") != interface:
        raise RuntimeError("wifi_is_not_default_route")
    status = command(
        [
            "curl",
            "--interface",
            interface,
            "--silent",
            "--show-error",
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
    ).strip()
    if not status.isdigit() or not 100 <= int(status) <= 599:
        raise RuntimeError("https_check_failed")
    return int(status)


def wait_internet(interface, url):
    failure = None
    for attempt in range(3):
        try:
            return internet(interface, url)
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            failure = error
            if attempt < 2:
                time.sleep(2)
    raise failure


def configure(settings):
    if os.geteuid() != 0:
        raise RuntimeError("root_required")
    for tool in ("netplan", "wpa_supplicant", "ip", "networkctl", "curl"):
        if not shutil.which(tool):
            raise RuntimeError("missing_dependency:" + tool)
    interface = settings["interface"]
    config = wifi_configuration(interface, settings["ssid"], settings["password"])
    if not (Path("/sys/class/net") / interface / "wireless").exists():
        raise RuntimeError("wifi_driver_not_ready")
    usb = Path(settings["usbNetworkFile"])
    if usb.parent != Path("/etc/systemd/network") or not usb.name.endswith(".network") or usb.is_symlink():
        raise ValueError("invalid_usb_profile")
    old_usb = usb.read_text(encoding="utf-8")
    usb_config = local_only(old_usb, settings["usbInterface"], settings["expectedUsbAddress"])
    target = Path("/etc/netplan/60-gar-wifi.yaml")
    if target.is_symlink():
        raise ValueError("invalid_wifi_profile")
    old_wifi = target.read_text(encoding="utf-8") if target.exists() else None
    # Rollback copies stay root-only on the Target, outside source/artifact trees.
    backup = Path("/var/lib/gar-wifi")
    backup.mkdir(mode=0o700, exist_ok=True)
    os.chmod(backup, 0o700)
    private_write(backup / "usb-network.before", old_usb)
    if old_wifi is not None:
        private_write(backup / "wifi.before", old_wifi)
    try:
        if shutil.which("rfkill"):
            command(["rfkill", "unblock", "wifi"], 5)
        private_write(target, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
        private_write(usb, usb_config, 0o644)
        command(["netplan", "generate"])
        command(["netplan", "apply"], 35)
        command(["networkctl", "reload"])
        command(["networkctl", "reconfigure", settings["usbInterface"]], 10)
        found = wait_address(interface)
        http = wait_internet(interface, settings["checkUrl"])
        # One real disconnect/reconnect; persistent files are retained unchanged.
        command(["ip", "link", "set", interface, "down"], 5)
        time.sleep(2)
        command(["ip", "link", "set", interface, "up"], 5)
        command(["networkctl", "reconfigure", interface], 10)
        found = wait_address(interface)
        http = wait_internet(interface, settings["checkUrl"])
        return {
            "ok": True,
            "state": "connected",
            "interface": interface,
            "address": found,
            "internet": {"httpsStatus": http, "via": interface},
            "reconnected": True,
            "usbManagementOnly": True,
        }
    except Exception:
        if old_wifi is None:
            target.unlink(missing_ok=True)
        else:
            private_write(target, old_wifi)
        private_write(usb, old_usb, 0o644)
        try:
            command(["netplan", "apply"], 35)
            command(["networkctl", "reload"])
            command(["networkctl", "reconfigure", settings["usbInterface"]], 10)
        except Exception:
            raise RuntimeError("setup_failed_rollback_needs_check") from None
        raise


def repair_existing(settings):
    if os.geteuid() != 0:
        raise RuntimeError("root_required")
    target = Path("/etc/netplan/60-gar-wifi.yaml")
    if not target.is_file() or target.is_symlink() or target.stat().st_uid != 0:
        raise RuntimeError("existing_wifi_profile_not_found")
    config = json.loads(target.read_text(encoding="utf-8"))
    if settings["interface"] not in config.get("network", {}).get("wifis", {}):
        raise RuntimeError("existing_wifi_profile_mismatch")
    os.chmod(target, 0o600)
    usb = Path(settings["usbNetworkFile"])
    if usb.parent != Path("/etc/systemd/network") or usb.is_symlink():
        raise ValueError("invalid_usb_profile")
    text = local_only(usb.read_text(encoding="utf-8"), settings["usbInterface"], settings["expectedUsbAddress"])
    private_write(usb, text, 0o644)
    command(["networkctl", "reload"])
    command(["networkctl", "reconfigure", settings["usbInterface"]], 10)
    if settings.get("cycleExisting"):
        command(["ip", "link", "set", settings["interface"], "down"], 5)
        time.sleep(2)
        command(["ip", "link", "set", settings["interface"], "up"], 5)
        command(["networkctl", "reconfigure", settings["interface"]], 10)
    found = wait_address(settings["interface"])
    http = wait_internet(settings["interface"], settings["checkUrl"])
    return {
        "ok": True,
        "state": "connected",
        "address": found,
        "interface": settings["interface"],
        "internet": {"httpsStatus": http, "via": settings["interface"]},
        "reconnected": bool(settings.get("cycleExisting")),
        "usbManagementOnly": True,
    }


if __name__ == "__main__":
    print("__GAR_WIFI_INPUT__", flush=True)
    try:
        settings = json.loads(sys.stdin.readline())
        result = repair_existing(settings) if settings.get("repairExisting") else configure(settings)
    except Exception as error:
        # Only our own fixed error codes may leave the Target; never exception data.
        message = str(error)
        result = {
            "ok": False,
            "state": "failed",
            "error": message if re.fullmatch(r"[a-z_]+(?::[a-z_]+)?", message) else "wifi_setup_failed",
        }
    print("__GAR_WIFI_RESULT__" + json.dumps(result), flush=True)
