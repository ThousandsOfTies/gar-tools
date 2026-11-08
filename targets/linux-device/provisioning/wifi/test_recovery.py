import importlib.util
import unittest
from pathlib import Path

import paramiko

spec = importlib.util.spec_from_file_location("wifi_recovery", Path(__file__).with_name("wifi_recovery.py"))
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class RecoveryTests(unittest.TestCase):
    def test_recovery_requires_same_previously_pinned_host_key(self):
        pinned = paramiko.RSAKey.generate(1024)
        other = paramiko.RSAKey.generate(1024)
        recovery = driver.WifiRecovery.__new__(driver.WifiRecovery)
        recovery.keys = {pinned.get_name(): pinned}
        recovery.verify(pinned)
        with self.assertRaisesRegex(RuntimeError, "一致しません"):
            recovery.verify(other)


if __name__ == "__main__":
    unittest.main()
