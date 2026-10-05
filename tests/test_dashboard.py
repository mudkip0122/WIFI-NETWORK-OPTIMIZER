"""Dashboard regression tests for current-cycle and partial measurements."""
import copy
import tkinter as tk
import unittest
from wifi_optimizer.visualization.dashboard import Dashboard, readings


class DashboardTests(unittest.TestCase):
    def test_missing_readings_and_unrequested_speed(self):
        values = readings({'wifi': None, 'speed': {'status': 'not_requested'}})
        self.assertEqual(values['rssi'], '측정 불가')
        self.assertEqual(values['external_ping'], '측정 불가')
        self.assertEqual(values['download'], '이번 주기 미측정')

    def test_zero_loss_and_partial_speed(self):
        result = {'wifi': {'rssi_dbm': -60, 'rssi_source': 'native_wifi'},
                  'ping': {'external': {'avg_ms': 0, 'packet_loss_percent': 100}},
                  'speed': {'status': 'partial', 'download': {'status': 'ok', 'mbps': 0},
                            'upload': {'status': 'error', 'mbps': None}}}
        original = copy.deepcopy(result)
        values = readings(result)
        self.assertEqual(values['download'], '0.00 Mbps')
        self.assertEqual(values['upload'], '측정 실패')
        self.assertEqual(values['external_loss'], '100.00 %')
        self.assertEqual(values['external_ping'], '0.00 ms')
        self.assertIn('드라이버 실측', values['rssi'])
        self.assertEqual(result, original)

    def test_widget_clears_previous_connection_and_speed(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        dashboard = Dashboard(root)
        dashboard.show_result({'wifi': {'ssid': '테스트', 'channel': 36},
                               'speed': {'status': 'ok', 'download': {'status': 'ok', 'mbps': 80}},
                               'status': 'ok', 'finished_at': '2026-10-05T00:00:00+00:00'})
        self.assertEqual(dashboard.values['ssid'].get(), '테스트')
        self.assertEqual(dashboard.values['download'].get(), '80.00 Mbps')
        dashboard.show_result({'status': 'error', 'wifi': None})
        self.assertEqual(dashboard.values['ssid'].get(), '측정 불가')
        self.assertEqual(dashboard.values['download'].get(), '이번 주기 미측정')
        self.assertIn('측정 실패', dashboard.updated.get())

    def test_application_routes_results_to_dashboard(self):
        from gui import WifiMonitorApp
        import matplotlib.pyplot as plt
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        app = WifiMonitorApp(root, auto_start=False)
        self.addCleanup(lambda: plt.close(app.fig))
        self.addCleanup(lambda: root.after_cancel(app.timer))
        result = {'sequence': 1, 'status': 'error', 'duration_seconds': 0.1,
                  'finished_at': '2026-10-05T00:00:00+00:00', 'wifi': None,
                  'speed': {'status': 'not_requested'}, 'ping': {},
                  'storage': {'status': 'saved', 'measurement_id': 1}}
        app.show_result(result)
        root.update_idletasks()
        self.assertEqual(app.dashboard.values['ssid'].get(), '측정 불가')
        self.assertIn('DB 저장 완료', app.storage_status.get())
        self.assertLessEqual(root.winfo_reqheight(), 960)
