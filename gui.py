"""Tk front end for the shared periodic Wi-Fi collector."""
import datetime
import json
import queue
import time
from collections import deque
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import matplotlib.pyplot as plt
import numpy as np
from wifi_optimizer.collector import CollectorConfig, WiFiCollector
from wifi_optimizer.visualization.dashboard import Dashboard
from wifi_optimizer.visualization.graphs import RealTimeGraphs


class WifiMonitorApp:
    def __init__(self, root, auto_start=True):
        self.root = root
        root.title("Wi-Fi 품질 모니터링")
        root.geometry("1000x960")
        root.minsize(950, 880)
        self.collector = None
        self.closing = self.stopping = False
        self.last_quality = self.connection_key = None
        self.started_at = time.monotonic()
        self.x_data, self.y_data = deque(maxlen=100), deque(maxlen=100)
        self.interface = tk.StringVar()
        self.target = tk.StringVar(value="1.1.1.1")
        self.interval = tk.StringVar(value="5")
        self.status = tk.StringVar(value="측정 대기")
        self.connection = tk.StringVar(value="연결 정보 대기")
        self.quality = tk.StringVar(value="Ping / 손실 측정 대기")
        self.storage_status = tk.StringVar(value="측정 결과는 로컬 DB에 자동 저장됩니다.")
        settings = ttk.Frame(root, padding=10)
        settings.pack()
        self.entries = []
        for col, (label, variable) in enumerate([
            ("인터페이스 (빈칸: 자동)", self.interface),
            ("외부 Ping IPv4", self.target), ("측정 후 대기 (초)", self.interval),
        ]):
            ttk.Label(settings, text=label).grid(row=0, column=col, padx=8)
            entry = ttk.Entry(settings, textvariable=variable, width=22)
            entry.grid(row=1, column=col, padx=8)
            self.entries.append(entry)
        controls = ttk.Frame(root)
        controls.pack()
        self.start_btn = ttk.Button(controls, text="자동 측정 시작", command=self.start)
        self.stop_btn = ttk.Button(controls, text="중지", command=self.stop, state="disabled")
        self.speed_btn = ttk.Button(controls, text="속도 포함 1회 예약 (약 12 MB)",
                                    command=self.request_speed, state="disabled")
        for button in (self.start_btn, self.stop_btn, self.speed_btn):
            button.pack(side="left", padx=5)
        ttk.Label(root, textvariable=self.status, wraplength=920).pack(pady=5)
        ttk.Label(root, textvariable=self.storage_status, wraplength=920).pack()
        self.dashboard = Dashboard(root)
        self.dashboard.pack(fill="x", padx=10, pady=6)
        plt.rc("font", family="Malgun Gothic")
        plt.rcParams["axes.unicode_minus"] = False
        self.graphs = RealTimeGraphs(root)
        self.graphs.pack(fill="both", expand=True)
        self.fig = self.graphs.fig
        ttk.Label(root, textvariable=self.quality, justify="left", wraplength=920).pack(pady=8)
        ttk.Label(root, text="속도는 단일 HTTPS 처리량 · 중지 시 진행 중인 단계의 종료를 기다립니다.").pack()
        footer = ttk.Frame(root, padding=8)
        footer.pack()
        for label, callback in [("최근 결과 JSON 저장", self.save_quality),
                                ("저장 기록 조회", self.show_history),
                                ("신호 요약 저장", self.save_report), ("신호 추세", self.analyze_trend)]:
            ttk.Button(footer, text=label, command=callback).pack(side="left", padx=5)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.timer = root.after(100, self.poll)
        if auto_start:
            root.after(0, self.start)

    def start(self):
        if self.closing or (self.collector and self.collector.running):
            return
        try:
            config = CollectorConfig(self.interface.get().strip() or None, self.target.get().strip(),
                                     4, float(self.interval.get()))
            if self.collector and (self.collector.config != config or self.collector.closing):
                if not self.collector.close():
                    self.status.set("이전 세션 저장 마무리 중 · 잠시 후 다시 시작해 주세요.")
                    return
                self.collector = None
                self.graphs.history.clear()
                self.x_data.clear()
                self.y_data.clear()
                self.connection_key = None
                self.graphs.draw()
            if self.collector is None:
                self.collector = WiFiCollector(config)
            self.collector.start()
        except (ValueError, OSError) as exc:
            self.status.set(f"시작 실패: {exc}")
            return
        self.stopping = False
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.speed_btn.config(state="normal")
        for entry in self.entries:
            entry.config(state="disabled")
        self.status.set("자동 측정 시작 · Wi-Fi / Ping / 손실 수집 중")

    def stop(self):
        if self.collector:
            self.stopping = True
            self.collector.stop()
            self.stop_btn.config(state="disabled")
            self.speed_btn.config(state="disabled")
            self.status.set("중지 요청됨 · 진행 중인 단계 종료 대기")

    def request_speed(self):
        if self.collector and self.collector.request_speed():
            self.status.set("속도 포함 1회 측정 예약됨 · 현재 측정 뒤 실행")
        else:
            self.status.set("이미 예약됐거나 자동 측정이 중지되어 있습니다.")

    @staticmethod
    def display(value):
        return "측정 불가" if value is None else f"{value:.2f}"

    def show_result(self, result):
        self.last_quality = result
        self.dashboard.show_result(result)
        storage = result.get("storage", {})
        if storage.get("status") == "saved":
            self.storage_status.set(f"DB 저장 완료 · 기록 #{storage['measurement_id']}")
        else:
            self.storage_status.set(f"DB 저장 실패 · {storage.get('error', '저장 상태 확인 불가')}")
        self.status.set(f"#{result['sequence']} · {result['status']} · "
                        f"소요 {result['duration_seconds']:.1f}초")
        self.graphs.show_result(result, time.monotonic() - self.started_at)
        wifi = result.get("wifi")
        if wifi:
            key = (wifi["interface"], wifi["bssid"], wifi["ssid"], wifi["band"])
            if key != self.connection_key:
                self.x_data.clear()
                self.y_data.clear()
                self.connection_key = key
            source = "드라이버 실측" if wifi["rssi_source"] == "native_wifi" else "추정/미확인"
            self.connection.set(
                f"{wifi['interface']} | SSID: {wifi['ssid']} | BSSID: {wifi['bssid']}\n"
                f"RSSI: {self.display(wifi['rssi_dbm'])} dBm ({source}) | "
                f"채널: {wifi['channel']} | 대역: {wifi['band']} | 신호: {wifi['signal_percent']}%"
            )
            if wifi["signal_percent"] is not None:
                self.x_data.append(time.monotonic() - self.started_at)
                self.y_data.append(wifi["signal_percent"])
        else:
            self.connection.set("현재 연결 정보 확인 불가 · 그래프는 이전 측정 기록")
        lines = []
        for name, value in result.get("ping", {}).items():
            lines.append(f"{name}: 평균 {self.display(value.get('avg_ms'))} ms / "
                         f"최소 {self.display(value.get('min_ms'))} / 최대 {self.display(value.get('max_ms'))} / "
                         f"손실 {self.display(value.get('packet_loss_percent'))}% [{value['status']}]")
            if value.get("error"):
                lines.append(value["error"])
        speed = result.get("speed", {})
        if speed.get("status") != "not_requested":
            lines.append(f"다운로드 {self.display(speed.get('download', {}).get('mbps'))} Mbps / "
                         f"업로드 {self.display(speed.get('upload', {}).get('mbps'))} Mbps [{speed.get('status')}]")
            for direction in ("download", "upload"):
                if speed.get(direction, {}).get("error"):
                    lines.append(f"{direction}: {speed[direction]['error']}")
        else:
            lines.append("속도: 이번 주기에는 측정하지 않음 (수동 예약 가능)")
        if result.get("error"):
            lines.append(result["error"])
        lines.extend(result.get("warnings", []))
        self.quality.set("\n".join(lines))

    def poll(self):
        if self.collector:
            while True:
                try:
                    self.show_result(self.collector.results.get_nowait())
                except queue.Empty:
                    break
            if self.collector.storage_failures:
                self.storage_status.set(
                    f"DB 저장 오류 누적 {self.collector.storage_failures}회 · 일부 기록이 저장되지 않았을 수 있습니다. "
                    f"{self.collector.storage_error}")
            if not self.collector.running:
                self.start_btn.config(state="normal")
                self.stop_btn.config(state="disabled")
                self.speed_btn.config(state="disabled")
                for entry in self.entries:
                    entry.config(state="normal")
                if self.stopping:
                    self.status.set("측정 중지됨 · 표시된 값은 마지막 측정 기록")
            elif self.stopping:
                self.status.set("중지 요청됨 · 진행 중인 단계 종료 대기")
        if self.closing and (not self.collector or not self.collector.running):
            if self.collector:
                if not self.collector.close():
                    self.timer = self.root.after(200, self.poll)
                    return
                if self.collector.storage_failures:
                    messagebox.showwarning("DB 저장 오류", self.storage_status.get())
            plt.close(self.fig)
            self.root.destroy()
            return
        self.timer = self.root.after(200, self.poll)

    def close(self):
        self.closing = True
        self.stop()

    def save_quality(self):
        if self.last_quality is None:
            messagebox.showinfo("저장 불가", "완료된 측정이 없습니다.")
            return
        self.save_text(json.dumps(self.last_quality, ensure_ascii=False, indent=2), ".json")

    def show_history(self):
        from wifi_optimizer.visualization.history import HistoryWindow
        from wifi_optimizer.storage import DEFAULT_DB_PATH
        existing = getattr(self, 'history_window', None)
        if existing is not None and existing.window.winfo_exists():
            existing.window.lift()
            return
        self.history_window = HistoryWindow(
            self.root, self.collector.db_path if self.collector else DEFAULT_DB_PATH)

    def save_text(self, text, extension):
        path = filedialog.asksaveasfilename(defaultextension=extension)
        if path:
            try:
                with open(path, "w", encoding="utf-8") as output:
                    output.write(text)
            except OSError as exc:
                messagebox.showerror("저장 실패", str(exc))

    def save_report(self):
        if not self.y_data:
            messagebox.showinfo("저장 불가", "신호 표본이 없습니다.")
            return
        self.save_text(f"최근 {len(self.y_data)}개 표본\n평균: {np.mean(self.y_data):.2f}%\n"
                       f"최소: {min(self.y_data)}%\n최대: {max(self.y_data)}%\n", ".txt")

    def analyze_trend(self):
        if len(self.y_data) < 2:
            messagebox.showinfo("분석 불가", "표본 2개 이상이 필요합니다.")
            return
        slope = np.polyfit(self.x_data, self.y_data, 1)[0]
        messagebox.showinfo("신호 추세", f"최근 신호 변화: {slope:.3f} %/초")


def main():
    root = tk.Tk()
    WifiMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
