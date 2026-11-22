"""Rule-based explanations and actions for surveyed Wi-Fi locations."""
from ..analysis.coverage import RSSI_LIMIT, QUALITY_LIMIT


def diagnose(point, rssi_limit=RSSI_LIMIT, quality_limit=QUALITY_LIMIT):
    values = point.averages
    rssi, score = values.get('rssi'), values.get('quality')
    gateway_ping, external_ping = values.get('gateway_ping'), values.get('external_ping')
    gateway_loss, external_loss = values.get('gateway_loss'), values.get('external_loss')

    findings = []
    if rssi is not None and rssi < rssi_limit:
        findings.append(f'[R01] RSSI {rssi:.1f} dBm으로 기준 {rssi_limit:g} dBm 미만입니다. '
                        'AP와의 거리 또는 벽·가구에 의한 감쇠를 확인하고, '
                        'AP를 이 지점에 가까운 탁 트인 위치로 옮겨 같은 조건에서 다시 측정하세요.')
    local_issue = _network_evidence(gateway_ping, gateway_loss, 20)
    outside_issue = _network_evidence(external_ping, external_loss, 100)
    local_normal = (gateway_ping is not None and gateway_ping < 20
                    and gateway_loss is not None and gateway_loss < 5)
    if local_issue:
        findings.append(f'[R02] 게이트웨이 측정값이 기준 이상입니다 ({local_issue}). AP 가까이에서 반복 측정해 '
                        '무선 구간과 AP 부하를 점검하세요.')
        if rssi is not None and rssi >= rssi_limit:
            channels = ', '.join(str(channel) for channel in sorted({ch for _, ch in point.radio if ch}))
            channel_detail = f'현재 측정 채널은 {channels}입니다. ' if channels else ''
            findings.append(f'[R03] RSSI {rssi:.1f} dBm은 기준 이상이며 게이트웨이 지연 또는 손실이 '
                            f'높습니다 ({local_issue}). '
                            f'{channel_detail}공유기나 Wi-Fi 분석 도구에서 주변 채널 사용량을 확인하고, '
                            '혼잡이 확인되면 같은 대역의 덜 혼잡한 지원 채널로 변경해 비교하세요.')
    if outside_issue:
        if local_normal:
            findings.append(f'[R04] 게이트웨이 지연 {gateway_ping:.1f} ms, 손실 {gateway_loss:.1f}%는 '
                            f'기준 이내이며 외부 지연 또는 손실이 높습니다 ({outside_issue}). '
                            '다른 외부 대상과 유선 연결에서 비교해 인터넷 경로와 회선 상태를 확인하세요.')
        else:
            findings.append(f'[R05] 외부 측정값이 기준 이상입니다 ({outside_issue}). '
                            '게이트웨이와 외부 대상을 함께 반복 측정해 '
                            '이상이 지속되는 구간을 확인하세요.')

    bands = {band for band, _ in point.radio}
    higher_bands = bands & {'5 GHz', '6 GHz'}
    if rssi is not None and rssi < rssi_limit and higher_bands:
        measured_bands = ', '.join(sorted(higher_bands))
        findings.append(f'[R06] {measured_bands}의 RSSI는 {rssi:.1f} dBm입니다. 장애물이 있는 지점에서 '
                        '2.4 GHz로도 측정해 도달 범위와 속도를 비교하세요.')
    elif '2.4 GHz' in bands and local_issue and rssi is not None and rssi >= rssi_limit:
        findings.append(f'[R07] 2.4 GHz의 RSSI {rssi:.1f} dBm은 기준 이상이며 게이트웨이 지연 또는 손실이 '
                        f'높습니다 ({local_issue}). '
                        '5 GHz도 사용해 지연과 손실을 비교하세요.')
    if not findings and score is not None and score < quality_limit:
        findings.append(f'[R08] 종합 품질 {score:.1f}점은 기준 {quality_limit:g}점 미만입니다. '
                        '같은 위치에서 속도를 포함해 반복 측정하고 '
                        '저장 기록의 지표별 점수를 확인하세요.')
    if not findings:
        findings.append('측정값에서 개선 규칙에 해당하는 항목을 찾지 못했습니다.' if values else
                        '이 지점에 유효한 측정값이 없습니다. 지점을 적용하고 자동 측정을 시작하세요.')
    return findings


def _network_evidence(ping, loss, ping_limit):
    evidence = []
    if ping is not None and ping >= ping_limit:
        evidence.append(f'지연 {ping:.1f} ms')
    if loss is not None and loss >= 5:
        evidence.append(f'손실 {loss:.1f}%')
    return ', '.join(evidence)


def placement_advice(points, rssi_limit=RSSI_LIMIT):
    measured = [point for point in points if 'rssi' in point.averages]
    weak = [point for point in measured if point.averages['rssi'] < rssi_limit]
    if not weak:
        return ''
    worst = min(weak, key=lambda point: point.averages['rssi'])
    target = f"「{worst.name}」({worst.averages['rssi']:.1f} dBm)"
    if len(weak) == len(measured):
        return (f'[R09] RSSI를 측정한 {len(measured)}개 지점 모두 기준 미만입니다. AP 가까이에서 기준값을 '
                f'확보한 다음, 신호가 가장 약한 {target} 쪽의 탁 트인 위치에서 AP 배치를 비교하세요.')
    return (f'[R10] {target} 방향으로 AP를 옮겨 개선 효과를 확인하고, 기존 양호 지점도 다시 측정하세요. '
            '여러 지점에서 약한 신호가 지속되면 해당 구역의 유선 연결 추가 AP 설치를 검토하세요.')
