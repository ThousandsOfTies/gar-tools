"""Use the previously pinned Target host key for password-based LAN recovery."""

import hmac
import json
import re
import shlex
import socket
import time
import uuid
from pathlib import Path

import paramiko


class WifiRecovery:
    needs_password = True

    def __init__(self, settings):
        self.settings = settings
        self.keys = paramiko.HostKeys(settings["knownHosts"]).lookup(settings["sshHost"])
        if not self.keys:
            raise RuntimeError("登録済みの実機ホスト鍵が見つかりません。")
        with socket.create_connection((settings["wifiHost"], 22), timeout=8) as connection:
            transport = paramiko.Transport(connection)
            try:
                transport.start_client(timeout=8)
                self.verify(transport.get_remote_server_key())
            finally:
                transport.close()
        self.client = None
        self.preflight = {"knownHostKeyMatches": True, "address": settings["wifiHost"]}

    def verify(self, key):
        known = self.keys.get(key.get_name())
        if known is None or not hmac.compare_digest(known.asbytes(), key.asbytes()):
            raise RuntimeError("Wi-Fi側のホスト鍵が登録済み実機と一致しません。")

    def login(self, user, password):
        owner = self

        class PinnedKey(paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, client, hostname, key):
                owner.verify(key)

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(PinnedKey())
        self.client.connect(
            self.settings["wifiHost"],
            username=user,
            password=password,
            allow_agent=False,
            look_for_keys=False,
            timeout=8,
            auth_timeout=12,
            banner_timeout=8,
        )

    def apply(self, settings, linux_password, progress):
        directory = "/tmp/gar-wifi-" + uuid.uuid4().hex
        sftp = self.client.open_sftp()
        sftp.mkdir(directory, 0o700)
        try:
            with sftp.open(directory + "/configure.py", "w") as target:
                target.write(Path(__file__).with_name("configure.py").read_text(encoding="utf-8"))
            sftp.chmod(directory + "/configure.py", 0o600)
            prompt = "__GAR_WIFI_AUTH_" + uuid.uuid4().hex + "__"
            channel = self.client.get_transport().open_session()
            channel.exec_command(
                shlex.join(["sudo", "-k", "-S", "-p", prompt, "/usr/bin/python3", directory + "/configure.py"])
            )
            output = b""
            errors = b""
            auth_sent = False
            input_sent = False
            deadline = time.monotonic() + 150
            progress("登録済みホスト鍵で実機を確認しました。USB管理経路を復旧しています…")
            try:
                while time.monotonic() < deadline:
                    if channel.recv_stderr_ready():
                        errors = (errors + channel.recv_stderr(4096))[-16384:]
                        count = errors.count(prompt.encode())
                        if count > 1:
                            raise RuntimeError("Linuxの管理者認証に失敗しました。")
                        if count and not auth_sent:
                            channel.sendall((linux_password + "\n").encode())
                            auth_sent = True
                    if channel.recv_ready():
                        output = (output + channel.recv(4096))[-32768:]
                        if b"__GAR_WIFI_INPUT__" in output and not input_sent:
                            channel.sendall((json.dumps(settings) + "\n").encode())
                            input_sent = True
                        result = re.search(rb"^__GAR_WIFI_RESULT__([^\r\n]+)\r?\n", output, re.M)
                        if result:
                            report = json.loads(result.group(1))
                            if not report.get("ok"):
                                return report
                            # Finish the radio reconnect check over the restored USB
                            # connection, so cycling Wi-Fi cannot drop this check.
                            from ssh_transport import SshConsole

                            usb = SshConsole({**settings, "check": False})
                            return usb.apply({**settings, "cycleExisting": True}, linux_password, progress)
                    if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                        break
                    time.sleep(0.05)
                raise RuntimeError("管理接続の復旧結果を確認できませんでした。")
            finally:
                channel.close()
        finally:
            try:
                sftp.remove(directory + "/configure.py")
                sftp.rmdir(directory)
            finally:
                sftp.close()

    def close(self):
        if self.client:
            self.client.close()
