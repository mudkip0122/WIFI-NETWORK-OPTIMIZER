"""Environment check and current Wi-Fi information CLI."""

import argparse
import json
import platform
import shutil
import sqlite3
import sys

from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(description="Wi-Fi Network Optimizer")
    parser.add_argument("--check", action="store_true", help="Check the development environment")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--wifi", action="store_true", help="Read current Wi-Fi information")
    parser.add_argument("--interface", help="Wi-Fi interface name (for example Wi-Fi)")
    parser.add_argument("--json", action="store_true", help="Print Wi-Fi results as JSON")
    parser.add_argument("--measure", action="store_true", help="Measure Wi-Fi and Ping quality")
    parser.add_argument("--speed", action="store_true", help="Include manual 10 MB down / 2 MB up test")
    parser.add_argument("--target", default="1.1.1.1", help="External Ping IPv4 address")
    parser.add_argument("--count", type=int, default=4, help="Ping requests per target (1..20)")
    parser.add_argument("--monitor", action="store_true", help="Periodically collect Wi-Fi and Ping")
    parser.add_argument("--interval", type=float, default=5, help="Seconds to wait after each cycle")
    parser.add_argument("--samples", type=int, help="Stop monitor after this many cycles")
    args = parser.parse_args()
    if sum((args.monitor, args.measure, args.wifi, args.check)) > 1:
        parser.error("Choose only one of --monitor, --measure, --wifi, --check")
    if args.monitor:
        import queue
        from .collector import CollectorConfig, WiFiCollector
        if args.speed:
            parser.error("Automatic speed testing is disabled; use --measure --speed")
        try:
            config = CollectorConfig(args.interface, args.target, args.count, args.interval)
            if args.samples is not None and args.samples < 1:
                raise ValueError("--samples must be positive")
        except ValueError as exc:
            parser.error(str(exc))
        collector = WiFiCollector(config)
        try:
            collector.start(max_samples=args.samples)
            while collector.running or not collector.results.empty():
                try:
                    print(json.dumps(collector.results.get(timeout=0.2), ensure_ascii=True), flush=True)
                except queue.Empty:
                    pass
        except KeyboardInterrupt:
            print("Stopping after the active measurement stage...", file=sys.stderr)
        finally:
            collector.close(timeout=None)
        return 0
    if args.speed and not args.measure:
        parser.error("--speed requires --measure")
    if args.measure:
        from .measurement import measure_quality
        try:
            result = measure_quality(args.interface, args.target, args.count, args.speed)
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["status"] == "ok" else 1
    if args.wifi:
        from .collectors.wifi import collect_wifi
        from .collectors.signal import WifiMeasurementError
        try:
            info = collect_wifi(args.interface)
        except WifiMeasurementError as exc:
            print(json.dumps({"status": exc.code, "message": str(exc)}, ensure_ascii=True))
            return 1
        if args.json:
            print(json.dumps(info.to_dict(), ensure_ascii=True, indent=2))
        else:
            for key, value in info.to_dict().items():
                print(f"{key:16}: {value if value is not None else 'N/A'}")
        return 0
    if not args.check:
        parser.print_help()
        return 0

    with sqlite3.connect(":memory:") as connection:
        sqlite_ok = connection.execute("SELECT 1").fetchone() == (1,)

    windows = platform.system() == "Windows"
    checks = {
        "python_supported": sys.version_info >= (3, 13),
        "sqlite_ok": sqlite_ok,
        "windows": windows,
        "netsh_available": shutil.which("netsh") is not None,
        "ping_available": shutil.which("ping") is not None,
    }
    print(json.dumps({
        "version": __version__,
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "platform": platform.system(),
        "checks": checks,
        "measurement_implemented": True,
    }, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
