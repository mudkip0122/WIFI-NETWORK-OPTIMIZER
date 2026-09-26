"""One manual quality measurement combining Wi-Fi, ICMP and optional throughput."""
import ipaddress
import subprocess
from datetime import datetime, timezone

from .collectors.wifi import collect_wifi
from .collectors.signal import WifiMeasurementError
from .collectors.network import interface_network
from .collectors.ping import measure_ping
from .collectors.speed import measure_speed


def measure_quality(interface=None, target="1.1.1.1", count=4, include_speed=False, *, stop_event=None):
    target = str(ipaddress.IPv4Address(target))
    if not 1 <= count <= 20:
        raise ValueError("Ping count must be 1..20")
    result = {"started_at": datetime.now(timezone.utc).isoformat(),
              "wifi": None, "ping": {}, "speed": {"status": "not_requested"},
              "status": "ok", "warnings": []}
    def cancelled():
        if stop_event is not None and stop_event.is_set():
            result["status"] = "cancelled"
            result["finished_at"] = datetime.now(timezone.utc).isoformat()
            return True
        return False
    try:
        if cancelled():
            return result
        wifi = collect_wifi(interface)
        result["wifi"] = wifi.to_dict()
        if cancelled():
            return result
        network = interface_network(wifi.interface)
        result["network"] = network
        gateway = network["gateway"]
        if cancelled():
            return result
        result["ping"]["gateway"] = (measure_ping(gateway, network["source_ip"], count)
                                     if gateway else {"status": "unavailable", "error": "No IPv4 gateway"})
        if cancelled():
            return result
        result["ping"]["external"] = measure_ping(target, network["source_ip"], count)
        if cancelled():
            return result
        if include_speed:
            result["speed"] = measure_speed(network["source_ip"])
        if cancelled():
            return result
        after = collect_wifi(wifi.interface)
        if (wifi.bssid, wifi.ssid, wifi.band) != (after.bssid, after.ssid, after.band):
            result["warnings"].append("측정 중 Wi-Fi 연결이 변경됐습니다. 결과를 다시 측정하세요.")
        statuses = [x["status"] for x in result["ping"].values()]
        if include_speed:
            statuses.append(result["speed"]["status"])
        if result["warnings"] or any(s != "ok" for s in statuses):
            result["status"] = "partial"
    except (WifiMeasurementError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["status"] = "partial" if result["wifi"] else "error"
        result["error"] = str(exc)
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result
