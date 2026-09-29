CREATE TABLE space (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, floorplan_path TEXT,
    width REAL CHECK(width > 0), height REAL CHECK(height > 0),
    coordinate_unit TEXT NOT NULL CHECK(coordinate_unit IN ('m', 'px'))
);
CREATE TABLE location (
    id INTEGER PRIMARY KEY, space_id INTEGER NOT NULL REFERENCES space(id) ON DELETE RESTRICT,
    name TEXT NOT NULL, x REAL NOT NULL CHECK(x >= 0), y REAL NOT NULL CHECK(y >= 0)
);
CREATE INDEX location_space ON location(space_id);
CREATE TABLE ap (
    id INTEGER PRIMARY KEY, bssid TEXT NOT NULL UNIQUE, display_name TEXT
);
CREATE TABLE session (
    id TEXT PRIMARY KEY NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('monitor', 'manual')),
    started_at TEXT NOT NULL, finished_at TEXT,
    config_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(config_json)),
    data_kind TEXT NOT NULL CHECK(data_kind IN ('real', 'example')),
    CHECK(finished_at IS NULL OR finished_at >= started_at)
);
CREATE TABLE measurement (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES session(id) ON DELETE RESTRICT,
    sequence INTEGER NOT NULL CHECK(sequence > 0 AND typeof(sequence) = 'integer'),
    started_at TEXT NOT NULL, finished_at TEXT NOT NULL CHECK(finished_at >= started_at),
    duration_seconds REAL CHECK(duration_seconds >= 0),
    location_id INTEGER REFERENCES location(id) ON DELETE RESTRICT,
    repeat_group_id TEXT, ap_id INTEGER REFERENCES ap(id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK(status IN ('ok', 'partial', 'error', 'cancelled')),
    error_code TEXT, error TEXT,
    warnings_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(warnings_json)),
    raw_result_json TEXT NOT NULL CHECK(json_valid(raw_result_json)),
    wifi_timestamp TEXT, interface TEXT, interface_guid TEXT, interface_description TEXT,
    wifi_state TEXT, ssid TEXT, bssid TEXT,
    signal_percent INTEGER CHECK(signal_percent BETWEEN 0 AND 100),
    rssi_dbm REAL, rssi_source TEXT,
    channel INTEGER CHECK(channel BETWEEN 1 AND 233), band TEXT,
    wifi_warnings_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(wifi_warnings_json)),
    network_interface TEXT, network_index INTEGER, source_ip TEXT, gateway TEXT,
    UNIQUE(session_id, sequence)
);
CREATE INDEX measurement_time ON measurement(started_at, id);
CREATE INDEX measurement_ap_time ON measurement(ap_id, started_at, id);
CREATE INDEX measurement_location_time ON measurement(location_id, started_at, id);
CREATE INDEX measurement_repeat_group ON measurement(repeat_group_id);
CREATE TABLE ping_result (
    id INTEGER PRIMARY KEY,
    measurement_id INTEGER NOT NULL REFERENCES measurement(id) ON DELETE RESTRICT,
    target_kind TEXT NOT NULL CHECK(target_kind IN ('gateway', 'external')),
    target TEXT, source_ip TEXT, started_at TEXT, finished_at TEXT,
    timeout_ms INTEGER CHECK(timeout_ms >= 0),
    status TEXT NOT NULL CHECK(status IN ('ok', 'partial', 'no_reply', 'error', 'unavailable')),
    attempted INTEGER CHECK(attempted >= 0), sent INTEGER CHECK(sent >= 0),
    received INTEGER CHECK(received >= 0), send_errors INTEGER CHECK(send_errors >= 0),
    min_ms REAL CHECK(min_ms >= 0), avg_ms REAL CHECK(avg_ms >= 0), max_ms REAL CHECK(max_ms >= 0),
    packet_loss_percent REAL CHECK(packet_loss_percent BETWEEN 0 AND 100), error TEXT,
    samples_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(samples_json)),
    UNIQUE(measurement_id, target_kind),
    CHECK(received <= sent AND sent <= attempted),
    CHECK(sent + send_errors = attempted),
    CHECK(sent IS NULL OR sent != 0 OR packet_loss_percent IS NULL),
    CHECK(received IS NULL OR received != 0 OR (min_ms IS NULL AND avg_ms IS NULL AND max_ms IS NULL)),
    CHECK(min_ms <= avg_ms AND avg_ms <= max_ms),
    CHECK(finished_at >= started_at)
);
CREATE TABLE speed_result (
    id INTEGER PRIMARY KEY,
    measurement_id INTEGER NOT NULL UNIQUE REFERENCES measurement(id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK(status IN ('ok', 'partial', 'error')),
    server TEXT, source_ip TEXT, method TEXT, started_at TEXT, finished_at TEXT, note TEXT, error TEXT,
    CHECK(finished_at >= started_at)
);
CREATE TABLE speed_transfer (
    id INTEGER PRIMARY KEY,
    speed_result_id INTEGER NOT NULL REFERENCES speed_result(id) ON DELETE RESTRICT,
    direction TEXT NOT NULL CHECK(direction IN ('download', 'upload')),
    status TEXT NOT NULL CHECK(status IN ('ok', 'error')),
    mbps REAL CHECK(mbps >= 0), bytes INTEGER CHECK(bytes >= 0), seconds REAL CHECK(seconds >= 0),
    server_location TEXT, error TEXT, UNIQUE(speed_result_id, direction)
);
