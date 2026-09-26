import unittest
from unittest.mock import patch

from wifi_optimizer.collectors.wifi import collect_wifi, parse_interfaces
from wifi_optimizer.collectors.signal import WifiMeasurementError


EN = """
Name : Wi-Fi
GUID : 00000000-0000-0000-0000-000000000001
State : connected
SSID : Example:Lab
AP BSSID : 02:11:22:33:44:55
Band : 2.4 GHz
Channel : 4
Signal : 100%
"""
KO = """
이름 : 무선
상태 : 연결됨
SSID : 테스트
BSSID : 02:11:22:33:44:55
밴드 : 5GHz
채널 : 36
신호 : 82 %
"""


class WifiTests(unittest.TestCase):
    def test_languages_and_colon_in_ssid(self):
        a, b = parse_interfaces(EN)[0], parse_interfaces(KO)[0]
        self.assertEqual((a.ssid, a.bssid, a.channel, a.band),
                         ("Example:Lab", "02:11:22:33:44:55", 4, "2.4 GHz"))
        self.assertEqual((b.interface, b.signal_percent, b.band), ("무선", 82, "5 GHz"))

    def test_disconnected_and_malformed(self):
        row = parse_interfaces(EN.replace("connected", "disconnected"))[0]
        self.assertIsNone(row.ssid)
        self.assertIsNone(row.signal_percent)
        row = parse_interfaces(EN.replace("100%", "999%").replace("Channel : 4", "Channel : ???"))[0]
        self.assertIsNone(row.signal_percent)
        self.assertIsNone(row.channel)

    @patch("wifi_optimizer.collectors.wifi.query_rssi", return_value=-43)
    @patch("wifi_optimizer.collectors.wifi.run_netsh", return_value=EN)
    def test_native_rssi(self, run, native):
        info = collect_wifi()
        self.assertEqual((info.rssi_dbm, info.rssi_source), (-43, "native_wifi"))
        self.assertTrue(info.timestamp.endswith("+00:00"))
        native.assert_called_once_with("00000000-0000-0000-0000-000000000001")

    @patch("wifi_optimizer.collectors.wifi.query_rssi", side_effect=OSError("unsupported"))
    @patch("wifi_optimizer.collectors.wifi.run_netsh", return_value=EN)
    def test_estimate_is_labelled(self, run, native):
        info = collect_wifi()
        self.assertEqual((info.rssi_dbm, info.rssi_source), (-50, "estimated_from_signal"))
        self.assertTrue(info.warnings)

    @patch("wifi_optimizer.collectors.wifi.run_netsh", return_value=KO.replace("밴드 : 5GHz", ""))
    def test_missing_band_not_guessed(self, run):
        info = collect_wifi()
        self.assertIsNone(info.band)
        self.assertEqual(info.rssi_dbm, -59)

    @patch("wifi_optimizer.collectors.wifi.run_netsh", return_value=KO + KO.replace("무선", "무선2"))
    def test_multiple_interfaces(self, run):
        with self.assertRaises(WifiMeasurementError) as error:
            collect_wifi()
        self.assertEqual(error.exception.code, "ambiguous_interface")
        self.assertEqual(collect_wifi("무선2").interface, "무선2")

    @patch("wifi_optimizer.collectors.wifi.run_netsh")
    def test_missing_or_disconnected(self, run):
        for output, code in [("", "unavailable"), ("Name : Wi-Fi\nState : disconnected", "disconnected"),
                             ("이름 : 무선\n상태 : 연결되지 않음", "disconnected"),
                             ("Name : Wi-Fi\nState : ???", "unavailable")]:
            run.return_value = output
            with self.assertRaises(WifiMeasurementError) as error:
                collect_wifi()
            self.assertEqual(error.exception.code, code)
        run.return_value = KO
        with self.assertRaises(WifiMeasurementError) as error:
            collect_wifi("missing")
        self.assertEqual(error.exception.code, "not_found")
