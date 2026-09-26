"""Week 2 connected-interface collection, with explicit RSSI provenance."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import re

from .native import query_rssi
from .signal import WifiMeasurementError, run_netsh


@dataclass
class WifiInfo:
    interface: str
    state: str = "unknown"
    guid: str | None = None
    description: str | None = None
    ssid: str | None = None
    bssid: str | None = None
    signal_percent: int | None = None
    rssi_dbm: float | None = None
    rssi_source: str = "unavailable"
    channel: int | None = None
    band: str | None = None
    timestamp: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


KEYS = {
    "name": "interface", "이름": "interface",
    "description": "description", "설명": "description", "guid": "guid",
    "state": "state", "상태": "state", "ssid": "ssid",
    "bssid": "bssid", "ap bssid": "bssid",
    "signal": "signal_percent", "신호": "signal_percent",
    "channel": "channel", "채널": "channel", "band": "band", "밴드": "band",
}


def parse_interfaces(output: str) -> list[WifiInfo]:
    rows, current = [], None
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = KEYS.get(key.strip().casefold())
        value = value.strip()
        if key == "interface":
            current = WifiInfo(interface=value)
            rows.append(current)
        elif current is not None and key:
            if key in ("signal_percent", "channel"):
                pattern = r"(\d+)\s*%" if key == "signal_percent" else r"(\d+)"
                match = re.fullmatch(pattern, value)
                number = int(match[1]) if match else None
                if number is not None and (0 <= number <= 100 if key == "signal_percent"
                                           else 1 <= number <= 233):
                    setattr(current, key, number)
            elif key == "band":
                match = re.fullmatch(r"(2\.4|5|6)\s*GHz", value, re.I)
                current.band = f"{match[1]} GHz" if match else None
            elif key == "state":
                current.state = {"connected": "connected", "연결됨": "connected",
                                 "disconnected": "disconnected", "연결 끊김": "disconnected",
                                 "연결되지 않음": "disconnected"}.get(
                                     value.casefold(), "unknown")
            elif key == "bssid":
                if re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", value, re.I):
                    current.bssid = value.lower()
            else:
                setattr(current, key, value or None)
    for row in rows:
        if row.state != "connected":
            row.ssid = row.bssid = None
            row.signal_percent = row.channel = row.band = None
    return rows


def collect_wifi(interface: str | None = None) -> WifiInfo:
    rows = parse_interfaces(run_netsh())
    if not rows:
        raise WifiMeasurementError("무선 인터페이스가 없거나 출력 형식을 인식하지 못했습니다.",
                                   "unavailable")
    if interface:
        candidates = [row for row in rows if row.interface.casefold() == interface.casefold()]
        if not candidates:
            raise WifiMeasurementError(f"인터페이스를 찾을 수 없습니다: {interface}", "not_found")
    else:
        candidates = [row for row in rows if row.state == "connected"]
        if len(candidates) > 1:
            raise WifiMeasurementError("연결된 Wi-Fi가 여러 개입니다. --interface로 선택하세요.",
                                       "ambiguous_interface")
        if not candidates:
            if any(row.state == "unknown" for row in rows):
                raise WifiMeasurementError("인터페이스 상태를 해석할 수 없습니다.", "unavailable")
            raise WifiMeasurementError("연결된 Wi-Fi가 없습니다.", "disconnected")
    info = candidates[0]
    if info.state != "connected":
        raise WifiMeasurementError("선택한 Wi-Fi가 연결되어 있지 않습니다.", "disconnected")
    info.timestamp = datetime.now(timezone.utc).isoformat()
    if info.guid:
        try:
            info.rssi_dbm = query_rssi(info.guid)
            info.rssi_source = "native_wifi"
        except (OSError, ValueError) as exc:
            info.warnings.append(f"드라이버 RSSI 조회 불가: {exc}")
    if info.rssi_dbm is None and info.signal_percent is not None:
        info.rssi_dbm = info.signal_percent / 2 - 100
        info.rssi_source = "estimated_from_signal"
        info.warnings.append("RSSI는 신호 % 환산 추정값이며 0/100%에서 포화될 수 있습니다.")
    if info.band is None:
        info.warnings.append("주파수 대역을 확인할 수 없습니다. 채널 번호만으로 추정하지 않습니다.")
    for name in ("ssid", "bssid", "signal_percent", "channel"):
        if getattr(info, name) is None:
            info.warnings.append(f"측정 필드 누락: {name}")
    return info
