"""Summarize measured points and estimate coverage inside their sampled footprint."""
from collections import defaultdict
from dataclasses import dataclass
from math import ceil, hypot

from .quality import evaluate_quality, finite


RSSI_LIMIT = -75
QUALITY_LIMIT = 60
METRICS = {
    'rssi': ('RSSI', 'dBm', -95, -45),
    'external_ping': ('외부 Ping', 'ms', 100, 0),
    'quality': ('품질 점수', '점', 0, 100),
}


@dataclass
class SurveyPoint:
    id: int
    name: str
    x: float
    y: float
    averages: dict
    counts: dict
    radio: tuple
    rssi_sources: tuple = ()


def summarize_points(rows):
    points = {}
    totals, counts = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(int))
    radios, rssi_sources = defaultdict(set), defaultdict(set)

    def add(point_id, metric, value, low, high=float('inf')):
        if finite(value, low, high):
            totals[point_id][metric] += value
            counts[point_id][metric] += 1

    for point_id, name, x, y, result in rows:
        points[point_id] = (name, x, y)
        if result is None:
            continue
        wifi = result.get('wifi') or {}
        rssi = wifi.get('rssi_dbm')
        if finite(rssi, -128, 0):
            add(point_id, 'rssi', rssi, -128, 0)
            rssi_sources[point_id].add(wifi.get('rssi_source') or 'unknown')
        band, channel = wifi.get('band'), wifi.get('channel')
        if band or channel:
            radios[point_id].add((band, channel))
        quality = result.get('quality')
        if not isinstance(quality, dict):
            quality = evaluate_quality(result)
        add(point_id, 'quality', quality.get('score'), 0, 100)
        for target in ('gateway', 'external'):
            ping = (result.get('ping') or {}).get(target) or {}
            status, sent = ping.get('status'), ping.get('sent')
            if not finite(sent, 1):
                continue
            loss = ping.get('packet_loss_percent')
            if status in ('ok', 'partial') and loss != 100:
                add(point_id, f'{target}_ping', ping.get('avg_ms'), 0)
            if status in ('ok', 'partial', 'no_reply'):
                add(point_id, f'{target}_loss', loss, 0, 100)

    return [SurveyPoint(point_id, *point, {
        metric: total / counts[point_id][metric] for metric, total in totals[point_id].items()
    }, dict(counts[point_id]), tuple(sorted(radios[point_id], key=str)),
        tuple(sorted(rssi_sources[point_id])))
            for point_id, point in points.items()]


def _cross(origin, a, b):
    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])


def _hull(coordinates):
    ordered = sorted(coordinates)

    def half(sequence):
        chain = []
        for point in sequence:
            while len(chain) >= 2 and _cross(chain[-2], chain[-1], point) <= 0:
                chain.pop()
            chain.append(point)
        return chain

    return half(ordered)[:-1] + half(reversed(ordered))[:-1]


def _estimate(metric, points, centers, width, height):
    samples = defaultdict(lambda: [0, 0])
    for point in points:
        if metric in point.averages:
            total = samples[(point.x / width, point.y / height)]
            count = point.counts[metric]
            total[0] += point.averages[metric] * count
            total[1] += count
    boundary = _hull(samples)
    if len(boundary) < 3:
        return {}
    estimates = {}
    longest = max(width, height)
    x_ratio, y_ratio = width / longest, height / longest
    for cell, center in centers.items():
        if any(_cross(a, b, center) < -1e-12
               for a, b in zip(boundary, boundary[1:] + boundary[:1])):
            continue
        distances = [(hypot((x - center[0]) * x_ratio, (y - center[1]) * y_ratio), total / count)
                     for (x, y), (total, count) in samples.items()]
        nearest, exact = min(distances)
        if nearest == 0:
            estimates[cell] = exact
            continue
        weights = [((nearest / distance) ** 2, value) for distance, value in distances]
        estimates[cell] = sum(w * v for w, v in weights) / sum(w for w, _ in weights)
    return estimates


def is_low(values, rssi_limit=RSSI_LIMIT, quality_limit=QUALITY_LIMIT):
    return (values.get('rssi', float('inf')) < rssi_limit
            or values.get('quality', float('inf')) < quality_limit)


@dataclass
class Coverage:
    columns: int
    rows: int
    values: dict
    assessed: int
    regions: list


def _connected_regions(cells):
    remaining = set(cells)
    regions = []
    while remaining:
        pending = [min(remaining)]
        remaining.remove(pending[0])
        region = set(pending)
        while pending:
            column, row = pending.pop()
            for neighbor in ((column - 1, row), (column + 1, row), (column, row - 1), (column, row + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    region.add(neighbor)
                    pending.append(neighbor)
        regions.append(region)
    return sorted(regions, key=len, reverse=True)


def estimate_coverage(points, width, height, rssi_limit=RSSI_LIMIT, quality_limit=QUALITY_LIMIT):
    """Use cell-center IDW within each metric's convex hull and classify contiguous low cells."""
    longest = max(width, height)
    columns = max(1, ceil(30 * (width / longest)))
    rows = max(1, ceil(30 * (height / longest)))
    centers = {(c, r): ((c + 0.5) / columns, (r + 0.5) / rows)
               for c in range(columns) for r in range(rows)}
    values = {metric: _estimate(metric, points, centers, width, height)
              for metric in METRICS}
    rssi, quality = values['rssi'], values['quality']
    assessed = rssi.keys() | quality.keys()
    low = {cell for cell in assessed if is_low({
        'rssi': rssi.get(cell, float('inf')), 'quality': quality.get(cell, float('inf'))
    }, rssi_limit, quality_limit)}
    return Coverage(columns, rows, values, len(assessed), _connected_regions(low))
