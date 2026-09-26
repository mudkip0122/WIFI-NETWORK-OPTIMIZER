import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from wifi_optimizer.collectors.ping import measure_ping, summarize_ping
from wifi_optimizer.collectors.speed import transfer, measure_speed
from wifi_optimizer.collectors.wifi import WifiInfo
from wifi_optimizer.measurement import measure_quality


class PingTests(unittest.TestCase):
    def test_statistics(self):
        result = summarize_ping([{"status": "Success", "rtt_ms": 10},
                                 {"status": "TimedOut", "rtt_ms": None},
                                 {"status": "Success", "rtt_ms": 30}])
        self.assertEqual((result['min_ms'], result['avg_ms'], result['max_ms']), (10, 20, 30))
        self.assertAlmostEqual(result['packet_loss_percent'], 100 / 3)

    def test_no_replies_and_send_errors(self):
        result = summarize_ping([{"status": "TimedOut", "rtt_ms": None}])
        self.assertEqual(result['packet_loss_percent'], 100)
        self.assertIsNone(result['avg_ms'])
        result = summarize_ping([{"status": "send_error", "rtt_ms": None}])
        self.assertIsNone(result['packet_loss_percent'])
        self.assertEqual(result['sent'], 0)

    def test_validation(self):
        for target, count in [("1.1.1.1'; exit", 4), ("1.1.1.1", 0), ("1.1.1.1", 21)]:
            with self.assertRaises(ValueError):
                measure_ping(target, '192.0.2.2', count)

    @patch('wifi_optimizer.collectors.ping.send_probes')
    def test_source_and_error(self, run):
        run.return_value = [{'status': 'Success', 'rtt_ms': 2}]
        result = measure_ping('1.1.1.1', '192.0.2.2', count=1)
        run.assert_called_once_with('1.1.1.1', '192.0.2.2', 1, 1000)
        self.assertEqual(result['avg_ms'], 2)
        run.side_effect = OSError('access denied')
        result = measure_ping('1.1.1.1', '192.0.2.2')
        self.assertEqual(result['status'], 'error')
        self.assertIsNone(result['packet_loss_percent'])


class SpeedTests(unittest.TestCase):
    @patch('wifi_optimizer.collectors.speed.time.perf_counter', side_effect=[0, 1, 2])
    @patch('wifi_optimizer.collectors.speed.http.client.HTTPSConnection')
    def test_download_units_and_binding(self, connection, clock):
        response = connection.return_value.getresponse.return_value
        response.status = 200
        response.read.side_effect = [b'x' * 1000, b'']
        response.getheader.return_value = 'abc-ICN'
        result = transfer('download', '192.0.2.2', 1000)
        self.assertEqual(result['mbps'], 0.004)
        self.assertEqual(connection.call_args.kwargs['source_address'], ('192.0.2.2', 0))
        connection.return_value.close.assert_called_once()

    @patch('wifi_optimizer.collectors.speed.http.client.HTTPSConnection')
    def test_incomplete_download(self, connection):
        response = connection.return_value.getresponse.return_value
        response.status = 200
        response.read.side_effect = [b'x', b'']
        self.assertIsNone(transfer('download', '192.0.2.2', 1000)['mbps'])

    @patch('wifi_optimizer.collectors.speed.http.client.HTTPSConnection')
    def test_upload_failure(self, connection):
        connection.return_value.getresponse.return_value.status = 503
        result = transfer('upload', '192.0.2.2', 1000)
        self.assertEqual(result['status'], 'error')
        self.assertIsNone(result['mbps'])

    @patch('wifi_optimizer.collectors.speed.subprocess.run')
    def test_hard_timeout(self, run):
        run.side_effect = subprocess.TimeoutExpired('speed', 75)
        self.assertEqual(measure_speed('192.0.2.2')['status'], 'error')


class MeasurementTests(unittest.TestCase):
    @patch('wifi_optimizer.measurement.measure_speed')
    @patch('wifi_optimizer.measurement.measure_ping')
    @patch('wifi_optimizer.measurement.interface_network')
    @patch('wifi_optimizer.measurement.collect_wifi')
    def test_combined_and_connection_change(self, wifi, network, ping, speed):
        first = WifiInfo(interface='Wi-Fi', bssid='02:11:22:33:44:55', ssid='TEST')
        second = WifiInfo(interface='Wi-Fi', bssid='02:11:22:33:44:66', ssid='TEST')
        wifi.side_effect = [first, second]
        network.return_value = {'gateway': '192.0.2.1', 'source_ip': '192.0.2.2', 'index': 3}
        ping.return_value = {'status': 'ok'}
        speed.return_value = {'status': 'ok', 'download': {'mbps': 50}, 'upload': {'mbps': 10}}
        result = measure_quality(include_speed=True)
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['warnings'])
        self.assertEqual(ping.call_count, 2)
        speed.assert_called_once_with('192.0.2.2')
        json.dumps(result)

    @patch('wifi_optimizer.measurement.collect_wifi', side_effect=OSError('offline'))
    def test_offline(self, wifi):
        result = measure_quality()
        self.assertEqual(result['status'], 'error')
        self.assertIsNone(result['wifi'])
