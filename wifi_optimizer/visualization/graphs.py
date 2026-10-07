"""Bounded measurement history and selectable live quality plots."""
from collections import deque
import math
from tkinter import ttk

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class GraphHistory:
    def __init__(self, limit=100):
        self.rows = deque(maxlen=limit)
        self.connection_key = None

    def clear(self):
        self.rows.clear()
        self.connection_key = None

    def append(self, result, elapsed):
        wifi = result.get('wifi') or {}
        if wifi:
            key = tuple(wifi.get(k) for k in ('interface', 'bssid', 'ssid', 'band'))
            if self.connection_key is not None and key != self.connection_key:
                self.rows.clear()
            self.connection_key = key
        row = {'time': elapsed, 'signal': wifi.get('signal_percent'),
               'rssi': wifi.get('rssi_dbm')}
        for target in ('gateway', 'external'):
            ping = result.get('ping', {}).get(target, {})
            row[target + '_ping'] = ping.get('avg_ms')
            row[target + '_loss'] = ping.get('packet_loss_percent')
        speed = result.get('speed') or {}
        for direction in ('download', 'upload'):
            transfer = speed.get(direction) or {}
            row[direction] = (transfer.get('mbps') if transfer.get('status') == 'ok'
                              and speed.get('status') != 'not_requested' else None)
        self.rows.append(row)

    def series(self, key):
        return [r['time'] for r in self.rows], [
            float('nan') if r[key] is None else r[key] for r in self.rows]


class RealTimeGraphs(ttk.Frame):
    SPECS = {
        'RSSI': ('RSSI (dBm)', [('rssi', 'RSSI')], None),
        '신호 세기': ('신호 (%)', [('signal', '신호')], (-5, 105)),
        'Ping': ('평균 Ping (ms)', [('gateway_ping', '게이트웨이'),
                                  ('external_ping', '외부')], None),
        '패킷 손실': ('손실 (%)', [('gateway_loss', '게이트웨이'),
                                   ('external_loss', '외부')], (-5, 105)),
        '속도': ('처리량 (Mbps)', [('download', '다운로드'), ('upload', '업로드')], None),
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.history = GraphHistory()
        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', padx=10)
        ttk.Label(toolbar, text='실시간 그래프').pack(side='left', padx=(0, 8))
        self.selector = ttk.Combobox(toolbar, values=list(self.SPECS), state='readonly', width=14)
        self.selector.set('RSSI')
        self.selector.pack(side='left')
        self.selector.bind('<<ComboboxSelected>>', lambda event: self.draw())
        ttk.Label(toolbar, text='최근 100개 · 빈 구간: 미측정/실패 · 연결/설정 변경 시 초기화').pack(side='left', padx=10)
        self.fig = Figure(figsize=(9, 2.6), layout='constrained')
        self.ax = self.fig.add_subplot()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.draw()

    def show_result(self, result, elapsed):
        self.history.append(result, elapsed)
        self.draw()

    def draw(self):
        name = self.selector.get()
        ylabel, series, limits = self.SPECS[name]
        self.ax.clear()
        for key, label in series:
            x, y = self.history.series(key)
            self.ax.plot(x, y, '-o', markersize=4, label=label)
        self.ax.set(title=name, xlabel='실행 후 시간 (초)', ylabel=ylabel)
        if limits:
            self.ax.set_ylim(*limits)
        elif name in ('Ping', '속도'):
            self.ax.set_ylim(bottom=0)
        if self.history.rows:
            first, last = self.history.rows[0]['time'], self.history.rows[-1]['time']
            self.ax.set_xlim(max(0, first - 1), max(last + 1, first + 25))
        self.ax.grid(True, alpha=0.25)
        self.ax.legend(loc='upper left')
        if not any(math.isfinite(y) for key, _ in series for y in self.history.series(key)[1]):
            self.ax.text(0.5, 0.5, '표시할 측정값이 없습니다', transform=self.ax.transAxes,
                         ha='center', va='center')
        self.canvas.draw_idle()
