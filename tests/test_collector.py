import tempfile
import sqlite3
import io
import json
from contextlib import closing
from contextlib import redirect_stdout, redirect_stderr
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from wifi_optimizer.collector import CollectorConfig, WiFiCollector
from wifi_optimizer.measurement import measure_quality


def sample(*args, **kwargs):
    return {"status": "ok", "wifi": None, "ping": {},
            "started_at": "2026-09-29T00:00:00Z", "finished_at": "2026-09-29T00:00:01Z",
            "speed": {"status": "not_requested"}, "warnings": []}


class CollectorTests(unittest.TestCase):
    def make(self, measure=sample, **kwargs):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        collector = WiFiCollector(CollectorConfig(interval=1), log_dir=directory.name,
                                  db_path=Path(directory.name) / 'test.sqlite3', data_kind='example',
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

    def test_storage_survives_queue_overflow_and_restart(self):
        collector, directory = self.make(queue_size=1)
        collector.start(max_samples=2)
        collector._thread.join(5)
        self.assertFalse(collector.running)
        self.assertEqual(collector.dropped_results, 1)
        result = collector.results.get_nowait()
        self.assertEqual(result['storage']['status'], 'saved')
        session = collector.session_id
        collector.start(max_samples=1)
        collector._thread.join(3)
        self.assertEqual(collector.session_id, session)
        self.assertTrue(collector.close(timeout=3))
        with closing(sqlite3.connect(directory / 'test.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM measurement').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT count(*) FROM session').fetchone()[0], 1)
            self.assertIsNotNone(db.execute('SELECT finished_at FROM session').fetchone()[0])

    def test_save_failure_is_separate_and_next_cycle_recovers(self):
        from wifi_optimizer.storage import MeasurementStore
        collector, directory = self.make()
        save = MeasurementStore.save_measurement
        calls = []
        def fail_once(store, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise sqlite3.OperationalError('disk full')
            return save(store, *args, **kwargs)
        with patch.object(MeasurementStore, 'save_measurement', fail_once):
            collector.start(max_samples=2)
            first = collector.results.get(timeout=3)
            second = collector.results.get(timeout=3)
            self.assertEqual(first['status'], 'ok')
            self.assertEqual(first['storage']['status'], 'error')
            self.assertEqual(second['storage']['status'], 'saved')
        self.assertTrue(collector.close(timeout=3))
        self.assertEqual(collector.storage_failures, 1)
        with closing(sqlite3.connect(directory / 'test.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT sequence FROM measurement').fetchall(), [(2,)])

    def test_initialization_failure_still_publishes_measurement(self):
        collector, _ = self.make()
        with patch('wifi_optimizer.collector.MeasurementStore', side_effect=OSError('access denied')):
            collector.start(max_samples=1)
            result = collector.results.get(timeout=3)
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['storage']['status'], 'error')
            self.assertTrue(collector.close(timeout=3))

    def test_close_waits_for_active_save_and_finalizes_off_main_thread(self):
        from wifi_optimizer.storage import MeasurementStore
        collector, _ = self.make()
        entered, release = threading.Event(), threading.Event()
        save = MeasurementStore.save_measurement
        finish = MeasurementStore.finish_session
        threads = []
        def delayed_save(store, *args, **kwargs):
            entered.set()
            release.wait(3)
            return save(store, *args, **kwargs)
        def track_finish(store, *args, **kwargs):
            threads.append(threading.current_thread().name)
            return finish(store, *args, **kwargs)
        with patch.object(MeasurementStore, 'save_measurement', delayed_save), \
                patch.object(MeasurementStore, 'finish_session', track_finish):
            collector.start(max_samples=1)
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(collector.close())
                with self.assertRaises(RuntimeError):
                    collector.start()
            finally:
                release.set()
            self.assertTrue(collector.close(timeout=3))
            self.assertEqual(threads, ['wifi-db-close'])
            self.assertEqual(collector.results.get_nowait()['storage']['status'], 'saved')

    def test_monitor_cli_saved_output_and_failure_exit_code(self):
        from wifi_optimizer.__main__ import main
        collector, _ = self.make()
        for fail in (False, True):
            # A fresh collector per CLI invocation, using only a temporary example DB.
            if fail:
                collector, _ = self.make()
                collector.db_path = collector.db_path.parent  # Directory cannot be a SQLite file.
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch('sys.argv', ['wifi_optimizer', '--monitor', '--samples', '1']), \
                    patch('wifi_optimizer.collector.WiFiCollector', return_value=collector), \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                code = main()
            output = json.loads(stdout.getvalue())
            self.assertEqual(code, 2 if fail else 0)
            self.assertEqual(output['storage']['status'], 'error' if fail else 'saved')
            if fail:
                self.assertIn('DB storage failures', stderr.getvalue())

    @patch('wifi_optimizer.measurement.collect_wifi')
    def test_cancel_before_network(self, wifi):
        stop = threading.Event()
        stop.set()
        self.assertEqual(measure_quality(stop_event=stop)['status'], 'cancelled')
        wifi.assert_not_called()
