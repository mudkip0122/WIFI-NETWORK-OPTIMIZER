"""Hidden-window integration tests for the application's history viewer."""
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from wifi_optimizer.storage import MeasurementStore
from wifi_optimizer.visualization.history import HistoryWindow
from test_storage import sample


class HistoryGuiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'history.sqlite3'
        with MeasurementStore(self.path) as store:
            session = store.create_session()
            self.record_id = store.save_measurement(session, sample())
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        original = tk.Toplevel
        def hidden(*args, **kwargs):
            window = original(*args, **kwargs)
            window.withdraw()
            return window
        with patch('wifi_optimizer.visualization.history.tk.Toplevel', hidden):
            self.viewer = HistoryWindow(self.root, self.path)
        self.addCleanup(self.viewer.close)

    def wait_for_query(self):
        deadline = time.monotonic() + 5
        while self.viewer.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.viewer.busy, 'History query did not finish')

    def test_list_selection_detail_and_empty_filter(self):
        self.wait_for_query()
        self.assertEqual(self.viewer.tree.get_children(), (str(self.record_id),))
        self.viewer.tree.selection_set(str(self.record_id))
        self.root.update()
        self.wait_for_query()
        self.assertIn('"no_reply"', self.viewer.detail.get('1.0', 'end'))
        self.assertIn('"data_kind": "real"', self.viewer.detail.get('1.0', 'end'))
        self.viewer.fields['location_id'].set('999')
        self.viewer.reload()
        self.wait_for_query()
        self.assertEqual(self.viewer.tree.get_children(), ())
        self.assertIn('기록이 없습니다', self.viewer.status.get())

    def test_missing_db_reports_error_and_clears_previous_rows(self):
        self.wait_for_query()
        self.viewer.db_path = self.path.parent / 'missing.sqlite3'
        self.viewer.reload()
        self.wait_for_query()
        self.assertIn('조회 실패', self.viewer.status.get())
        self.assertEqual(self.viewer.tree.get_children(), ())
        self.assertFalse(self.viewer.db_path.exists())
