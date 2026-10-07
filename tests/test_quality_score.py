import copy
import unittest

from wifi_optimizer.analysis.quality import evaluate_quality


def measurement():
    return {'status': 'ok', 'wifi': {'rssi_dbm': -50, 'rssi_source': 'native_wifi'},
            'ping': {key: {'status': 'ok', 'sent': 20, 'avg_ms': 0, 'packet_loss_percent': 0}
                     for key in ('gateway', 'external')},
            'speed': {'status': 'ok', 'download': {'status': 'ok', 'mbps': 100},
                      'upload': {'status': 'ok', 'mbps': 20}}}


class QualityScoreTests(unittest.TestCase):
    def test_complete_and_immutable(self):
        result = measurement()
        original = copy.deepcopy(result)
        quality = evaluate_quality(result)
        self.assertEqual((quality['score'], quality['grade'], quality['status']), (100, '매우 좋음', 'complete'))
        self.assertEqual(quality['coverage_percent'], 100)
        self.assertEqual(result, original)

    def test_unrequested_speed_renormalizes(self):
        result = measurement()
        result['speed']['status'] = 'not_requested'
        quality = evaluate_quality(result)
        self.assertEqual(quality['score'], 100)
        self.assertEqual(quality['coverage_percent'], 90)
        self.assertEqual(quality['missing'], ['download', 'upload'])

    def test_no_reply_counts_loss_but_not_latency(self):
        result = measurement()
        for ping in result['ping'].values():
            ping.update(status='no_reply', avg_ms=None, packet_loss_percent=100)
        quality = evaluate_quality(result)
        self.assertEqual(quality['scores']['gateway_loss'], 0)
        self.assertNotIn('gateway_ping', quality['scores'])
        self.assertLess(quality['score'], 60)

    def test_failure_cancel_and_changed_connection(self):
        for state, warnings in (('error', []), ('cancelled', []), ('partial', ['changed'])):
            result = measurement()
            result.update(status=state, warnings=warnings)
            self.assertIsNone(evaluate_quality(result)['score'])

    def test_insufficient_and_invalid_readings(self):
        for value in (None, float('nan'), float('inf'), True, -101, 'bad'):
            result = measurement()
            result['wifi']['rssi_dbm'] = value
            self.assertIsNone(evaluate_quality(result)['score'])
        result = measurement()
        for ping in result['ping'].values():
            ping['sent'] = 0
        self.assertIsNone(evaluate_quality(result)['score'])

    def test_partial_speed_and_targets(self):
        result = measurement()
        result['speed']['status'] = 'partial'
        result['speed']['upload']['status'] = 'error'
        result['speed']['download']['mbps'] = 0
        quality = evaluate_quality(result)
        self.assertEqual(quality['scores']['download'], 0)
        self.assertNotIn('upload', quality['scores'])
        self.assertEqual(evaluate_quality(measurement(), download_target=200)['scores']['download'], 50)
        for target in (0, -1, float('inf'), float('nan'), True):
            with self.assertRaises(ValueError):
                evaluate_quality(result, download_target=target)

    def test_thresholds_and_distinct_ping_targets(self):
        result = measurement()
        for rssi, expected in ((-85, 20), (-75, 40), (-67, 60), (-55, 90), (-50, 100)):
            result['wifi']['rssi_dbm'] = rssi
            self.assertEqual(evaluate_quality(result)['scores']['rssi'], expected)
        for ping in result['ping'].values():
            ping.update(avg_ms=20, sent=4)
        quality = evaluate_quality(result)
        self.assertEqual(quality['scores']['gateway_ping'], 75)
        self.assertEqual(quality['scores']['external_ping'], 100)
        self.assertTrue(any('표본 4개' in note for note in quality['notes']))

    def test_dashboard_clears_score(self):
        import tkinter as tk
        from wifi_optimizer.visualization.dashboard import Dashboard
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        dashboard = Dashboard(root)
        dashboard.show_result(measurement())
        self.assertIn('100.0/100', dashboard.quality.get())
        dashboard.show_result({'status': 'error'})
        self.assertIn('평가 불가', dashboard.quality.get())
        self.assertNotIn('100.0/100', dashboard.quality.get())
