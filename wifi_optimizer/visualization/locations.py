"""Space and point management, with explicit coordinates in metres."""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..storage import MeasurementStore


class LocationWindow:
    def __init__(self, parent, db_path, select):
        self.db_path, self.select = db_path, select
        self.window = tk.Toplevel(parent)
        self.window.title('공간별 측정 위치 · 좌표 단위 m')
        self.window.geometry('900x850')
        self.space = ttk.Combobox(self.window, state='readonly', width=40)
        self.space.pack(pady=8)
        self.space.bind('<<ComboboxSelected>>', lambda _: self.refresh())
        controls = ttk.Frame(self.window)
        controls.pack()
        for label, action in [('내 방 3.6 × 3.6 m', self.use_room),
                              ('공간 추가', self.add_space), ('지점 추가', self.add_point),
                              ('평균 새로고침', self.refresh), ('선택 지점 적용', self.apply)]:
            ttk.Button(controls, text=label, command=action).pack(side='left', padx=4)
        ttk.Label(self.window, text='좌측 상단 (0, 0) 기준 · x는 오른쪽, y는 아래쪽 거리(m)\n'
                  '평균은 실제 기록만 포함 · Ping/손실은 외부 대상 · 실패/미측정 값 제외').pack(pady=8)
        self.canvas = tk.Canvas(self.window, width=460, height=440, bg='white',
                                highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind('<Button-1>', self.click_plan)
        self.table_points = {}
        columns = ('name', 'x', 'y', 'samples', 'rssi', 'ping', 'loss')
        self.table = ttk.Treeview(self.window, columns=columns, show='headings')
        for key, label in zip(columns, ['지점', 'x(m)', 'y(m)', '기록 수', 'RSSI 평균(표본)',
                                       'Ping 평균(표본)', '손실 평균 %']):
            self.table.heading(key, text=label)
            self.table.column(key, width=110)
        self.table.pack(fill='both', expand=True, padx=8, pady=8)
        self.table.bind('<<TreeviewSelect>>', lambda _: self.draw_plan())
        self.reload_spaces()

    def use_room(self):
        """Reuse the room on repeated presses without changing other spaces."""
        def ensure(store):
            for space in store.list_spaces():
                if (space['name'], space['width'], space['height'], space['coordinate_unit']) == (
                        '내 방', 3.6, 3.6, 'm'):
                    return space['id']
            return store.create_space('내 방', width=3.6, height=3.6)
        room_id = self.run(ensure)
        self.reload_spaces()
        for index, space in enumerate(self.spaces):
            if space['id'] == room_id:
                self.space.current(index)
                self.refresh()
                break

    def plan_geometry(self):
        space = self.current_space()
        if not space or space['coordinate_unit'] != 'm' or not space['width'] or not space['height']:
            return None
        scale = min(360 / space['width'], 360 / space['height'])
        return 50, 40, space['width'] * scale, space['height'] * scale, scale

    def draw_plan(self):
        self.canvas.delete('all')
        geometry = self.plan_geometry()
        if geometry is None:
            self.canvas.create_text(230, 200, text='크기가 등록된 공간에서 평면도를 표시합니다.\n'
                                    '위의 「내 방 3.6 × 3.6 m」를 누르세요.')
            return
        left, top, width, height, scale = geometry
        space = self.current_space()
        for axis, length in [('x', space['width']), ('y', space['height'])]:
            steps = min(int(length / 0.6), 100)
            for step in range(steps + 1):
                offset = step * 0.6 * scale
                if axis == 'x':
                    self.canvas.create_line(left + offset, top, left + offset, top + height,
                                            fill='#cdd9e7', dash=(4, 4))
                else:
                    self.canvas.create_line(left, top + offset, left + width, top + offset,
                                            fill='#cdd9e7', dash=(4, 4))
        self.canvas.create_rectangle(left, top, left + width, top + height, width=3)
        self.canvas.create_text(left, top - 15, anchor='w', text='(0, 0) · x → / y ↓')
        self.canvas.create_text(left + width / 2, top + height + 18,
                                text=f"{space['width']:g} m × {space['height']:g} m · 클릭하여 지점 추가")
        selected = self.table.selection()
        for point in self.table_points.values():
            x, y = left + point['x'] * scale, top + point['y'] * scale
            color = '#e16b20' if str(point['id']) in selected else '#167dba'
            self.canvas.create_oval(x-6, y-6, x+6, y+6, fill=color, outline='white')
            self.canvas.create_text(x, y-14, text=point['name'], fill=color)

    def click_plan(self, event):
        geometry = self.plan_geometry()
        if geometry is None:
            return
        left, top, width, height, scale = geometry
        if not (left <= event.x <= left + width and top <= event.y <= top + height):
            return
        for point in self.table_points.values():
            if ((event.x-left-point['x']*scale)**2 +
                    (event.y-top-point['y']*scale)**2) <= 100:
                self.table.selection_set(str(point['id']))
                self.table.see(str(point['id']))
                self.draw_plan()
                return
        x, y = round((event.x-left)/scale, 2), round((event.y-top)/scale, 2)
        name = simpledialog.askstring('측정 지점 추가',
                                      f'좌표 ({x}, {y}) m · 지점 이름', parent=self.window)
        if name is None:
            return
        point_id = self.run(lambda store: store.create_location(
            self.current_space()['id'], name.strip(), x=x, y=y))
        self.refresh()
        if point_id is not None:
            self.table.selection_set(str(point_id))
            self.draw_plan()

    def run(self, action):
        try:
            with MeasurementStore(self.db_path) as store:
                return action(store)
        except (ValueError, OSError, sqlite3.Error) as exc:
            messagebox.showerror('공간 작업 실패', str(exc), parent=self.window)

    def reload_spaces(self):
        self.spaces = self.run(lambda store: store.list_spaces()) or []
        self.space['values'] = [f"{s['id']} · {s['name']} ({s['coordinate_unit']})" for s in self.spaces]
        if self.spaces:
            self.space.current(len(self.spaces) - 1)
        self.refresh()

    def current_space(self):
        index = self.space.current()
        return self.spaces[index] if index >= 0 else None

    def add_space(self):
        name = simpledialog.askstring('공간 추가', '공간 이름', parent=self.window)
        if name is None:
            return
        self.run(lambda store: store.create_space(name.strip()))
        self.reload_spaces()

    def add_point(self):
        space = self.current_space()
        if not space:
            return
        name = simpledialog.askstring('지점 추가', '지점 이름 (예: 출입문)', parent=self.window)
        if name is None:
            return
        x = simpledialog.askfloat('지점 좌표', 'x (m)', minvalue=0, parent=self.window)
        if x is None:
            return
        y = simpledialog.askfloat('지점 좌표', 'y (m)', minvalue=0, parent=self.window)
        if y is None:
            return
        self.run(lambda store: store.create_location(space['id'], name.strip(), x=x, y=y))
        self.refresh()

    def refresh(self):
        self.table.delete(*self.table.get_children())
        self.table_points = {}
        space = self.current_space()
        if not space:
            self.draw_plan()
            return
        rows = self.run(lambda store: store.location_averages(space['id'])) or []
        self.table_points = {row['id']: row for row in rows}
        def number(value):
            return '—' if value is None else f'{value:.2f}'
        for row in rows:
            self.table.insert('', 'end', iid=str(row['id']), values=(
                row['name'], row['x'], row['y'], row['samples'],
                f"{number(row['rssi_dbm'])} ({row['rssi_samples']})",
                f"{number(row['ping_avg_ms'])} ({row['ping_samples']})",
                number(row['packet_loss_percent'])))
        self.draw_plan()

    def apply(self):
        selected = self.table.selection()
        if selected:
            point = self.run(lambda store: store.get_location(int(selected[0])))
            if point and self.select(point):
                self.window.destroy()
