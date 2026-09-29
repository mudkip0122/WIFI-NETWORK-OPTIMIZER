from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from wifi_optimizer.storage import MeasurementStore
from wifi_optimizer.__main__ import main
from test_storage import sample


class HistoryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'history.sqlite3'
        with MeasurementStore(self.path) as store:
            session = store.create_session()
            self.session = session
            space = store.create_space('교실')
            self.location = store.create_location(space, '창가', x=1, y=2)
            self.ids = []
            for sequence in range(1, 4):
                result = sample()
                if sequence == 3:
                    result['started_at'] = '2026-09-29T01:00:00Z'
                    result['finished_at'] = '2026-09-29T01:00:02Z'
                    result['wifi']['bssid'] = '11:22:33:44:55:66'
                self.ids.append(store.save_measurement(session, result, sequence=sequence,
                                                       location_id=self.location if sequence < 3 else None))
            example = store.create_session(data_kind='example')
            self.example_id = store.save_measurement(example, sample())

    def test_reopen_filters_time_boundaries_and_nulls(self):
        with MeasurementStore(self.path, readonly=True) as store:
            rows = store.list_measurements(from_time='2026-09-29T09:00:00+09:00',
                                           to_time='2026-09-29T10:00:00+09:00',
                                           bssid='AA:BB:CC:DD:EE:FF',
                                           location_id=self.location, session_id=self.session)
            self.assertEqual([r['id'] for r in rows], self.ids[1::-1])
            self.assertEqual(rows[0]['location_name'], '창가')
            self.assertEqual(rows[0]['packet_loss_percent'], 100)
            self.assertIsNone(rows[0]['ping_avg_ms'])
            self.assertIsNone(rows[0]['upload_mbps'])
            self.assertEqual(rows[0]['download_mbps'], 12.5)
            self.assertEqual(len(store.list_measurements(ap_id=rows[0]['ap_id'])), 2)
            self.assertEqual(store.list_measurements(location_id=999), [])

    def test_stable_pagination_and_data_kind(self):
        with MeasurementStore(self.path, readonly=True) as store:
            first = store.list_measurements(limit=2)
            second = store.list_measurements(limit=2, before=(first[-1]['started_at'], first[-1]['id']))
            self.assertEqual([r['id'] for r in first + second], self.ids[::-1])
            self.assertEqual([r['id'] for r in store.list_measurements(data_kind='example')],
                             [self.example_id])
            self.assertEqual(len(store.list_measurements(data_kind=None)), 4)

    def test_detail_preserves_original_and_context(self):
        with MeasurementStore(self.path, readonly=True) as store:
            row = store.get_measurement(self.ids[0])
            self.assertEqual(row['result'], sample())
            self.assertEqual(row['location_id'], self.location)
            self.assertEqual(row['data_kind'], 'real')
            self.assertIsNone(store.get_measurement(999))
            with self.assertRaises(sqlite3.OperationalError):
                store.create_space('readonly')

    def test_invalid_filters_and_injection(self):
        with MeasurementStore(self.path, readonly=True) as store:
            for kwargs in ({'limit': 0}, {'limit': 501}, {'ap_id': -1}, {'location_id': True},
                           {'from_time': '2026-09-29'}, {'from_time': '2026-09-30T00:00:00Z',
                            'to_time': '2026-09-29T00:00:00Z'}, {'bssid': "' OR 1=1--"},
                           {'data_kind': 'bad'}, {'before': ('2026-09-29T00:00:00Z', 0)}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    store.list_measurements(**kwargs)
            self.assertEqual(store.list_measurements(session_id="' OR 1=1--"), [])

    def test_readonly_does_not_create_files_or_wait_for_writer_reservation(self):
        missing = self.path.parent / 'missing' / 'data.sqlite3'
        with self.assertRaises(sqlite3.OperationalError):
            MeasurementStore(missing, readonly=True)
        self.assertFalse(missing.parent.exists())
        with MeasurementStore(self.path) as writer:
            writer.connection.execute('BEGIN IMMEDIATE')
            try:
                with MeasurementStore(self.path, readonly=True) as reader:
                    self.assertEqual(len(reader.list_measurements()), 3)
            finally:
                writer.connection.rollback()

    def cli(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with patch('sys.argv', ['wifi_optimizer', '--history', '--db', str(self.path), *args]), \
                redirect_stdout(output), redirect_stderr(error):
            code = main()
        return code, output.getvalue(), error.getvalue()

    def test_cli_list_detail_empty_and_errors(self):
        code, output, _ = self.cli('--limit', '1')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)[0]['id'], self.ids[-1])
        code, output, _ = self.cli('--record-id', str(self.ids[0]))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)['result'], sample())
        code, output, _ = self.cli('--location-id', '999')
        self.assertEqual((code, json.loads(output)), (0, []))
        self.assertEqual(self.cli('--record-id', '999')[0], 1)
        self.assertEqual(self.cli('--limit', '0')[0], 2)
