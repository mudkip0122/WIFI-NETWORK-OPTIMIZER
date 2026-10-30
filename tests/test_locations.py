import tempfile
from pathlib import Path
import unittest

from wifi_optimizer.storage import MeasurementStore
from wifi_optimizer.collector import CollectorConfig, WiFiCollector
from test_storage import sample


class LocationTests(unittest.TestCase):
    def test_room_plan_click_and_reuse(self):
        import tkinter as tk
        from types import SimpleNamespace
        from unittest.mock import patch
        from wifi_optimizer.visualization.locations import LocationWindow
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.db'
            root = tk.Tk()
            root.withdraw()
            try:
                window = LocationWindow(root, path, lambda value: True)
                window.use_room()
                window.use_room()
                self.assertEqual(len(window.spaces), 1)
                self.assertEqual(window.current_space()['width'], 3.6)
                with patch('wifi_optimizer.visualization.locations.simpledialog.askstring',
                           return_value='중앙') as ask:
                    window.click_plan(SimpleNamespace(x=230, y=220))
                    self.assertEqual(ask.call_count, 1)
                    window.click_plan(SimpleNamespace(x=230, y=220))
                    window.click_plan(SimpleNamespace(x=0, y=0))
                    self.assertEqual(ask.call_count, 1)
                with MeasurementStore(path) as store:
                    points = store.list_locations(window.current_space()['id'])
                self.assertEqual(len(points), 1)
                self.assertEqual((points[0]['x'], points[0]['y']), (1.8, 1.8))
                self.assertEqual(window.table.selection(), (str(points[0]['id']),))
            finally:
                root.destroy()

    def test_location_window_selection(self):
        import tkinter as tk
        from wifi_optimizer.visualization.locations import LocationWindow
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.db'
            with MeasurementStore(path) as store:
                space = store.create_space('방')
                point = store.create_location(space, '문', x=1, y=2)
            root = tk.Tk()
            root.withdraw()
            chosen = []
            try:
                window = LocationWindow(root, path, lambda value: chosen.append(value) or True)
                root.update_idletasks()
                self.assertEqual(window.table.get_children(), (str(point),))
                window.table.selection_set(str(point))
                window.apply()
                self.assertEqual(chosen[0]['space_name'], '방')
                self.assertEqual(chosen[0]['y'], 2)
            finally:
                root.destroy()

    def test_coordinates_and_averages(self):
        with MeasurementStore(':memory:') as store:
            space = store.create_space('방', width=5, height=4)
            point = store.create_location(space, '입구', x=1, y=2)
            empty = store.create_location(space, '구석', x=5, y=4)
            for x, y in [(6, 0), (0, -1), (float('nan'), 0)]:
                with self.assertRaises(ValueError):
                    store.create_location(space, '오류', x=x, y=y)
            for kind, status, rssi in [('real', 'partial', -60), ('real', 'partial', -80),
                                        ('example', 'partial', -10), ('real', 'error', -20)]:
                session = store.create_session(data_kind=kind)
                result = sample()
                result['status'] = status
                result['wifi']['rssi_dbm'] = rssi
                store.save_measurement(session, result, location_id=point)
            rows = store.location_averages(space)
            self.assertEqual(rows[0]['samples'], 3)
            self.assertEqual(rows[0]['rssi_dbm'], -70)
            self.assertEqual(rows[0]['rssi_samples'], 2)
            self.assertIsNone(rows[0]['ping_avg_ms'])
            self.assertEqual(rows[0]['packet_loss_percent'], 100)
            self.assertEqual(rows[1]['id'], empty)
            self.assertEqual(rows[1]['samples'], 0)
            self.assertIsNone(rows[1]['rssi_dbm'])

    def test_collector_persists_location_and_repeat_group(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.db'
            with MeasurementStore(path) as store:
                space = store.create_space('강의실')
                point = store.create_location(space, '문', x=0, y=1)
            collector = WiFiCollector(CollectorConfig(interval=1, location_id=point),
                                      db_path=path, log_dir=directory,
                                      measure=lambda *args, **kwargs: sample())
            try:
                collector.start(max_samples=2)
                results = [collector.results.get(timeout=5) for _ in range(2)]
                collector.stop(timeout=3)
                self.assertEqual(results[0]['location']['x'], 0)
                with MeasurementStore(path) as store:
                    rows = store.list_measurements(location_id=point)
                    self.assertEqual(len(rows), 2)
                    saved = store.get_measurement(rows[0]['id'])
                    self.assertEqual(saved['repeat_group_id'], collector.session_id)
                    self.assertEqual(saved['result']['location']['space_name'], '강의실')
            finally:
                collector.close(timeout=3)
