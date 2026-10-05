"""Current-cycle dashboard. Missing readings never reuse earlier values."""
import datetime
from tkinter import ttk, StringVar


FIELDS = (
    ('ssid', 'SSID'), ('bssid', 'BSSID'), ('interface', '인터페이스'),
    ('rssi', 'RSSI'), ('signal', '신호'), ('channel', '채널'), ('band', '주파수 대역'),
    ('gateway_ping', '게이트웨이 Ping'), ('gateway_loss', '게이트웨이 손실'),
    ('external_ping', '외부 Ping'), ('external_loss', '외부 손실'),
    ('download', 'Download'), ('upload', 'Upload'),
)


def readings(result):
    values = dict.fromkeys((key for key, _ in FIELDS), '측정 불가')
    def number(value, unit):
        return '측정 불가' if value is None else f'{value:.2f} {unit}'
    wifi = result.get('wifi') or {}
    for key in ('ssid', 'bssid', 'interface', 'channel', 'band'):
        value = wifi.get(key)
        values[key] = str(value) if value is not None else '측정 불가'
    source = '드라이버 실측' if wifi.get('rssi_source') == 'native_wifi' else '추정/미확인'
    values['rssi'] = number(wifi.get('rssi_dbm'), 'dBm')
    if wifi.get('rssi_dbm') is not None:
        values['rssi'] += f' ({source})'
    values['signal'] = number(wifi.get('signal_percent'), '%')
    for target in ('gateway', 'external'):
        ping = result.get('ping', {}).get(target, {})
        values[f'{target}_ping'] = number(ping.get('avg_ms'), 'ms')
        values[f'{target}_loss'] = number(ping.get('packet_loss_percent'), '%')
    speed = result.get('speed') or {}
    for direction in ('download', 'upload'):
        part = speed.get(direction) or {}
        values[direction] = '이번 주기 미측정' if speed.get('status', 'not_requested') == 'not_requested' else (
            number(part.get('mbps'), 'Mbps') if part.get('status') == 'ok' else '측정 실패')
    return values


class Dashboard(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text='현재 Wi-Fi Dashboard', padding=10)
        self.values = {}
        self.updated = StringVar(master=self, value='완료된 측정 대기')
        ttk.Label(self, textvariable=self.updated).grid(row=0, column=0, columnspan=3, sticky='w')
        for index, (key, title) in enumerate(FIELDS):
            frame = ttk.Frame(self, padding=5)
            frame.grid(row=index // 3 + 1, column=index % 3, sticky='nsew', padx=3, pady=2)
            ttk.Label(frame, text=title).pack(anchor='w')
            variable = StringVar(master=self, value='측정 대기')
            self.values[key] = variable
            ttk.Label(frame, textvariable=variable, font=('Malgun Gothic', 10, 'bold'),
                      wraplength=280).pack(anchor='w')
        for col in range(3):
            self.columnconfigure(col, weight=1, uniform='metric')

    def show_result(self, result):
        for key, value in readings(result).items():
            self.values[key].set(value)
        stamp = result.get('finished_at')
        try:
            stamp = datetime.datetime.fromisoformat(stamp).astimezone().strftime('%Y-%m-%d %H:%M:%S')
        except (TypeError, ValueError):
            stamp = '시각 확인 불가'
        state = {'ok': '측정 완료', 'partial': '일부 측정 실패', 'error': '측정 실패',
                 'cancelled': '측정 취소'}.get(result.get('status'), '상태 확인 불가')
        self.updated.set(f'{state} · 마지막 완료 {stamp} · 아래 값은 이번 측정 결과')
