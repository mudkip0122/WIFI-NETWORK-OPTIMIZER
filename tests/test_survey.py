from pathlib import Path
import tempfile
import unittest

from test_storage import sample
from wifi_optimizer.analysis.coverage import SurveyPoint, estimate_coverage, summarize_points
from wifi_optimizer.optimization.recommendations import diagnose, placement_advice
from wifi_optimizer.storage import MeasurementStore


def point(point_id, x, y, rssi):
    return SurveyPoint(point_id, str(point_id), x, y, {'rssi': rssi}, {'rssi': 1}, ())


def save_point(store, location, *, rssi=-85, bssid='AA:BB:CC:DD:EE:FF',
               kind='real', warnings=(), quality=None, band='5 GHz', latency=None):
    result = sample()
    result['wifi'].update(rssi_dbm=rssi, bssid=bssid, band=band, channel=36)
    result['warnings'] = list(warnings)
    if quality is not None:
        result['quality'] = {'score': quality}
    if latency is not None:
        result['ping']['external'].update(status='ok', received=4, packet_loss_percent=0,
                                          min_ms=latency, avg_ms=latency, max_ms=latency)
    store.save_measurement(store.create_session(data_kind=kind), result, location_id=location)


class SurveyTests(unittest.TestCase):
    def test_filter_and_previous_quality_calculation(self):
        with MeasurementStore(':memory:') as store:
            space = store.create_space('실습실')
            measured = store.create_location(space, '구석', x=0, y=0)
            empty = store.create_location(space, '미측정', x=2, y=2)
            save_point(store, measured, quality=40)
            save_point(store, measured, rssi=-75)
            save_point(store, measured, bssid='AA:BB:CC:DD:EE:00', rssi=-40)
            save_point(store, measured, band='2.4 GHz', rssi=-35)
            save_point(store, measured, kind='example', rssi=-45)
            save_point(store, measured, warnings=['연결 변경'], rssi=-55)
            self.assertEqual([ap['samples'] for ap in store.survey_access_points(space)], [2, 1, 1])
            points = summarize_points(store.survey_rows(space, 'aa:bb:cc:dd:ee:ff', '5 GHz'))
            self.assertEqual(points[0].averages['rssi'], -80)
            self.assertEqual(points[0].counts['quality'], 2)
            self.assertEqual(points[0].rssi_sources, ('native_wifi',))
            self.assertEqual(points[0].averages['external_loss'], 100)
            self.assertNotIn('external_ping', points[0].averages)
            self.assertEqual(points[1].id, empty)
            self.assertEqual(points[1].averages, {})

    def test_metric_footprint_and_contiguous_regions(self):
        triangle = [point(1, 0, 0, -80), point(2, 4, 0, -80), point(3, 0, 4, -80)]
        triangle[0].averages['external_ping'] = 15
        triangle[0].counts['external_ping'] = 1
        result = estimate_coverage(triangle, 4, 4)
        self.assertGreater(result.assessed, 0)
        self.assertLess(result.assessed, result.columns * result.rows)
        self.assertEqual(len(result.regions), 1)
        self.assertEqual(len(result.regions[0]), result.assessed)
        self.assertEqual(result.values['external_ping'], {})
        self.assertEqual(estimate_coverage(triangle, 4, 4, rssi_limit=-85).regions, [])
        self.assertEqual(estimate_coverage(triangle[:2], 4, 4).assessed, 0)

        square = [point(x + 3 * y, x, y, -90 if (x, y) in ((0, 0), (2, 2)) else -50)
                  for x in range(3) for y in range(3)]
        result = estimate_coverage(square, 2, 2)
        self.assertEqual(result.assessed, result.columns * result.rows)
        self.assertEqual(len(result.regions), 2)

    def test_distinguishes_external_path_and_weak_signal(self):
        weak = point(1, 0, 0, -86)
        weak.radio = (('5 GHz', 36),)
        findings = ' '.join(diagnose(weak))
        self.assertIn('2.4 GHz', findings)
        self.assertIn('[R01] RSSI -86.0 dBm', findings)
        healthy_radio = point(2, 1, 1, -65)
        healthy_radio.averages.update(gateway_ping=8, gateway_loss=0, external_ping=120)
        self.assertIn('유선 연결', ' '.join(diagnose(healthy_radio)))
        healthy_radio.averages['gateway_ping'] = 30
        self.assertIn('덜 혼잡한 지원 채널', ' '.join(diagnose(healthy_radio)))
        self.assertIn('「1」', placement_advice([weak, healthy_radio]))

    def test_gui_entry_displays_real_saved_points_and_reclassifies(self):
        import tkinter as tk
        from unittest.mock import patch

        from gui import WifiMonitorApp

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'survey.db'
            with MeasurementStore(db) as store:
                space = store.create_space('내 방', width=3.6, height=3.6)
                for index, (x, y) in enumerate(((0, 0), (3.6, 0), (0, 3.6))):
                    location = store.create_location(space, f'지점 {index}', x=x, y=y)
                    save_point(store, location, quality=45, latency=20 + index * 10)
            root = tk.Tk()
            root.withdraw()
            try:
                app = WifiMonitorApp(root, auto_start=False)
                with patch('wifi_optimizer.storage.DEFAULT_DB_PATH', db):
                    app.show_survey()
                window = app.survey_window
                root.update_idletasks()
                self.assertEqual(len(window.table.get_children()), 3)
                self.assertTrue(window.canvas.find_withtag('weak_edge'))
                self.assertIn('100.0%', window.summary.cget('text'))
                self.assertIn('AP 배치', window.details.get('1.0', 'end'))
                window.metric.current(1)
                window.draw_map()
                self.assertTrue(window.coverage.values['external_ping'])
                self.assertIn('회색은 이 지표의 보간 범위 밖', window.summary.cget('text'))
                window.metric.current(2)
                window.draw_map()
                self.assertTrue(window.coverage.values['quality'])
                window.rssi_input.set('-100')
                window.quality_input.set('0')
                window.apply_thresholds()
                self.assertEqual(window.coverage.regions, [])
                self.assertFalse(window.canvas.find_withtag('weak_edge'))
                root.after_cancel(app.timer)
            finally:
                root.destroy()
