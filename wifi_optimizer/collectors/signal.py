"""Read signal percentage from Korean or English Windows netsh output."""

import ctypes
import os
import re
import subprocess


class WifiMeasurementError(RuntimeError):
    """A measurement could not be obtained; never substitute zero."""

    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.code = code


def parse_signal(output: str) -> int | None:
    match = re.search(r"^\s*(?:신호|Signal)\s*:\s*(\d+)\s*%", output, re.M | re.I)
    if match:
        value = int(match.group(1))
        if 0 <= value <= 100:
            return value
    return None


def run_netsh() -> str:
    if os.name != "nt":
        raise WifiMeasurementError("Windows에서 실행해 주세요.", "unsupported_platform")
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise WifiMeasurementError("Wi-Fi 정보 조회 시간이 초과되었습니다.", "timeout") from exc
    except OSError as exc:
        raise WifiMeasurementError("netsh 명령을 실행할 수 없습니다.") from exc

    encoding = f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    raw = result.stdout + result.stderr
    try:
        output = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        output = raw.decode(encoding, errors="replace")
    if re.search(r"error\s*5\b|access.*denied|requires elevation|액세스.*거부|권한.*상승|위치.*권한", output, re.I):
        raise WifiMeasurementError(
            "Wi-Fi 정보 접근이 거부되었습니다. Windows 위치 접근 설정과 실행 권한을 확인하세요.",
            "permission_denied",
        )
    if result.returncode != 0:
        raise WifiMeasurementError(f"Wi-Fi 정보 조회 실패 (종료 코드 {result.returncode}).")
    return output


def get_wifi_signal_strength() -> int:
    signal = parse_signal(run_netsh())
    if signal is None:
        raise WifiMeasurementError(
            "신호 정보를 찾지 못했습니다. Wi-Fi 연결·어댑터 상태와 netsh 출력 언어를 확인하세요."
        )
    return signal
