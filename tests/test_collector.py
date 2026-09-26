import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from wifi_optimizer.collector import CollectorConfig, WiFiCollector
from wifi_optimizer.measurement import measure_quality


def sample(*args, **kwargs):
    return {"status": "ok", "wifi": None, "ping": {},
            "speed": {"status": "not_requested"}, "warnings": []}


class CollectorTests(unittest.TestCase):
    def make(self, measure=sample, **kwargs):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        collector = WiFiCollector(CollectorConfig(interval=1), log_dir=directory.name,
                                  measure=measure, **kwargs)
        self.addCleanup(lambda: collector.close(timeout=3))
        return collector, Path(directory.name)

    def test_config(self):
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                CollectorConfig(interval=value)

    def test_duplicate_start_and_cooperative_stop(self):
        entered = threading.Event()
        def measure(*args, stop_event):
            entered.set()
            stop_event.wait(3)
            return sample()
        collector, _ = self.make(measure)
        self.assertTrue(collector.start())
        self.assertTrue(entered.wait(2))
        self.assertFalse(collector.start())
        self.assertTrue(collector.stop(timeout=3))
        self.assertFalse(collector.request_speed())
        self.assertEqual(collector.results.get(timeout=1)['sequence'], 1)

    def test_interval_and_restart(self):
        collector, _ = self.make()
        collector.start(max_samples=2)
        first = collector.results.get(timeout=2)
        second = collector.results.get(timeout=3)
        self.assertEqual((first['sequence'], second['sequence']), (1, 2))
        self.assertTrue(collector.stop(timeout=2))
        collector.start(max_samples=1)
        self.assertEqual(collector.results.get(timeout=2)['sequence'], 3)

    def test_failure_then_recovery_and_log(self):
        calls = []
        def measure(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError('failure')
            return sample()
        collector, directory = self.make(measure)
        collector.start(max_samples=2)
        self.assertEqual(collector.results.get(timeout=2)['status'], 'error')
        self.assertEqual(collector.results.get(timeout=3)['status'], 'ok')
        collector.stop(timeout=2)
        text = next(directory.glob('*.log')).read_text(encoding='utf-8')
        self.assertIn('measurement_exception', text)
        self.assertIn('stopped', text)

    def test_speed_serialization(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def measure(interface, target, count, speed, **kwargs):
            calls.append(speed)
            if len(calls) == 1:
                entered.set()
                release.wait(2)
            return sample()
        collector, _ = self.make(measure)
        collector.start(max_samples=2)
        self.assertTrue(entered.wait(2))
        self.assertTrue(collector.request_speed())
        self.assertFalse(collector.request_speed())
        release.set()
        collector.results.get(timeout=2)
        collector.results.get(timeout=2)
        self.assertEqual(calls, [False, True])

    def test_bounded_queue(self):
        collector, _ = self.make(queue_size=1)
        collector._publish({'sequence': 1})
        collector._publish({'sequence': 2})
        self.assertEqual(collector.results.get()['sequence'], 2)
        self.assertEqual(collector.dropped_results, 1)

    @patch('wifi_optimizer.measurement.collect_wifi')
    def test_cancel_before_network(self, wifi):
        stop = threading.Event()
        stop.set()
        self.assertEqual(measure_quality(stop_event=stop)['status'], 'cancelled')
        wifi.assert_not_called()
