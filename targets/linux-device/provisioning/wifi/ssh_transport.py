"""Existing-key setup route; no Linux password reset or saved Wi-Fi key export."""

import ctypes
import json
import os
import queue
import re
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path


class SshConsole:
    def __init__(self, settings):
        self.settings = settings
        self.options = [
            "-T",
            "-i",
            settings["sshKey"],
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=6",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UserKnownHostsFile=" + settings["knownHosts"],
        ]
        self.endpoint = settings["sshUser"] + "@" + settings["sshHost"]
        if self.run("id -u", timeout=9).returncode:
            if settings.get("check"):
                raise RuntimeError("USB管理経路が未接続です。診断ではPCの設定を変更しません。")
            self.prepare_usb()
        identity = self.run("id -u")
        if identity.returncode:
            raise RuntimeError("登録済みSSH鍵で実機に接続できませんでした。")
        if settings.get("check"):
            self.preflight = {}
            for label, command in [
                ("identity", "id"),
                ("sudo", "sudo -n -l"),
                ("dockerVersion", "docker info --format '{{.ServerVersion}}'"),
                ("images", "docker image ls --format '{{.Repository}} {{.ID}}'"),
                (
                    "networkTools",
                    "PATH=/usr/sbin:/sbin:/usr/bin:/bin; command -v netplan; command -v wpa_supplicant; command -v iw; command -v nmcli; ip -br link show wlan0",
                ),
                (
                    "networkDelegation",
                    "systemctl is-active NetworkManager.service wpa_supplicant.service systemd-networkd.service; stat -c '%A %U %G %n' /etc/netplan /etc/wpa_supplicant /run/wpa_supplicant 2>/dev/null; ls /etc/netplan; networkctl list --no-pager --no-legend",
                ),
            ]:
                try:
                    observed = self.run(command)
                    self.preflight[label] = {"exit": observed.returncode, "output": observed.stdout[:3000]}
                except subprocess.TimeoutExpired:
                    self.preflight[label] = {"exit": 1, "error": "timeout"}
            return
        self.needs_password = False
        if identity.stdout.strip() == "0":
            self.root_prefix = []
        elif self.run("sudo -n true").returncode == 0:
            self.root_prefix = ["sudo", "-n"]
        else:
            self.needs_password = True
            self.root_prefix = ["sudo", "-k", "-S"]

    def run(self, command, *, data=None, timeout=20):
        return subprocess.run(
            ["ssh", *self.options, self.endpoint, command],
            input=data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    def prepare_usb(self):
        # Elevation is solely for assigning the USB management IP. No ICS changes.
        directory = Path(self.settings["resultDirectory"])
        result = directory / ("wifi-usb-" + uuid.uuid4().hex + ".json")
        script = Path(__file__).with_name("prepare-usb.ps1")
        argv = [
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-InterfaceGuid",
            self.settings["usbGuid"],
            "-Address",
            self.settings["usbHostAddress"],
            "-ResultFile",
            str(result),
        ]
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "powershell.exe", subprocess.list2cmdline(argv), str(directory), 0
        )
        if rc <= 32:
            raise RuntimeError("Windowsの管理者確認が必要です。USB用の固定アドレス設定を許可してください。")
        for _ in range(90):
            if result.exists():
                try:
                    value = json.loads(result.read_text(encoding="utf-8-sig"))
                    if not value.get("ok"):
                        raise RuntimeError("PC側のUSB管理用アドレスを設定できませんでした。")
                    time.sleep(2)
                    return
                except json.JSONDecodeError:
                    pass
            time.sleep(1)
        raise RuntimeError("Windowsの管理者確認が完了しませんでした。")

    def login(self, user, password):
        pass

    def apply(self, settings, linux_password, progress):
        progress("既存のSSH鍵と管理権限でWi-Fiを設定しています…")
        directory = "/tmp/gar-wifi-" + uuid.uuid4().hex
        create = self.run(
            "umask 077; mkdir " + directory + "; cat > " + directory + "/configure.py",
            data=Path(__file__).with_name("configure.py").read_text(encoding="utf-8"),
        )
        if create.returncode:
            raise RuntimeError("Wi-Fi設定用の一時プログラムを準備できませんでした。")
        try:
            program = ["/usr/bin/python3", directory + "/configure.py"]
            prompt = "__GAR_WIFI_AUTH_" + uuid.uuid4().hex + "__"
            prefix = [*self.root_prefix, "-p", prompt] if self.needs_password else self.root_prefix
            command = shlex.join([*prefix, *program])
            process = subprocess.Popen(
                ["ssh", *self.options, self.endpoint, command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            messages = queue.Queue()

            def read(name, stream):
                while True:
                    try:
                        chunk = os.read(stream.fileno(), 4096)
                    except OSError:
                        return
                    messages.put((name, chunk))
                    if not chunk:
                        return

            for name, stream in [("out", process.stdout), ("err", process.stderr)]:
                threading.Thread(target=read, args=(name, stream), daemon=True).start()
            output = b""
            errors = b""
            auth_sent = False
            input_sent = False
            closed = set()
            try:
                deadline = time.monotonic() + 300
                while time.monotonic() < deadline:
                    try:
                        name, chunk = messages.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if not chunk:
                        closed.add(name)
                        if len(closed) == 2:
                            break
                        continue
                    if name == "err":
                        errors = (errors + chunk)[-16384:]
                        count = errors.count(prompt.encode())
                        if count > 1:
                            raise RuntimeError("Linuxの管理者認証に失敗しました。")
                        if count and not auth_sent:
                            process.stdin.write((linux_password + "\n").encode())
                            process.stdin.flush()
                            auth_sent = True
                            progress("管理者認証を確認しています…")
                    else:
                        output = (output + chunk)[-32768:]
                        if b"__GAR_WIFI_INPUT__" in output and not input_sent:
                            process.stdin.write((json.dumps(settings) + "\n").encode())
                            process.stdin.flush()
                            input_sent = True
                            progress("Wi-Fiの接続・外部通信・再接続を確認しています…")
                        match = re.search(rb"^__GAR_WIFI_RESULT__([^\r\n]+)\r?\n", output, re.M)
                        if match:
                            process.stdin.close()
                            process.wait(timeout=10)
                            return json.loads(match.group(1))
                raise RuntimeError("実機のWi-Fi設定結果を確認できませんでした。")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                for stream in (process.stdin, process.stdout, process.stderr):
                    if not stream.closed:
                        stream.close()
                output = b""
                errors = b""
        finally:
            self.run("rm -f -- " + directory + "/configure.py; rmdir -- " + directory)

    def close(self):
        pass
