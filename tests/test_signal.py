import subprocess
import unittest
from unittest.mock import patch

from wifi_optimizer.collectors.signal import (
    WifiMeasurementError,
    get_wifi_signal_strength,
    parse_signal,
)


class SignalTests(unittest.TestCase):
    def test_localized_output(self):
        for text, expected in [("    Signal : 100%", 100), (" 신호 : 82 %", 82),
                               ("Signal : 0%", 0), ("Signal : 101%", None),
                               ("State : disconnected", None)]:
            with self.subTest(text=text):
                self.assertEqual(parse_signal(text), expected)

    @patch("wifi_optimizer.collectors.signal.subprocess.run")
    def test_command_success(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, b"Signal : 75%", b"")
        self.assertEqual(get_wifi_signal_strength(), 75)

    @patch("wifi_optimizer.collectors.signal.subprocess.run")
    def test_korean_encodings(self, run):
        for encoding in ("utf-8", "cp949"):
            with self.subTest(encoding=encoding):
                run.return_value = subprocess.CompletedProcess(
                    [], 0, "신호 : 82%".encode(encoding), b""
                )
                self.assertEqual(get_wifi_signal_strength(), 82)

    @patch("wifi_optimizer.collectors.signal.subprocess.run")
    def test_permission_failure(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, b"error 5: requires elevation", b"")
        with self.assertRaises(WifiMeasurementError):
            get_wifi_signal_strength()

    @patch("wifi_optimizer.collectors.signal.subprocess.run")
    def test_timeout(self, run):
        run.side_effect = subprocess.TimeoutExpired("netsh", 5)
        with self.assertRaises(WifiMeasurementError):
            get_wifi_signal_strength()


if __name__ == "__main__":
    unittest.main()
