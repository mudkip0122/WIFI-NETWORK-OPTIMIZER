"""Versioned local SQLite storage. Use each instance only on its creating thread."""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
import uuid


DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / 'data' / 'wifi_optimizer.sqlite3'
SCHEMA_VERSION = 1


class SchemaVersionError(RuntimeError):
    """The file is not an empty database or a supported schema."""


class DuplicateMeasurementError(ValueError):
    """A session/sequence already exists with different data or location context."""


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be a timezone-aware ISO 8601 string')
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError('Timestamp must include a timezone')
    return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds')


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':'))


def _fields(source, names):
    values = {name: source.get(name) for name in names.split()}
    for key, value in values.items():
        if key in ('started_at', 'finished_at') and value is not None:
            values[key] = _timestamp(value)
    return values


class MeasurementStore:
    """Create/open the v1 schema and atomically persist complete result dictionaries.

    Context exit closes the connection; public mutations commit independently.
    It does not start a collector, perform network calls, or fabricate measurements.
    """

    def __init__(self, path=DEFAULT_DB_PATH, *, readonly=False):
        if readonly:
            self.connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro',
                                              uri=True, timeout=5)
        elif str(path) != ':memory:':
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(str(path), timeout=5)
        else:
            self.connection = sqlite3.connect(':memory:', timeout=5)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute('PRAGMA foreign_keys = ON')
            self.connection.execute('PRAGMA busy_timeout = 5000')
            if readonly:
                version = self.connection.execute('PRAGMA user_version').fetchone()[0]
                if version != SCHEMA_VERSION:
                    raise SchemaVersionError(f'Unsupported schema version: {version}')
            else:
                self._initialize()
        except Exception:
            self.connection.close()
            raise

    def _initialize(self):
        # Lock before checking the version so simultaneous initializers cannot race.
        with self.connection:
            self.connection.execute('BEGIN IMMEDIATE')
            version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version == SCHEMA_VERSION:
                return
            if version != 0:
                raise SchemaVersionError(f'Unsupported schema version: {version}')
            if self.connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
            ).fetchone():
                raise SchemaVersionError('Refusing to initialize a nonempty unversioned database')
            schema = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
            # executescript commits pending work; execute complete statements instead.
            statement = ''
            for line in schema.splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    self.connection.execute(statement)
                    statement = ''
            if statement.strip():
                raise SchemaVersionError('Incomplete schema statement')
            self.connection.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.connection.close()

    def list_measurements(self, *, limit=100, from_time=None, to_time=None, ap_id=None,
                          bssid=None, location_id=None, session_id=None, data_kind='real',
                          before=None):
        """Newest first; UTC [from_time, to_time), optional keyset (timestamp, id).

        Summary rows retain nulls and individual metric statuses. Examples are excluded
        by default; data_kind=None explicitly includes both real and example sessions.
        """
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('limit must be an integer from 1 to 500')
        clauses, parameters = [], []
        start = _timestamp(from_time) if from_time is not None else None
        end = _timestamp(to_time) if to_time is not None else None
        if start is not None and end is not None and start >= end:
            raise ValueError('from_time must be earlier than to_time')
        for column, operator, value in [('m.started_at', '>=', start), ('m.started_at', '<', end),
                                         ('m.session_id', '=', session_id)]:
            if value is not None:
                clauses.append(f'{column} {operator} ?')
                parameters.append(value)
        for column, value in [('m.ap_id', ap_id), ('m.location_id', location_id)]:
            if value is not None:
                if type(value) is not int or value < 1:
                    raise ValueError('AP and location IDs must be positive integers')
                clauses.append(f'{column} = ?')
                parameters.append(value)
        if bssid is not None:
            if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', bssid):
                raise ValueError('Invalid BSSID')
            clauses.append('m.ap_id = (SELECT id FROM ap WHERE bssid = ?)')
            parameters.append(bssid.lower())
        if data_kind is not None:
            if data_kind not in ('real', 'example'):
                raise ValueError('data_kind must be real, example or None')
            clauses.append('s.data_kind = ?')
            parameters.append(data_kind)
        if before is not None:
            if len(before) != 2 or type(before[1]) is not int or before[1] < 1:
                raise ValueError('before must contain a timestamp and positive measurement ID')
            clauses.append('(m.started_at, m.id) < (?, ?)')
            parameters.extend((_timestamp(before[0]), before[1]))
        where = ' AND '.join(clauses) or '1=1'
        rows = self.connection.execute(f'''
            SELECT m.id, m.session_id, m.sequence, m.started_at, m.finished_at, m.status,
                   m.ap_id, m.ssid, m.bssid, m.interface, m.rssi_dbm, m.rssi_source,
                   m.signal_percent, m.channel, m.band, m.location_id,
                   l.name AS location_name, s.data_kind, m.warnings_json, m.error,
                   p.status AS ping_status, p.avg_ms AS ping_avg_ms,
                   p.packet_loss_percent, d.mbps AS download_mbps, d.status AS download_status,
                   u.mbps AS upload_mbps, u.status AS upload_status
            FROM measurement m JOIN session s ON s.id = m.session_id
            LEFT JOIN location l ON l.id = m.location_id
            LEFT JOIN ping_result p ON p.measurement_id = m.id AND p.target_kind = 'external'
            LEFT JOIN speed_result speed ON speed.measurement_id = m.id
            LEFT JOIN speed_transfer d ON d.speed_result_id = speed.id AND d.direction = 'download'
            LEFT JOIN speed_transfer u ON u.speed_result_id = speed.id AND u.direction = 'upload'
            WHERE {where} ORDER BY m.started_at DESC, m.id DESC LIMIT ?
        ''', (*parameters, limit)).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item['warnings'] = json.loads(item.pop('warnings_json'))
            results.append(item)
        return results

    def get_measurement(self, measurement_id):
        """Return saved context and original complete result, or None if absent."""
        if type(measurement_id) is not int or measurement_id < 1:
            raise ValueError('measurement_id must be a positive integer')
        row = self.connection.execute('''
            SELECT m.*, s.data_kind, l.name AS location_name
            FROM measurement m JOIN session s ON s.id = m.session_id
            LEFT JOIN location l ON l.id = m.location_id WHERE m.id = ?
        ''', (measurement_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        for source, target in [('raw_result_json', 'result'), ('warnings_json', 'warnings'),
                                ('wifi_warnings_json', 'wifi_warnings')]:
            result[target] = json.loads(result.pop(source))
        return result

    def _insert(self, table, values):
        # Identifiers are internal constants, values are always bound parameters.
        columns = ', '.join(values)
        placeholders = ', '.join('?' for _ in values)
        return self.connection.execute(
            f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', tuple(values.values())
        ).lastrowid

    def create_session(self, *, mode='manual', config=None, data_kind='real', started_at=None):
        session_id = str(uuid.uuid4())
        if config is not None and not isinstance(config, dict):
            raise ValueError('config must be a dictionary')
        with self.connection:
            self._insert('session', {
                'id': session_id, 'mode': mode, 'started_at': _timestamp(started_at or _now()),
                'config_json': _json(config if config is not None else {}), 'data_kind': data_kind,
            })
        return session_id

    def finish_session(self, session_id, *, finished_at=None):
        with self.connection:
            cursor = self.connection.execute(
                'UPDATE session SET finished_at = ? WHERE id = ? AND finished_at IS NULL',
                (_timestamp(finished_at or _now()), session_id),
            )
            if cursor.rowcount != 1:
                raise ValueError('Session does not exist or is already finished')

    def create_space(self, name, *, coordinate_unit='m', floorplan_path=None,
                     width=None, height=None):
        for value in (width, height):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError('Space dimensions must be positive and finite')
        with self.connection:
            return self._insert('space', dict(name=name, coordinate_unit=coordinate_unit,
                                             floorplan_path=floorplan_path, width=width, height=height))

    def create_location(self, space_id, name, *, x, y):
        if any(not math.isfinite(v) or v < 0 for v in (x, y)):
            raise ValueError('Coordinates must be nonnegative and finite')
        with self.connection:
            return self._insert('location', dict(space_id=space_id, name=name, x=x, y=y))

    def save_measurement(self, session_id, result, *, sequence=None, location_id=None,
                         repeat_group_id=None):
        """Save one result; identical retries return its ID, conflicting retries raise.

        Manual results default to sequence 1. Collector results use their own sequence.
        Raw JSON is preserved semantically; normalized columns use UTC timestamps.
        """
        raw = _json(result)  # Also rejects NaN/infinity anywhere in nested results.
        seq = result.get('sequence', 1) if sequence is None else sequence
        if type(seq) is not int or seq < 1:
            raise ValueError('sequence must be a positive integer')
        if sequence is not None and 'sequence' in result and result['sequence'] != sequence:
            raise ValueError('sequence disagrees with result')
        wifi = result.get('wifi') or {}
        network = result.get('network') or {}
        values = _fields(result, 'started_at finished_at duration_seconds status error_code error')
        values.update(session_id=session_id, sequence=seq, location_id=location_id,
                      repeat_group_id=repeat_group_id, raw_result_json=raw,
                      warnings_json=_json(result.get('warnings', [])),
                      wifi_warnings_json=_json(wifi.get('warnings', [])))
        values.update(_fields(wifi, 'interface ssid bssid signal_percent rssi_dbm rssi_source channel band'))
        values.update(interface_guid=wifi.get('guid'), interface_description=wifi.get('description'),
                      wifi_state=wifi.get('state'),
                      wifi_timestamp=_timestamp(wifi['timestamp']) if wifi.get('timestamp') else None,
                      network_interface=network.get('interface'), network_index=network.get('index'),
                      source_ip=network.get('source_ip'), gateway=network.get('gateway'))
        bssid = values['bssid']
        if bssid is not None:
            if not isinstance(bssid, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', bssid):
                raise ValueError('Invalid BSSID')
            values['bssid'] = bssid = bssid.lower()
        with self.connection:
            self.connection.execute('BEGIN IMMEDIATE')
            existing = self.connection.execute(
                'SELECT id, raw_result_json, location_id, repeat_group_id FROM measurement '
                'WHERE session_id = ? AND sequence = ?', (session_id, seq)
            ).fetchone()
            if existing:
                if (existing['raw_result_json'], existing['location_id'], existing['repeat_group_id']) != (
                    raw, location_id, repeat_group_id
                ):
                    raise DuplicateMeasurementError('Existing measurement has different content')
                return existing['id']
            session = self.connection.execute(
                'SELECT finished_at FROM session WHERE id = ?', (session_id,)
            ).fetchone()
            if session is None or session['finished_at'] is not None:
                raise ValueError('An open session is required')
            if bssid is not None:
                self.connection.execute('INSERT INTO ap(bssid) VALUES (?) ON CONFLICT(bssid) DO NOTHING',
                                        (bssid,))
                values['ap_id'] = self.connection.execute(
                    'SELECT id FROM ap WHERE bssid = ?', (bssid,)
                ).fetchone()[0]
            measurement_id = self._insert('measurement', values)
            for kind, ping in result.get('ping', {}).items():
                row = _fields(ping, 'target source_ip started_at finished_at timeout_ms status '
                              'attempted sent received send_errors min_ms avg_ms max_ms '
                              'packet_loss_percent error')
                row.update(measurement_id=measurement_id, target_kind=kind,
                           samples_json=_json(ping.get('samples', [])))
                self._insert('ping_result', row)
            speed = result.get('speed', {'status': 'not_requested'})
            if speed.get('status') != 'not_requested':
                row = _fields(speed, 'status server source_ip method started_at finished_at note error')
                row['measurement_id'] = measurement_id
                speed_id = self._insert('speed_result', row)
                for direction in ('download', 'upload'):
                    if direction in speed:
                        transfer = _fields(speed[direction], 'status mbps bytes seconds server_location error')
                        transfer.update(speed_result_id=speed_id, direction=direction)
                        self._insert('speed_transfer', transfer)
            return measurement_id
