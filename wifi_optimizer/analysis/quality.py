"""Versioned project scoring rules, not a universal Wi-Fi certification."""
import math


VERSION = 'week08-v1'
WEIGHTS = {'rssi': 30, 'gateway_ping': 15, 'external_ping': 10,
           'gateway_loss': 20, 'external_loss': 15, 'download': 7, 'upload': 3}
GRADES = ((90, '매우 좋음'), (75, '좋음'), (60, '보통'), (40, '나쁨'), (0, '매우 나쁨'))


def finite(value, low, high=math.inf):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and low <= value <= high)


def interpolate(value, points):
    if value <= points[0][0]:
        return float(points[0][1])
    for (left, a), (right, b) in zip(points, points[1:]):
        if value <= right:
            return a + (b - a) * (value - left) / (right - left)
    return float(points[-1][1])


def evaluate_quality(result, *, download_target=100, upload_target=20):
    """Score only valid readings from this cycle; expose missingness and weights."""
    if not finite(download_target, 0) or download_target == 0 or not finite(upload_target, 0) or upload_target == 0:
        raise ValueError('속도 목표는 유한한 양수여야 합니다.')
    scores, notes, samples = {}, [], {}
    wifi = result.get('wifi') or {}
    blocked = result.get('status') in ('error', 'cancelled') or bool(result.get('warnings'))
    if blocked:
        notes.append('실패·취소 또는 연결 변경 경고가 있어 종합 평가하지 않습니다.')
    rssi = wifi.get('rssi_dbm')
    if not blocked and finite(rssi, -100, 0):
        scores['rssi'] = interpolate(rssi, [(-100, 0), (-85, 20), (-75, 40), (-67, 60), (-55, 90), (-50, 100)])
        if wifi.get('rssi_source') != 'native_wifi':
            notes.append('RSSI는 추정값 또는 출처 미확인입니다.')
    for target in ('gateway', 'external'):
        ping = (result.get('ping') or {}).get(target) or {}
        sent = ping.get('sent')
        valid_sent = isinstance(sent, int) and not isinstance(sent, bool) and sent > 0
        samples[target] = sent if valid_sent else None
        if blocked or not valid_sent or ping.get('status') not in ('ok', 'partial', 'no_reply'):
            continue
        latency, loss = ping.get('avg_ms'), ping.get('packet_loss_percent')
        if finite(latency, 0) and loss != 100:
            points = ([(0, 100), (5, 100), (20, 75), (50, 40), (100, 0)] if target == 'gateway'
                      else [(0, 100), (20, 100), (50, 75), (100, 40), (300, 0)])
            scores[f'{target}_ping'] = interpolate(latency, points)
        if finite(loss, 0, 100):
            scores[f'{target}_loss'] = interpolate(loss, [(0, 100), (1, 90), (3, 75), (5, 60), (10, 40), (25, 0), (100, 0)])
        if sent < 20:
            notes.append(f'{target} Ping 표본 {sent}개: 손실률은 변동성이 큽니다.')
    speed = result.get('speed') or {}
    for direction, goal in (('download', download_target), ('upload', upload_target)):
        part = speed.get(direction) or {}
        if (not blocked and speed.get('status') in ('ok', 'partial')
                and part.get('status') == 'ok' and finite(part.get('mbps'), 0)):
            scores[direction] = min(100.0, part['mbps'] / goal * 100)
    used_weight = sum(WEIGHTS[key] for key in scores)
    # RSSI and at least one network reading are required for a composite.
    enough = 'rssi' in scores and any(key.endswith(('_ping', '_loss')) for key in scores)
    total = sum(score * WEIGHTS[key] for key, score in scores.items()) / used_weight if enough else None
    grade = next(label for threshold, label in GRADES if total >= threshold) if total is not None else '평가 불가'
    if not enough:
        notes.append('종합 점수에는 RSSI와 Ping 또는 손실 측정이 필요합니다.')
    notes.append('외부 Ping·속도에는 인터넷 경로와 서버 영향이 포함됩니다.')
    return {'version': VERSION, 'score': round(total, 2) if total is not None else None,
            'grade': grade, 'status': 'complete' if len(scores) == len(WEIGHTS) else 'partial' if enough else 'unavailable',
            'scores': {key: round(value, 2) for key, value in scores.items()},
            'used': list(scores), 'missing': [key for key in WEIGHTS if key not in scores],
            'coverage_percent': used_weight, 'weights': dict(WEIGHTS),
            'speed_targets_mbps': {'download': download_target, 'upload': upload_target},
            'ping_samples': samples, 'notes': notes}
