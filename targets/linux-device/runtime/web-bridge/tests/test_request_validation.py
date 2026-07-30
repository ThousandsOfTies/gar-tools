from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


WEB_BRIDGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_BRIDGE_DIR))

from request_validation import (  # noqa: E402
    RequestValidationError,
    boolean_value,
    bounded_int,
    browser_request_allowed,
    parse_json_object,
    resolve_panel_file,
    rfid_uid,
)


class RequestValidationTests(unittest.TestCase):
    def test_boolean_value_does_not_treat_string_zero_as_true(self) -> None:
        self.assertFalse(boolean_value({"value": "0"}, "value"))
        self.assertTrue(boolean_value({"value": "true"}, "value"))

    def test_bounded_int_rejects_boolean_and_out_of_range_values(self) -> None:
        with self.assertRaises(RequestValidationError):
            bounded_int({"value": True}, "value", minimum=0, maximum=10)
        with self.assertRaises(RequestValidationError):
            bounded_int({"value": 11}, "value", minimum=0, maximum=10)

    def test_bounded_int_rejects_fractional_json_numbers(self) -> None:
        with self.assertRaises(RequestValidationError):
            bounded_int({"value": 1.5}, "value", minimum=0, maximum=10)

        self.assertEqual(
            7,
            bounded_int({"value": " 7 "}, "value", minimum=0, maximum=10),
        )

    def test_bounded_int_normalises_excessively_large_strings(self) -> None:
        with self.assertRaisesRegex(RequestValidationError, "must be an integer"):
            bounded_int(
                {"value": "9" * 10_000},
                "value",
                minimum=0,
                maximum=10,
            )

    def test_json_parser_requires_a_valid_object(self) -> None:
        self.assertEqual({"value": 1}, parse_json_object('{"value": 1}'))
        with self.assertRaisesRegex(RequestValidationError, "valid JSON"):
            parse_json_object("{")
        with self.assertRaisesRegex(RequestValidationError, "JSON object"):
            parse_json_object("[]")

    def test_rfid_uid_is_normalised_and_bounded(self) -> None:
        self.assertEqual(
            rfid_uid({"uid": "04:ab:cd:ef"}, "00:00:00:00"),
            "04:AB:CD:EF",
        )
        with self.assertRaises(RequestValidationError):
            rfid_uid({"uid": "../../etc/passwd"}, "00:00:00:00")

    def test_panel_path_cannot_escape_static_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "panel"
            root.mkdir()
            index = root / "index.html"
            index.write_text("panel", encoding="utf-8")
            outside = root.parent / "secret.txt"
            outside.write_text("secret", encoding="utf-8")

            self.assertEqual(resolve_panel_file(root, ""), index)
            self.assertIsNone(resolve_panel_file(root, "../secret.txt"))
            self.assertIsNone(resolve_panel_file(root, "/does-not-exist"))

    def test_browser_access_requires_an_allowed_host_and_same_origin(self) -> None:
        allowed_hosts = frozenset({"127.0.0.1", "localhost"})

        self.assertTrue(browser_request_allowed("127.0.0.1:8080", None, allowed_hosts))
        self.assertTrue(
            browser_request_allowed(
                "localhost:8080",
                "http://localhost:8080",
                allowed_hosts,
            )
        )
        self.assertFalse(
            browser_request_allowed(
                "127.0.0.1:8080",
                "https://malicious.example",
                allowed_hosts,
            )
        )
        self.assertFalse(
            browser_request_allowed("malicious.example", None, allowed_hosts)
        )
        self.assertFalse(
            browser_request_allowed("localhost:not-a-port", None, allowed_hosts)
        )
        self.assertFalse(
            browser_request_allowed(
                "localhost:8080",
                "http://localhost:8080/unexpected-path",
                allowed_hosts,
            )
        )
        self.assertFalse(
            browser_request_allowed(
                "localhost:8080",
                "http://user@localhost:8080",
                allowed_hosts,
            )
        )


if __name__ == "__main__":
    unittest.main()
