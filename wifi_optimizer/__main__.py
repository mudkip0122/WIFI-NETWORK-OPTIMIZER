"""Week 1 development environment check; no network measurements are performed."""

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
    args = parser.parse_args()
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
        "measurement_implemented": False,
    }, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
