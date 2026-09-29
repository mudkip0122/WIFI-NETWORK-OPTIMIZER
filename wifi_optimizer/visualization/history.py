"""Read-only, asynchronous Tk history viewer."""

from datetime import datetime
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from ..storage import DEFAULT_DB_PATH, MeasurementStore


class HistoryWindow:
    def __init__(self, parent, db_path=DEFAULT_DB_PATH):
        self.window = tk.Toplevel(parent)
        self.window.title('저장된 Wi-Fi 측정 기록')
        self.window.geometry('1160x720')
        self.window.minsize(900, 600)
        self.db_path = db_path
        self.messages = queue.Queue()
        self.busy = False
        self.cursor = None
        self.filters = {}
        self.rows = []
        self.fields = {}
        filters = ttk.Frame(self.window, padding=10)
        filters.pack(fill='x')
        for column, (key, label) in enumerate([
            ('from_time', '시작 시각 (포함)'), ('to_time', '종료 시각 (미포함)'),
            ('bssid', 'BSSID'), ('location_id', '위치 ID'),
        ]):
            ttk.Label(filters, text=label).grid(row=0, column=column, sticky='w')
            variable = tk.StringVar()
            self.fields[key] = variable
            ttk.Entry(filters, textvariable=variable, width=28 if column < 2 else 20).grid(
                row=1, column=column, padx=(0, 8), sticky='ew')
            filters.columnconfigure(column, weight=1)
        self.kind = tk.StringVar(value='실측')
        ttk.Label(filters, text='데이터 종류').grid(row=0, column=4)
        ttk.Combobox(filters, textvariable=self.kind, values=['실측', '예제', '전체'],
                     state='readonly', width=8).grid(row=1, column=4)
        ttk.Label(filters, text='빈칸은 전체 · 시각 예: 2026-09-29T09:00:00+09:00 · '
                  '목록은 최신순 100개, 시각은 PC 현지 시간으로 표시').grid(
                      row=2, column=0, columnspan=5, sticky='w', pady=(6, 0))
        controls = ttk.Frame(self.window, padding=(10, 0))
        controls.pack(fill='x')
        self.refresh = ttk.Button(controls, text='조회 / 최신 기록', command=self.reload)
        self.refresh.pack(side='left')
        self.older = ttk.Button(controls, text='이전 기록 100개', command=self.load_older)
        self.older.pack(side='left', padx=8)
        self.status = tk.StringVar()
        ttk.Label(controls, textvariable=self.status).pack(side='left')
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill='both', expand=True)
        columns = ['id', 'time', 'kind', 'ssid', 'bssid', 'location', 'rssi', 'ping', 'loss', 'status']
        self.tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse')
        for key, title, width in zip(columns, ['ID', '측정 시각', '종류', 'SSID', 'BSSID', '위치',
                                              'RSSI (dBm)', '외부 Ping (ms)', '손실 (%)', '측정 상태'],
                                     [55, 175, 55, 120, 150, 90, 85, 100, 75, 90]):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=50)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=vertical.set)
        horizontal = ttk.Scrollbar(frame, orient='horizontal', command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.tree.configure(xscrollcommand=horizontal.set)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.tree.bind('<<TreeviewSelect>>', self.show_detail)
        ttk.Label(self.window, text='기록을 선택하면 저장 문맥과 전체 결과를 표시합니다. '
                  '— 는 미측정 값이며 0이 아닙니다.').pack(anchor='w', padx=10)
        self.detail = ScrolledText(self.window, height=13, wrap='word', state='disabled')
        self.detail.pack(fill='both', padx=10, pady=(4, 10))
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.timer = self.window.after(100, self.poll)
        self.reload()

    def set_detail(self, text):
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', text)
        self.detail.configure(state='disabled')

    def submit(self, action, arguments):
        if self.busy:
            return
        self.busy = True
        self.refresh.configure(state='disabled')
        self.older.configure(state='disabled')
        self.status.set('조회 중…')
        def worker():
            try:
                with MeasurementStore(self.db_path, readonly=True) as store:
                    value = (store.list_measurements(**arguments) if action == 'list'
                             else store.get_measurement(arguments))
                self.messages.put((action, value, None))
            except Exception as exc:
                self.messages.put((action, None, str(exc)))
        threading.Thread(target=worker, name='wifi-history', daemon=True).start()

    def reload(self):
        if self.busy:
            return
        arguments = {key: variable.get().strip() or None for key, variable in self.fields.items()}
        try:
            if arguments['location_id'] is not None:
                arguments['location_id'] = int(arguments['location_id'])
        except ValueError:
            self.status.set('위치 ID는 양의 정수로 입력해 주세요.')
            return
        arguments['data_kind'] = {'실측': 'real', '예제': 'example', '전체': None}[self.kind.get()]
        self.filters = arguments
        self.cursor = None
        self.submit('list', self.filters)

    def load_older(self):
        if self.cursor is not None:
            self.submit('list', dict(self.filters, before=self.cursor))

    def show_detail(self, event=None):
        selection = self.tree.selection()
        if selection and not self.busy:
            self.set_detail('상세 기록 조회 중…')
            self.submit('detail', int(selection[0]))

    def poll(self):
        try:
            action, value, error = self.messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.refresh.configure(state='normal')
            if error:
                self.status.set(f'조회 실패: {error}')
                self.set_detail('DB 파일과 조회 조건을 확인해 주세요. 아직 측정하지 않았다면 자동 측정을 먼저 실행하세요.')
                if action == 'list':
                    self.rows = []
                    self.cursor = None
                    self.tree.delete(*self.tree.get_children())
            elif action == 'list':
                self.rows = value
                self.tree.delete(*self.tree.get_children())
                for row in value:
                    def number(key):
                        return '—' if row[key] is None else f'{row[key]:.2f}'
                    self.tree.insert('', 'end', iid=str(row['id']), values=(
                        row['id'], datetime.fromisoformat(row['started_at']).astimezone().strftime('%Y-%m-%d %H:%M:%S'),
                        '실측' if row['data_kind'] == 'real' else '예제', row['ssid'] or '—',
                        row['bssid'] or '—', row['location_name'] or '미지정', number('rssi_dbm'),
                        number('ping_avg_ms'), number('packet_loss_percent'),
                        row['status'] + (' · 경고' if row['warnings'] else ''),
                    ))
                self.cursor = (value[-1]['started_at'], value[-1]['id']) if value else None
                self.status.set(f'{len(value)}개 기록' if value else '조건에 맞는 기록이 없습니다.')
                self.set_detail('목록에서 기록을 선택해 주세요.' if value else '표시할 기록이 없습니다.')
            else:
                self.status.set(f"기록 #{value['id']} 상세" if value else '기록을 찾을 수 없습니다.')
                self.set_detail(json.dumps(value, ensure_ascii=False, indent=2) if value else '')
            self.older.configure(state='normal' if len(self.rows) == 100 else 'disabled')
            # A user can select another row while the previous detail query is running.
            selection = self.tree.selection()
            if action == 'detail' and not error and value and selection and int(selection[0]) != value['id']:
                self.show_detail()
        self.timer = self.window.after(100, self.poll)

    def close(self):
        self.window.after_cancel(self.timer)
        self.window.destroy()
