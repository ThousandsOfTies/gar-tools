import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("wifi_ssh", Path(__file__).with_name("ssh_transport.py"))
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
REAL_POPEN = subprocess.Popen
PROVIDER = """
import json,sys
mode,prompt=sys.argv[1:]
if mode!='no-prompt':
 print(prompt,file=sys.stderr,end='',flush=True)
 password=sys.stdin.readline().rstrip('\\n')
 if mode=='repeat':
  print(prompt,file=sys.stderr,end='',flush=True)
  sys.stdin.read()
  raise SystemExit(1)
 if password!='private-linux-test':raise SystemExit(2)
print('__GAR_WIFI_INPUT__',flush=True)
config=json.loads(sys.stdin.readline())
if config['password']!='private-wifi-test':raise SystemExit(3)
print('__GAR_WIFI_RESULT__'+json.dumps({'ok':True,'state':'connected'}),flush=True)
"""


class PrivateTransportTests(unittest.TestCase):
    def apply(self, mode):
        console = driver.SshConsole.__new__(driver.SshConsole)
        console.settings = {}
        console.options = []
        console.endpoint = "test-only"
        console.needs_password = mode != "no-prompt"
        console.root_prefix = ["sudo", "-k", "-S"] if console.needs_password else []
        console.run = lambda *args, **kwargs: SimpleNamespace(returncode=0)

        def start(args, **kwargs):
            self.assertNotIn("private-linux-test", str(args))
            self.assertNotIn("private-wifi-test", str(args))
            found = re.search(r"__GAR_WIFI_AUTH_[a-f0-9]+__", args[-1])
            prompt = found.group(0) if found else "unused"
            return REAL_POPEN([sys.executable, "-c", PROVIDER, mode, prompt], **kwargs)

        with patch.object(driver.subprocess, "Popen", start):
            return console.apply({"password": "private-wifi-test"}, "private-linux-test", lambda _: None)

    def test_password_follows_sudo_prompt_then_configuration_follows_input_marker(self):
        self.assertTrue(self.apply("sudo")["ok"])

    def test_no_sudo_prompt_does_not_send_linux_password(self):
        self.assertTrue(self.apply("no-prompt")["ok"])

    def test_repeated_sudo_prompt_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "認証に失敗"):
            self.apply("repeat")


if __name__ == "__main__":
    unittest.main()
