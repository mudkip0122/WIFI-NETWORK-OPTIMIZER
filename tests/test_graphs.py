"""Live graph regressions for outages, sparse speed and bounded history."""
import math
import tkinter as tk
import unittest

from wifi_optimizer.visualization.graphs import GraphHistory, RealTimeGraphs


def result(bssid='a'):
    return {'wifi': {'interface': 'Wi-Fi', 'bssid': bssid, 'ssid': 'test',
                     'band': '5 GHz', 'rssi_dbm': -60, 'signal_percent': 80},
            'ping': {'external': {'avg_ms': 0, 'packet_loss_percent': 100}},
            'speed': {'status': 'partial', 'download': {'status': 'ok', 'mbps': 0},
                      'upload': {'status': 'error', 'mbps': None}}}


class GraphTests(unittest.TestCase):
    def test_outage_and_unrequested_speed_leave_gaps(self):
        history = GraphHistory()
        history.append(result(), 1)
        history.append({'wifi': None, 'speed': {'status': 'not_requested'}}, 2)
        history.append(result(), 3)
        self.assertEqual(history.series('rssi')[0], [1, 2, 3])
        self.assertTrue(math.isnan(history.series('rssi')[1][1]))
        self.assertEqual(history.series('external_ping')[1][0], 0)
        self.assertEqual(history.series('external_loss')[1][0], 100)
        self.assertEqual(history.series('download')[1][0], 0)
        self.assertTrue(math.isnan(history.series('upload')[1][0]))
        self.assertTrue(math.isnan(history.series('download')[1][1]))

    def test_limit_connection_change_and_reset(self):
        history = GraphHistory()
        for i in range(120):
            history.append(result(), i)
        self.assertEqual(len(history.rows), 100)
        self.assertEqual(history.rows[0]['time'], 20)
        history.append(result('b'), 120)
        self.assertEqual(len(history.rows), 1)
        history.clear()
        self.assertFalse(history.rows)
        self.assertIsNone(history.connection_key)

    def test_select_graphs_with_missing_and_zero_readings(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        graph = RealTimeGraphs(root)
        graph.show_result(result(), 1)
        graph.show_result({'wifi': None}, 2)
        for name in graph.SPECS:
            graph.selector.set(name)
            graph.draw()
            graph.canvas.draw()
            self.assertEqual(graph.ax.get_title(), name)
            self.assertEqual(len(graph.ax.lines), len(graph.SPECS[name][1]))
            self.assertTrue(math.isnan(graph.ax.lines[0].get_ydata()[-1]))
        root.update_idletasks()
