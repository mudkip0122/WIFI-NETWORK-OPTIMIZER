"""Initialize the local measurement database without collecting network data."""

import argparse
from pathlib import Path

from . import DEFAULT_DB_PATH, MeasurementStore


def main():
    parser = argparse.ArgumentParser(description='Create or verify the Wi-Fi SQLite v1 schema.')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB_PATH, help='SQLite file path')
    args = parser.parse_args()
    with MeasurementStore(args.db):
        print(f'SQLite schema v1 ready: {args.db.resolve()}')


if __name__ == '__main__':
    main()
