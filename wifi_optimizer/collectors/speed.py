"""Bounded single-connection HTTPS throughput; explicitly not peak line capacity."""
import http.client
import ipaddress
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

HOST = "speed.cloudflare.com"
DOWNLOAD_BYTES = 10_000_000
UPLOAD_BYTES = 2_000_000


def transfer(direction: str, source_ip: str, size: int) -> dict:
    connection = http.client.HTTPSConnection(
        HOST, timeout=15, source_address=(source_ip, 0)
    )
    started = time.perf_counter()
    try:
        headers = {"Cache-Control": "no-cache", "Accept-Encoding": "identity",
                   "User-Agent": "wifi-network-optimizer/0.1"}
        if direction == "download":
            connection.request("GET", f"/__down?bytes={size}", headers=headers)
        else:
            headers["Content-Type"] = "application/octet-stream"
            connection.request("POST", "/__up", body=b"0" * size, headers=headers)
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            raise OSError(f"HTTP {response.status}")
        received = 0
        while chunk := response.read(65536):
            received += len(chunk)
            if time.perf_counter() - started > 30:
                raise TimeoutError("Transfer deadline exceeded")
            if received > (size if direction == "download" else 1_000_000):
                raise OSError("Unexpected response size")
        if direction == "download" and received != size:
            raise OSError(f"Incomplete download: {received}/{size} bytes")
        seconds = time.perf_counter() - started
        return {"status": "ok", "mbps": size * 8 / seconds / 1_000_000,
                "bytes": size, "seconds": seconds,
                "server_location": response.getheader("cf-ray", "").rsplit("-", 1)[-1] or None}
    except (OSError, http.client.HTTPException) as exc:
        return {"status": "error", "mbps": None, "bytes": None,
                "seconds": None, "error": str(exc)}
    finally:
        connection.close()


def measure_speed(source_ip: str) -> dict:
    source_ip = str(ipaddress.IPv4Address(source_ip))
    started = datetime.now(timezone.utc).isoformat()
    try:
        process = subprocess.run(
            [sys.executable, "-m", "wifi_optimizer.collectors.speed", "--worker"],
            input=json.dumps({"source_ip": source_ip}), capture_output=True, text=True,
            timeout=75, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.returncode:
            raise OSError("Speed worker failed")
        result = json.loads(process.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {"status": "error", "error": str(exc),
                  "download": {"status": "error", "mbps": None},
                  "upload": {"status": "error", "mbps": None}}
    return {**result, "server": HOST, "source_ip": source_ip,
            "method": "single_https_total_elapsed", "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "note": "단일 HTTPS 전송의 연결·TLS·응답 시간을 포함한 처리량이며 최대 회선 속도가 아닙니다."}


if __name__ == "__main__":
    settings = json.load(sys.stdin)
    source = str(ipaddress.IPv4Address(settings["source_ip"]))
    download = transfer("download", source, DOWNLOAD_BYTES)
    upload = transfer("upload", source, UPLOAD_BYTES)
    successes = sum(x["status"] == "ok" for x in (download, upload))
    status = "ok" if successes == 2 else "partial" if successes else "error"
    print(json.dumps({"status": status, "download": download, "upload": upload}))
