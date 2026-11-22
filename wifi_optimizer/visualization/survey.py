"""Tk window for comparing measured locations, coverage, and recommendations."""
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from ..analysis.coverage import (
    METRICS, QUALITY_LIMIT, RSSI_LIMIT, estimate_coverage, is_low, summarize_points,
)
from ..analysis.quality import finite
from ..optimization.recommendations import diagnose, placement_advice
from ..storage import MeasurementStore


def _color(value, worst, best):
    ratio = min(1, max(0, (value - worst) / (best - worst)))
    return '#{:02x}{:02x}{:02x}'.format(*(round(a + (b - a) * ratio)
                                         for a, b in zip((224, 144, 45), (30, 134, 192))))


class SurveyWindow:
    def __init__(self, parent, db_path, space_id=None):
        self.db_path = db_path
        self.spaces, self.access_points, self.points = [], [], []
        self.active_space = None
        self.rssi_limit, self.quality_limit = RSSI_LIMIT, QUALITY_LIMIT
        self.window = tk.Toplevel(parent)
        self.window.title('Wi-Fi 공간 분석')
        self.window.geometry('1130x760')
        self.window.minsize(1040, 690)

        toolbar = ttk.Frame(self.window, padding=(12, 10))
        toolbar.pack(fill='x')
        self.space = ttk.Combobox(toolbar, state='readonly', width=23)
        self.ap = ttk.Combobox(toolbar, state='readonly', width=33)
        self.metric = ttk.Combobox(toolbar, state='readonly', width=14,
                                   values=[label for label, _, _, _ in METRICS.values()])
        self.metric.current(0)
        for label, combo in (('공간', self.space), ('AP', self.ap), ('Heatmap 지표', self.metric)):
            ttk.Label(toolbar, text=label).pack(side='left', padx=(0, 5))
            combo.pack(side='left', padx=(0, 15))
        ttk.Button(toolbar, text='측정 기록 새로고침', command=self.reload).pack(side='right')
        self.space.bind('<<ComboboxSelected>>', lambda _: self.load_space())
        self.ap.bind('<<ComboboxSelected>>', lambda _: self.load_points())
        self.metric.bind('<<ComboboxSelected>>', lambda _: self.draw_map())

        thresholds = ttk.Frame(self.window, padding=(12, 0, 12, 8))
        thresholds.pack(fill='x')
        self.rssi_input = tk.StringVar(value=str(RSSI_LIMIT))
        self.quality_input = tk.StringVar(value=str(QUALITY_LIMIT))
        for label, value in (('음영 기준 · RSSI(dBm) <', self.rssi_input),
                             ('또는 품질 점수 <', self.quality_input)):
            ttk.Label(thresholds, text=label).pack(side='left', padx=(0, 5))
            ttk.Entry(thresholds, textvariable=value, width=8).pack(side='left', padx=(0, 12))
        ttk.Button(thresholds, text='기준 적용', command=self.apply_thresholds).pack(side='left')

        body = ttk.Frame(self.window, padding=(12, 0, 12, 8))
        body.pack(fill='both', expand=True)
        map_panel = ttk.Frame(body)
        map_panel.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(map_panel, width=500, height=490, background='#f7f8fa',
                                highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda _: self.draw_map())
        self.summary = ttk.Label(map_panel, wraplength=500, justify='left', padding=(0, 7))
        self.summary.pack(fill='x')

        sidebar = ttk.Frame(body, padding=(15, 0, 0, 0))
        sidebar.pack(side='right', fill='both')
        columns = ('name', 'rssi', 'external_ping', 'quality')
        headers = ('측정 지점', 'RSSI (dBm)', '외부 Ping (ms)', '품질 점수')
        table_frame = ttk.Frame(sidebar)
        table_frame.pack(fill='x')
        self.table = ttk.Treeview(table_frame, columns=columns, show='headings', height=9,
                                  selectmode='browse')
        for key, title, width in zip(columns, headers, (145, 91, 105, 82)):
            self.table.heading(key, text=title)
            self.table.column(key, width=width, stretch=False, anchor='w' if key == 'name' else 'e')
        self.table.tag_configure('weak', foreground='#7f215e')
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left', fill='x', expand=True)
        scroll.pack(side='right', fill='y')
        self.table.bind('<<TreeviewSelect>>', lambda _: self.select_point())

        ttk.Label(sidebar, text='진단 및 개선 권장', padding=(0, 10, 0, 4)).pack(anchor='w')
        detail_frame = ttk.Frame(sidebar)
        detail_frame.pack(fill='both', expand=True)
        self.details = tk.Text(detail_frame, width=48, height=12, wrap='word', state='disabled',
                               padx=10, pady=8, font='TkDefaultFont', relief='flat')
        scroll = ttk.Scrollbar(detail_frame, orient='vertical', command=self.details.yview)
        self.details.configure(yscrollcommand=scroll.set)
        self.details.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.coverage = None
        self.reload(space_id)

    def reload(self, space_id=None):
        if space_id is None and self.active_space:
            space_id = self.active_space['id']
        try:
            with MeasurementStore(self.db_path) as store:
                self.spaces = store.list_spaces()
        except (ValueError, OSError, sqlite3.Error) as exc:
            messagebox.showerror('공간 분석 조회 실패', str(exc), parent=self.window)
            return
        self.space['values'] = [f"{space['id']} · {space['name']}" for space in self.spaces]
        if self.spaces:
            index = next((i for i, space in enumerate(self.spaces) if space['id'] == space_id),
                         len(self.spaces) - 1)
            self.space.current(index)
        else:
            self.space.set('')
        self.load_space()

    def load_space(self):
        ap_index = self.ap.current()
        previous = self.access_points[ap_index] if ap_index >= 0 else None
        index = self.space.current()
        self.active_space = self.spaces[index] if index >= 0 else None
        self.access_points = []
        if self.active_space:
            try:
                with MeasurementStore(self.db_path) as store:
                    self.access_points = store.survey_access_points(self.active_space['id'])
            except (ValueError, OSError, sqlite3.Error) as exc:
                messagebox.showerror('공간 분석 조회 실패', str(exc), parent=self.window)
        self.ap['values'] = [f"{ap['band'] or '대역 미확인'} · {ap['bssid'] or 'BSSID 미확인'} · {ap['ssid'] or 'SSID 미확인'}"
                             for ap in self.access_points]
        if self.access_points:
            index = next((i for i, ap in enumerate(self.access_points)
                          if previous and (ap['bssid'], ap['band']) == (previous['bssid'], previous['band'])), 0)
            self.ap.current(index)
        else:
            self.ap.set('')
        self.load_points()

    def load_points(self):
        self.points = []
        if self.active_space:
            index = self.ap.current()
            try:
                with MeasurementStore(self.db_path) as store:
                    space_id = self.active_space['id']
                    if index >= 0:
                        ap = self.access_points[index]
                        self.points = summarize_points(store.survey_rows(space_id, ap['bssid'], ap['band']))
                    else:
                        self.points = summarize_points((row['id'], row['name'], row['x'], row['y'], None)
                                                       for row in store.list_locations(space_id))
            except (ValueError, OSError, sqlite3.Error) as exc:
                messagebox.showerror('공간 분석 조회 실패', str(exc), parent=self.window)
        self.recompute()

    def apply_thresholds(self):
        try:
            rssi, quality = float(self.rssi_input.get()), float(self.quality_input.get())
            if not finite(rssi, -128, 0) or not finite(quality, 0, 100):
                raise ValueError
        except ValueError:
            messagebox.showwarning('음영 기준 확인', 'RSSI는 -128~0 dBm, 품질은 0~100점을 입력하세요.',
                                   parent=self.window)
            return
        self.rssi_limit, self.quality_limit = rssi, quality
        self.recompute()

    def recompute(self):
        self.coverage = None
        if self.active_space:
            width, height = self.active_space['width'], self.active_space['height']
            self.inferred = not width or not height
            self.width = width or max((point.x for point in self.points), default=0) or 1
            self.height = height or max((point.y for point in self.points), default=0) or 1
            self.coverage = estimate_coverage(self.points, self.width, self.height,
                                              self.rssi_limit, self.quality_limit)
        previous = next(iter(self.table.selection()), '')
        self.table.delete(*self.table.get_children())
        for point in self.points:
            averages = [f'{point.averages[key]:.1f}' if key in point.averages else '—' for key in METRICS]
            weak = is_low(point.averages, self.rssi_limit, self.quality_limit)
            self.table.insert('', 'end', iid=str(point.id), values=(point.name, *averages),
                              tags=('weak',) if weak else ())
        if self.table.exists(previous):
            self.table.selection_set(previous)
        elif self.points:
            first = next((p for p in self.points if is_low(p.averages, self.rssi_limit, self.quality_limit)),
                         next((p for p in self.points if p.averages), self.points[0]))
            self.table.selection_set(str(first.id))
        self.select_point()

    def select_point(self):
        selected = next(iter(self.table.selection()), '')
        point = next((point for point in self.points if str(point.id) == selected), None)
        advice = placement_advice(self.points, self.rssi_limit)
        lines = []
        if point:
            unit = self.active_space['coordinate_unit']
            lines.append(f'{point.name} · ({point.x:g}, {point.y:g}) {unit}')
            radio = [f"{band or '대역 미확인'} / 채널 {channel or '미확인'}" for band, channel in point.radio]
            if radio:
                lines.append(' · '.join(radio))
            readings = {'rssi': ('RSSI', 'dBm'), 'quality': ('품질', '점'),
                        'gateway_ping': ('게이트웨이 Ping', 'ms'), 'gateway_loss': ('게이트웨이 손실', '%'),
                        'external_ping': ('외부 Ping', 'ms'), 'external_loss': ('외부 손실', '%')}
            lines.extend(f'{label} {point.averages[key]:.1f} {unit} ({point.counts[key]}회)'
                         for key, (label, unit) in readings.items() if key in point.averages)
            source_labels = {'native_wifi': '드라이버 조회', 'estimated_from_signal': '신호 % 환산 추정'}
            if point.rssi_sources:
                sources = ', '.join(source_labels.get(source, '미확인') for source in point.rssi_sources)
                lines.append(f'RSSI 출처 · {sources}')
            lines.append('')
            lines.extend(f'• {finding}' for finding in diagnose(point, self.rssi_limit, self.quality_limit))
        else:
            lines.append('공간 / 지점 선택에서 측정 지점을 등록하세요.')
        if advice:
            lines.extend(('', 'AP 배치', advice))
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', '\n'.join(lines))
        self.details.configure(state='disabled')
        self.draw_map()

    def draw_map(self):
        canvas = self.canvas
        canvas.delete('all')
        if self.coverage is None or not self.points:
            canvas.create_text(max(canvas.winfo_width(), 500) / 2, 180,
                               text='공간 / 지점 선택에서 먼저 측정 지점을 등록하세요.')
            self.summary.configure(text='')
            return
        metric = list(METRICS)[self.metric.current()]
        label, unit, worst, best = METRICS[metric]
        grid = self.coverage
        canvas_width, canvas_height = max(canvas.winfo_width(), 470), max(canvas.winfo_height(), 360)
        aspect = max(self.width, self.height)
        scale = min(canvas_width - 78, canvas_height - 93)
        width, height = self.width / aspect * scale, self.height / aspect * scale
        left, top = (canvas_width - width) / 2, 30 + (canvas_height - 85 - height) / 2
        dx, dy = width / grid.columns, height / grid.rows
        canvas.create_rectangle(left, top, left + width, top + height, fill='#e1e6ec', outline='')
        for (column, row), value in grid.values[metric].items():
            x, y = left + column * dx, top + row * dy
            canvas.create_rectangle(x, y, x + dx, y + dy, fill=_color(value, worst, best), width=0)
        for region in grid.regions:
            for column, row in region:
                x, y = left + column * dx, top + row * dy
                for neighbor, edge in (((column - 1, row), (x, y, x, y + dy)),
                                       ((column + 1, row), (x + dx, y, x + dx, y + dy)),
                                       ((column, row - 1), (x, y, x + dx, y)),
                                       ((column, row + 1), (x, y + dy, x + dx, y + dy))):
                    if neighbor not in region:
                        canvas.create_line(*edge, fill='#772457', width=2, tags='weak_edge')
        selected = self.table.selection()
        for point in self.points:
            x, y = left + point.x / self.width * width, top + point.y / self.height * height
            value = point.averages.get(metric)
            weak = is_low(point.averages, self.rssi_limit, self.quality_limit)
            tag = f'p{point.id}'
            canvas.create_oval(x - 6, y - 6, x + 6, y + 6,
                               fill=_color(value, worst, best) if value is not None else 'white',
                               outline='#772457' if weak else '#202c3c',
                               width=3 if weak or str(point.id) in selected else 1, tags=tag)
            if str(point.id) in selected:
                canvas.create_oval(x - 10, y - 10, x + 10, y + 10, outline='#202c3c', tags=tag)
            canvas.tag_bind(tag, '<Button-1>', lambda _, key=str(point.id): self.select_from_map(key))
        dim = self.active_space['coordinate_unit']
        suffix = ' · 지점 좌표 기준 범위' if self.inferred else ''
        canvas.create_text(12, 14, anchor='w', text=f'{label} · {self.width:g} × {self.height:g} {dim}{suffix}')
        y = canvas_height - 21
        for step in range(40):
            x = 133 + step * 4
            canvas.create_rectangle(x, y - 6, x + 4, y + 6,
                                    fill=_color(worst + (best - worst) * step / 39, worst, best), width=0)
        canvas.create_text(126, y, anchor='e', text=f'{worst:g} {unit}')
        canvas.create_text(301, y, anchor='w', text=f'{best:g} {unit}')
        canvas.create_text(canvas_width - 9, y, anchor='e', fill='#772457', text='보라색 테두리 · 음영')

        low = sum(map(len, grid.regions))
        assessed_points = [point for point in self.points if {'rssi', 'quality'} & point.averages.keys()]
        weak_points = sum(is_low(point.averages, self.rssi_limit, self.quality_limit) for point in assessed_points)
        point_summary = f'기준 미만 지점 {weak_points}/{len(assessed_points)}'
        if grid.assessed:
            footprint = grid.assessed / (grid.columns * grid.rows)
            largest = len(grid.regions[0]) / grid.assessed if grid.regions else 0
            summary = (f'{point_summary} · 추정 음영 {low / grid.assessed:.1%} (판정 영역 기준)\n'
                       f'연속 음영 {len(grid.regions)}곳 · 가장 큰 영역 {largest:.1%} · 전체의 {footprint:.1%} 판정')
        else:
            summary = f'{point_summary} · RSSI 또는 품질을 일직선 밖의 세 지점 이상에서 측정하세요.'
        if not grid.values[metric]:
            summary += f'\n{label} 보간이 가능한 범위가 없어 유효한 측정 지점만 색으로 표시합니다.'
        else:
            summary += '\n회색은 이 지표의 보간 범위 밖입니다. 점을 눌러 실측 평균을 확인하세요.'
        self.summary.configure(text=summary)

    def select_from_map(self, key):
        self.table.selection_set(key)
        self.table.see(key)
