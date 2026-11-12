"""Masked Windows input and private serial transport for a Netplan Target recipe.

Never export a saved PC Wi-Fi key. Passwords are supplied by the owner, kept in
memory, sent only after console echo is disabled, and never included in argv,
result JSON, source artifacts or PC credential files.
"""

import base64
import json
import re
import shlex
import subprocess
import sys
import threading
import time
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import ttk

import serial
from serial.tools import list_ports


class Console:
    def __init__(self, settings):
        matches = [
            p
            for p in list_ports.comports()
            if p.device.upper() == settings["port"].upper() and p.vid == settings["vid"] and p.pid == settings["pid"]
        ]
        if len(matches) != 1 or not matches[0].serial_number:
            raise RuntimeError("USBコンソールの機器識別を確認できません。USB接続を確認してください。")
        self.machine_id = matches[0].serial_number.lower()
        self.link = serial.Serial(matches[0].device, 115200, timeout=0.15, write_timeout=8)
        self.data = b""
        self.logged_in = False
        self.echo_off = False

    def write(self, value):
        self.link.write(value.encode("utf-8"))
        self.link.flush()

    def expect(self, pattern, timeout=15):
        deadline = time.monotonic() + timeout
        pattern = re.compile(pattern, re.M)
        while time.monotonic() < deadline:
            match = pattern.search(self.data)
            if match:
                value = match.group(0)
                self.data = self.data[match.end() :]
                return value
            self.data = (self.data + self.link.read(4096))[-131072:]
        raise RuntimeError("実機からの応答待ちが時間切れになりました。")

    def line_marker(self, marker, timeout=15):
        return self.expect(b"^" + re.escape(marker.encode()) + b"\r?$", timeout)

    def login(self, user, password):
        if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user):
            raise RuntimeError("Linuxユーザー名が不正です。")
        self.link.reset_input_buffer()
        self.write("\r")
        prompt = self.expect(rb"^(?:[a-z0-9_.-]+ )?login: |^[^\r\n]*@[a-zA-Z0-9_.-]+:[^\r\n]*[#$] ", 8)
        if b"login:" in prompt:
            self.write(user + "\r")
            self.expect(rb"[Pp]assword: |\xe3\x83\x91\xe3\x82\xb9\xe3\x83\xaf\xe3\x83\xbc\xe3\x83\x89: ", 8)
            self.write(password + "\r")
            answer = self.expect(
                rb"Login incorrect|^(?:[a-z0-9_.-]+ )?login: |^[^\r\n]*@[a-zA-Z0-9_.-]+:[^\r\n]*[#$] ", 15
            )
            if b"login:" in answer or b"incorrect" in answer:
                raise RuntimeError("Linuxのログイン認証に失敗しました。パスワードを確認してください。")
            self.logged_in = True
        marker = "__GAR_WIFI_ECHO_OFF_" + uuid.uuid4().hex + "__"
        self.write("stty -echo; printf '\\n" + marker + "\\n'\r")
        self.line_marker(marker)
        self.echo_off = True
        # Match the Linux machine identity to the attached USB gadget identity.
        marker = "__GAR_WIFI_MACHINE_" + uuid.uuid4().hex + "__"
        self.write("printf '\\n" + marker + "'; cat /etc/machine-id\r")
        observed = self.expect(re.escape(marker.encode()) + rb"([a-fA-F0-9]{32})\r?\n")
        found = re.search(rb"([a-fA-F0-9]{32})\r?\n$", observed).group(1).decode().lower()
        if found != self.machine_id:
            raise RuntimeError("USB機器とLinux実機の識別が一致しません。")

    def apply(self, settings, linux_password, progress):
        directory = "/tmp/gar-wifi-" + uuid.uuid4().hex
        marker = "__GAR_WIFI_UPLOAD_" + uuid.uuid4().hex + "__"
        encoded = base64.b64encode(Path(__file__).with_name("configure.py").read_bytes()).decode()
        lines = "\n".join(encoded[i : i + 76] for i in range(0, len(encoded), 76))
        self.write(
            "umask 077; mkdir "
            + directory
            + "; cat > "
            + directory
            + "/source.b64 <<'GAR_WIFI_SOURCE'\n"
            + lines
            + "\nGAR_WIFI_SOURCE\nbase64 -d "
            + directory
            + "/source.b64 > "
            + directory
            + "/configure.py; printf '\\n"
            + marker
            + "\\n'\r"
        )
        self.line_marker(marker, 25)
        progress("実機の管理者認証を確認しています…")
        prompt = "__GAR_WIFI_SUDO_" + uuid.uuid4().hex + "__"
        done = "__GAR_WIFI_AUTH_" + uuid.uuid4().hex + "__"
        self.write("sudo -k -S -p '" + prompt + "' -v; printf '\\n" + done + ':%s\\n\' "$?"\r')
        answer = self.expect(re.escape(prompt.encode()) + b"|" + re.escape(done.encode()) + rb":[0-9]+\r?\n")
        if answer.startswith(prompt.encode()):
            self.write(linux_password + "\n")
            answer = self.expect(re.escape(prompt.encode()) + b"|" + re.escape(done.encode()) + rb":[0-9]+\r?\n")
            if answer.startswith(prompt.encode()):
                self.write("\x03")
                raise RuntimeError("Linuxの管理者認証に失敗しました。")
        if b":0" not in answer:
            raise RuntimeError("Linuxの管理者認証に失敗しました。")
        progress("Wi-Fiを設定し、外部接続と再接続を確認しています…")
        self.write("sudo -n python3 " + shlex.quote(directory + "/configure.py") + "\r")
        self.line_marker("__GAR_WIFI_INPUT__", 10)
        self.write(json.dumps(settings, ensure_ascii=True) + "\n")
        answer = self.expect(rb"^__GAR_WIFI_RESULT__[^\r\n]+\r?\n", 300)
        report = json.loads(answer.decode().split("__GAR_WIFI_RESULT__", 1)[1])
        self.write(
            "rm -f -- "
            + directory
            + "/source.b64 "
            + directory
            + "/configure.py; rmdir -- "
            + directory
            + "; sudo -k\r"
        )
        return report

    def close(self):
        if self.link.is_open:
            if self.echo_off:
                try:
                    self.write("\x03stty echo\r" + ("exit\r" if self.logged_in else ""))
                    time.sleep(0.15)
                except (OSError, serial.SerialException):
                    pass
            self.data = b""
            self.link.close()


def current_ssid():
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, errors="replace", timeout=8
        )
        found = re.search(r"^\s*SSID\s*:\s*(.+)$", result.stdout, re.M)
        return found.group(1).strip() if found else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def main(settings):
    ssh_console = None
    if settings.get("transport") == "ssh":
        from ssh_transport import SshConsole

        try:
            if settings.get("repairExisting"):
                from wifi_recovery import WifiRecovery

                ssh_console = WifiRecovery(settings)
            else:
                ssh_console = SshConsole(settings)
        except Exception as error:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "state": "failed",
                        "error": str(error) if type(error) is RuntimeError else "SSH管理経路を確認できませんでした。",
                    },
                    ensure_ascii=True,
                )
            )
            return 1
        if settings.get("check"):
            print(json.dumps({"ok": True, "state": "preflight", "preflight": ssh_console.preflight}, ensure_ascii=True))
            return 0
    root = tk.Tk()
    root.title(settings.get("title", "Linux device - Wi-Fi setup"))
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=20)
    frame.grid()
    ttk.Label(frame, text="ロボットのWi-Fi自動接続を設定します", font=("Meiryo UI", 12, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
    )
    ttk.Label(
        frame,
        text="パスワードは画面に表示せず、PCのファイル・ログには保存しません。\nWi-Fiの接続情報は、実機の管理者専用設定に保存します。",
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))
    values = {}
    fields_to_show = [
        ("ssid", "Wi-Fi名（SSID）", current_ssid(), False),
        ("password", "Wi-Fiのパスワード", "", True),
        ("linuxPassword", "実機Linuxのパスワード", "", True),
    ]
    if ssh_console and not ssh_console.needs_password:
        fields_to_show = [field for field in fields_to_show if field[0] != "linuxPassword"]
    if settings.get("repairExisting"):
        fields_to_show = [field for field in fields_to_show if field[0] == "linuxPassword"]
    for row, (name, label, default, masked) in enumerate(fields_to_show, 2):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
        values[name] = tk.StringVar(value=default)
        entry = ttk.Entry(frame, textvariable=values[name], show="●" if masked else "", width=34)
        entry.grid(row=row, column=1, sticky="ew", pady=5)
        if name == "password":
            entry.focus_set()
    status = tk.StringVar(
        value="Wi-Fi名とWi-Fiパスワードを入力してください。"
        if ssh_console and not ssh_console.needs_password
        else "Wi-Fi名を確認し、2つのパスワードを入力してください。"
    )
    if settings.get("repairExisting"):
        status.set("Wi-Fi設定は実機に保存されています。Linuxのパスワードだけ入力してください。")
    ttk.Label(frame, textvariable=status, wraplength=520).grid(row=5, column=0, columnspan=2, sticky="w", pady=14)
    report = {"ok": False, "state": "cancelled"}
    busy = False

    def update(text):
        root.after(0, lambda: status.set(text))

    def finish(result):
        nonlocal report, busy
        report = result
        if settings.get("resultDirectory"):
            safe = {
                key: result[key]
                for key in (
                    "ok",
                    "state",
                    "error",
                    "address",
                    "interface",
                    "internet",
                    "reconnected",
                    "usbManagementOnly",
                )
                if key in result
            }
            Path(settings["resultDirectory"], "wifi-setup-result.json").write_text(
                json.dumps(safe, ensure_ascii=True), encoding="utf-8"
            )
        busy = False
        button.config(state="normal")
        if result.get("ok"):
            status.set("接続できました。Wi-Fi経由の外部通信と再接続を確認しました。")
            root.after(1800, root.destroy)
        else:
            status.set("設定を完了できませんでした。" + result.get("error", "接続情報を確認して再試行してください。"))

    def submit():
        nonlocal busy
        fields = {name: value.get() for name, value in values.items()}
        fields.setdefault("ssid", "")
        fields.setdefault("password", "")
        fields.setdefault("linuxPassword", "")
        if (not settings.get("repairExisting") and (not fields["ssid"] or not fields["password"])) or (
            (not ssh_console or ssh_console.needs_password) and not fields["linuxPassword"]
        ):
            status.set("Wi-Fi名と2つのパスワードを入力してください。")
            return
        busy = True
        button.config(state="disabled")
        if "password" in values:
            values["password"].set("")
        if "linuxPassword" in values:
            values["linuxPassword"].set("")

        def work():
            console = None
            try:
                update("実機へSSH接続しています…" if ssh_console else "USBコンソールから実機へ接続しています…")
                console = ssh_console or Console(settings)
                console.login(settings["user"], fields["linuxPassword"])
                result = console.apply(
                    {**settings, "ssid": fields["ssid"], "password": fields["password"]},
                    fields["linuxPassword"],
                    update,
                )
            except Exception as error:
                # Our own fixed messages are safe. Never forward serial or subprocess output.
                message = str(error) if type(error) is RuntimeError else "USB接続か実機の状態を確認してください。"
                result = {"ok": False, "state": "failed", "error": message}
            finally:
                fields["password"] = ""
                fields["linuxPassword"] = ""
                if console:
                    console.close()
            root.after(0, lambda: finish(result))

        threading.Thread(target=work, daemon=True).start()

    button = ttk.Button(frame, text="Wi-Fiを設定する", command=submit)
    button.grid(row=6, column=1, sticky="e")

    def closing():
        if busy:
            status.set("実機の設定が終わるまで、この画面を開いたままお待ちください。")
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", closing)
    root.mainloop()
    print(json.dumps(report, ensure_ascii=True), flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(json.loads(sys.argv[1])))
    except (ValueError, KeyError, tk.TclError):
        print(json.dumps({"ok": False, "state": "failed", "error": "Wi-Fi setup screen could not start"}))
        raise SystemExit(1) from None
