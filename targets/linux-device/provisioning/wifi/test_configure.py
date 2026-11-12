import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("wifi_recipe", Path(__file__).with_name("configure.py"))
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


class WifiTests(unittest.TestCase):
    def test_public_networkd_profile_gets_exact_readable_mode_even_with_private_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(recipe.os, "fchmod", create=True) as chmod:
                recipe.private_write(Path(directory) / "usb.network", "[Match]\nName=usb0\n", 0o644)
                self.assertEqual(chmod.call_args.args[1], 0o644)

    @patch.object(recipe, "time")
    @patch.object(recipe, "internet", side_effect=[RuntimeError("dns_check_failed"), 404])
    def test_waits_for_transient_reconnection_without_treating_http_404_as_api_auth(self, internet, clock):
        self.assertEqual(recipe.wait_internet("wlan0", "https://example.com/"), 404)
        self.assertEqual(internet.call_count, 2)
        clock.sleep.assert_called_once_with(2)

    def test_usb_address_retained_without_gateway_or_dns(self):
        original = "[Match]\nName=usb0\n[Link]\nRequiredForOnline=no\n[Network]\nAddress=192.0.2.2/24\nDNS=192.0.2.1\nDomains=~.\nDNSDefaultRoute=yes\n[Route]\nGateway=192.0.2.1\nMetric=20\n"
        result = recipe.local_only(original, "usb0", "192.0.2.2/24")
        self.assertIn("Address=192.0.2.2/24", result)
        self.assertIn("RequiredForOnline=no", result)
        self.assertIn("DNSDefaultRoute=no", result)
        self.assertNotIn("Gateway=", result)
        self.assertNotIn("DNS=", result)
        self.assertNotIn("Domains=", result)
        self.assertEqual(result, recipe.local_only(result, "usb0", "192.0.2.2/24"))

    def test_foreign_usb_profile_rejected(self):
        with self.assertRaises(ValueError):
            recipe.local_only("[Match]\nName=eth0\n[Network]\nAddress=192.0.2.2/24\n", "usb0", "192.0.2.2/24")

    def test_credentials_are_data_and_survive_quoting(self):
        result = recipe.wifi_configuration("wlan0", '日本語 "Wi-Fi"', "ab'c\"$()xyz")
        decoded = json.loads(json.dumps(result, ensure_ascii=False))
        self.assertIn('日本語 "Wi-Fi"', decoded["network"]["wifis"]["wlan0"]["access-points"])
        self.assertEqual(decoded["network"]["wifis"]["wlan0"]["dhcp4-overrides"]["route-metric"], 10)

    def test_invalid_credentials_rejected(self):
        for interface, ssid, password in [
            ("wlan0;reboot", "home", "password123"),
            ("wlan0", "x" * 33, "password123"),
            ("wlan0", "home", "short"),
            ("wlan0", "home", "p" * 64),
        ]:
            with self.assertRaises(ValueError):
                recipe.wifi_configuration(interface, ssid, password)

    def test_private_atomic_replace_and_stale_temporary_does_not_clobber(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "network.yaml"
            recipe.private_write(target, "before")
            recipe.private_write(target, "after")
            self.assertEqual(target.read_text(), "after")
            (Path(directory) / "network.yaml.gar-new").write_text("other")
            with self.assertRaises(FileExistsError):
                recipe.private_write(target, "unexpected")
            self.assertEqual(target.read_text(), "after")


if __name__ == "__main__":
    unittest.main()
