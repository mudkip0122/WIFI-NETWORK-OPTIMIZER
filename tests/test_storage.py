import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from wifi_optimizer.storage import DuplicateMeasurementError, MeasurementStore, SchemaVersionError


def sample():
    return {
        'started_at': '2026-09-29T09:00:00+09:00',
        'finished_at': '2026-09-29T09:00:02+09:00', 'status': 'partial',
        'wifi': {'interface': 'Wi-Fi', 'ssid': '테스트', 'bssid': 'AA:BB:CC:DD:EE:FF',
                 'rssi_dbm': -60, 'rssi_source': 'native_wifi', 'signal_percent': 80,
                 'timestamp': '2026-09-29T09:00:00+09:00', 'warnings': []},
        'network': {'interface': 'Wi-Fi', 'index': 7, 'source_ip': '192.168.1.2',
                    'gateway': '192.168.1.1'},
        'ping': {
            'gateway': {'status': 'unavailable', 'error': 'No IPv4 gateway'},
            'external': {'status': 'no_reply', 'target': '1.1.1.1', 'attempted': 4,
                         'sent': 4, 'received': 0, 'send_errors': 0,
                         'packet_loss_percent': 100, 'min_ms': None, 'avg_ms': None,
                         'max_ms': None, 'samples': [{'status': 'RequestTimedOut'}]},
        },
        'speed': {'status': 'partial', 'server': 'example.test',
                  'download': {'status': 'ok', 'mbps': 12.5, 'bytes': 1000, 'seconds': 0.1},
                  'upload': {'status': 'error', 'mbps': None, 'error': 'timeout'}},
        'warnings': ['측정 중 연결 변경'],
    }


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'nested' / 'test.sqlite3'
        self.store = MeasurementStore(self.path)
        self.addCleanup(self.store.close)
        self.session = self.store.create_session(data_kind='example',
                                                  started_at='2026-09-29T00:00:00Z')

    def count(self, table):
        return self.store.connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0]

    def test_reopen_preserves_hierarchy_nulls_and_utc(self):
        space = self.store.create_space('강의실', width=10, height=10)
        location = self.store.create_location(space, '입구', x=1, y=2)
        result = sample()
        mid = self.store.save_measurement(self.session, result, location_id=location)
        self.store.finish_session(self.session, finished_at=result['finished_at'])
        self.store.close()
        with MeasurementStore(self.path) as reopened:
            db = reopened.connection
            row = db.execute('SELECT * FROM measurement WHERE id=?', (mid,)).fetchone()
            self.assertEqual(json.loads(row['raw_result_json']), result)
            self.assertEqual(row['started_at'], '2026-09-29T00:00:00.000000+00:00')
            self.assertEqual(row['bssid'], 'aa:bb:cc:dd:ee:ff')
            self.assertEqual(row['location_id'], location)
            ping = db.execute("SELECT * FROM ping_result WHERE target_kind='external'").fetchone()
            self.assertEqual(ping['packet_loss_percent'], 100)
            self.assertIsNone(ping['avg_ms'])
            transfers = db.execute('SELECT * FROM speed_transfer ORDER BY direction').fetchall()
            self.assertEqual(transfers[0]['mbps'], 12.5)
            self.assertIsNone(transfers[1]['mbps'])
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_schema_and_pragmas(self):
        db = self.store.connection
        self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
        self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0], 1)
        self.assertEqual(db.execute('PRAGMA busy_timeout').fetchone()[0], 5000)
        self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0], 8)

    def test_idempotence_and_conflict(self):
        result = sample()
        mid = self.store.save_measurement(self.session, result)
        self.assertEqual(self.store.save_measurement(self.session, copy.deepcopy(result)), mid)
        self.assertEqual(self.count('measurement'), 1)
        with self.assertRaises(DuplicateMeasurementError):
            self.store.save_measurement(self.session, result, repeat_group_id='different')
        result['wifi']['rssi_dbm'] = -70
        with self.assertRaises(DuplicateMeasurementError):
            self.store.save_measurement(self.session, result)
        self.assertEqual(self.count('measurement'), 1)

    def test_child_failure_rolls_back_new_ap_and_all_children(self):
        result = sample()
        result['speed']['upload']['mbps'] = -1
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_measurement(self.session, result)
        for table in ('ap', 'measurement', 'ping_result', 'speed_result', 'speed_transfer'):
            self.assertEqual(self.count(table), 0, table)
        # The same connection remains usable after rollback.
        self.store.save_measurement(self.session, sample())
        self.assertEqual(self.count('measurement'), 1)

    def test_error_cancelled_and_not_requested(self):
        for seq, status in enumerate(('error', 'cancelled'), 1):
            result = sample()
            result.update(wifi=None, ping={}, speed={'status': 'not_requested'}, status=status)
            result['error_code'] = 'permission_denied' if status == 'error' else None
            self.store.save_measurement(self.session, result, sequence=seq)
        self.assertEqual(self.count('measurement'), 2)
        self.assertEqual(self.count('ap'), 0)
        self.assertEqual(self.count('speed_result'), 0)
        self.assertEqual(self.count('ping_result'), 0)
        self.assertIsNone(self.store.connection.execute('SELECT rssi_dbm FROM measurement').fetchone()[0])

    def test_send_failure_keeps_loss_null(self):
        result = sample()
        result['ping']['external'].update(status='error', sent=0, received=0, send_errors=4,
                                           packet_loss_percent=None)
        self.store.save_measurement(self.session, result)
        row = self.store.connection.execute(
            "SELECT packet_loss_percent FROM ping_result WHERE target_kind='external'"
        ).fetchone()
        self.assertIsNone(row[0])

    def test_invalid_inputs_do_not_persist(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            result = sample()
            result['wifi']['rssi_dbm'] = value
            with self.assertRaises(ValueError):
                self.store.save_measurement(self.session, result)
        result = sample()
        result['started_at'] = '2026-09-29T00:00:00'
        with self.assertRaises(ValueError):
            self.store.save_measurement(self.session, result)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_measurement(self.session, sample(), location_id=999)
        with self.assertRaises(ValueError):
            self.store.save_measurement(self.session, sample(), sequence=True)
        self.assertEqual(self.count('ap'), 0)
        self.assertEqual(self.count('measurement'), 0)

    def test_ap_reuse_sessions_and_finished_session(self):
        self.store.save_measurement(self.session, sample())
        self.store.save_measurement(self.session, sample(), sequence=2)
        other = self.store.create_session(data_kind='example')
        self.store.save_measurement(other, sample())
        self.assertEqual(self.count('ap'), 1)
        self.store.finish_session(other)
        with self.assertRaises(ValueError):
            self.store.save_measurement(other, sample(), sequence=2)
        self.assertEqual(self.count('measurement'), 3)

    def test_unsupported_and_unversioned_files_untouched(self):
        for version in (0, 2):
            path = Path(self.directory.name) / f'unknown{version}.sqlite3'
            with closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE existing(value TEXT)')
                db.execute(f'PRAGMA user_version = {version}')
            before = path.read_bytes()
            with self.assertRaises(SchemaVersionError):
                MeasurementStore(path)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
