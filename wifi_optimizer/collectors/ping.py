"""ICMP measurements bound to a Wi-Fi source address with bounded requests."""
import ipaddress
import statistics
from datetime import datetime, timezone

from .icmp import send_probes


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def summarize_ping(samples: list[dict]) -> dict:
    # Send exceptions are not evidence that a packet left the device.
    sent = [s for s in samples if s["status"] != "send_error"]
    received = [float(s["rtt_ms"]) for s in sent if s["status"] == "Success"]
    errors = len(samples) - len(sent)
    status = ("error" if not sent else "partial" if errors else
              "no_reply" if not received else "ok")
    return {
        "status": status, "attempted": len(samples), "sent": len(sent),
        "received": len(received), "send_errors": errors,
        "packet_loss_percent": 100 * (len(sent) - len(received)) / len(sent) if sent else None,
        "min_ms": min(received) if received else None,
        "avg_ms": statistics.mean(received) if received else None,
        "max_ms": max(received) if received else None,
        "samples": samples,
    }


def measure_ping(target: str, source_ip: str, count: int = 4,
                 timeout_ms: int = 1000) -> dict:
    target = str(ipaddress.IPv4Address(target))
    source_ip = str(ipaddress.IPv4Address(source_ip))
    if not 1 <= count <= 20 or not 100 <= timeout_ms <= 5000:
        raise ValueError("count must be 1..20 and timeout_ms 100..5000")
    start = utc_now()
    base = {"target": target, "source_ip": source_ip,
            "started_at": start, "timeout_ms": timeout_ms}
    try:
        result = summarize_ping(send_probes(target, source_ip, count, timeout_ms))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = summarize_ping([])
        result.update(status="error", error=str(exc))
    return {**base, **result, "finished_at": utc_now()}
