"""Serial periodic Wi-Fi collection with lifecycle control and bounded result queue."""
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import logging
from logging.handlers import RotatingFileHandler
import math
from pathlib import Path
import queue
import threading
import time
import uuid

from .measurement import measure_quality


@dataclass(frozen=True)
class CollectorConfig:
    interface: str | None = None
    target: str = "1.1.1.1"
    count: int = 4
    interval: float = 5.0

    def __post_init__(self):
        ipaddress.IPv4Address(self.target)
        if not isinstance(self.count, int) or not 1 <= self.count <= 20:
            raise ValueError("Ping 횟수는 1~20이어야 합니다.")
        if not math.isfinite(self.interval) or self.interval < 1:
            raise ValueError("측정 간격은 1초 이상의 유한한 값이어야 합니다.")


class WiFiCollector:
    """One worker; interval is idle time after each finished measurement.

    stop() prevents new measurements and requests cooperative stage cancellation.
    running remains True until the in-flight bounded operation has returned.
    """

    def __init__(self, config=None, *, log_dir="logs", measure=None, queue_size=100):
        self.config = config or CollectorConfig()
        self._measure = measure or measure_quality
        self.results = queue.Queue(maxsize=queue_size)
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self._busy = False
        self._manual_speed = False
        self._closed = False
        self.sequence = 0
        self.dropped_results = 0
        self.logger = logging.getLogger(f"wifi_collector.{uuid.uuid4().hex}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        self._handler = RotatingFileHandler(
            Path(log_dir) / f"collector-{uuid.uuid4().hex[:8]}.log",
            maxBytes=1_000_000, backupCount=3, encoding="utf-8",
        )
        self._handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(self._handler)

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def busy(self):
        with self._lock:
            return self._busy

    def start(self, *, max_samples=None):
        with self._lock:
            if self._closed:
                raise RuntimeError("Collector is closed")
            if self.running:
                return False
            if max_samples is not None and (not isinstance(max_samples, int) or max_samples < 1):
                raise ValueError("max_samples must be positive")
            self._stop.clear()
            self._wake.clear()
            self._manual_speed = False
            self._thread = threading.Thread(target=self._run, args=(max_samples,),
                                            name="wifi-collector", daemon=False)
            self._thread.start()
            return True

    def request_speed(self):
        """Queue one speed-inclusive cycle after the current cycle, without overlap."""
        with self._lock:
            if not self.running or self._stop.is_set() or self._manual_speed:
                return False
            self._manual_speed = True
            self._wake.set()
            return True

    def stop(self, timeout=0):
        with self._lock:
            self._stop.set()
            self._wake.set()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        return not self.running

    def close(self, timeout=0):
        if not self.stop(timeout):
            return False
        with self._lock:
            self._closed = True
        self.logger.removeHandler(self._handler)
        self._handler.close()
        return True

    def _publish(self, result):
        while True:
            try:
                self.results.put_nowait(result)
                return
            except queue.Full:
                try:
                    self.results.get_nowait()
                    self.dropped_results += 1
                    self.logger.warning("result_queue_full dropped=%s", self.dropped_results)
                except queue.Empty:
                    pass

    def _run(self, max_samples):
        self.logger.info("started interval=%s count=%s", self.config.interval, self.config.count)
        completed = 0
        try:
            while not self._stop.is_set():
                with self._lock:
                    if self._stop.is_set():
                        break
                    speed = self._manual_speed
                    self._manual_speed = False
                    self._wake.clear()
                    self._busy = True
                started = time.monotonic()
                try:
                    result = self._measure(
                        self.config.interface, self.config.target, self.config.count, speed,
                        stop_event=self._stop,
                    )
                except Exception as exc:
                    now = datetime.now(timezone.utc).isoformat()
                    result = {"status": "error", "error": str(exc), "wifi": None,
                              "ping": {}, "speed": {"status": "not_requested"},
                              "warnings": [], "started_at": now, "finished_at": now}
                    self.logger.error("measurement_exception type=%s", type(exc).__name__)
                finally:
                    with self._lock:
                        self._busy = False
                self.sequence += 1
                completed += 1
                result["sequence"] = self.sequence
                result["duration_seconds"] = round(time.monotonic() - started, 3)
                self._publish(result)
                self.logger.info("measurement sequence=%s status=%s seconds=%s speed=%s",
                                 self.sequence, result.get("status"), result["duration_seconds"], speed)
                if max_samples is not None and completed >= max_samples:
                    break
                self._wake.wait(self.config.interval)
        finally:
            self.logger.info("stopped measurements=%s", completed)
