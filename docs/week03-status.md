# 3주차 - 네트워크 품질 측정

상태: 구현 및 실제 GUI 검증 완료 (2026-09-24).

## 구현 범위

- Windows ICMP API로 게이트웨이 및 외부 IPv4 대상 Ping을 각각 측정한다.
- 평균·최소·최대 RTT(ms), 송신·수신 횟수, 표본별 상태, 패킷 손실률을 기록한다.
- Wi-Fi IPv4 출발 주소를 지정하여 유선과 동시에 연결된 PC에서도 측정 대상을 명확히 한다.
- 속도는 수동 요청 시 Cloudflare HTTPS 다운로드 10,000,000 bytes 및 업로드
  2,000,000 bytes를 순서대로 측정한다. 업로드 데이터는 생성한 시험 데이터다.
- 속도 연결에도 Wi-Fi IPv4 주소를 지정한다. 시스템 프록시 대신 직접 HTTPS 연결을 사용한다.
- 하나의 결과에 wifi(RSSI·채널·대역 포함), network, ping, speed,
  시작·종료 UTC 시각, 상태, 경고를 포함한다.
- 측정 전후 AP가 바뀌거나 연결 확인이 실패하면 결과를 partial로 표시한다.
- GUI 버튼으로 Ping만 측정하거나 속도를 포함할 수 있다. 동시에 같은 측정을 중복 시작하지 않는다.
- 품질 결과를 JSON 파일로 저장할 수 있다. DB 자동 저장은 5주차 범위다.

## 실행

```powershell
# Wi-Fi + 게이트웨이/외부 Ping (각 4회)
.\.venv\Scripts\python.exe -m wifi_optimizer --measure

# 다운로드/업로드 포함 (약 12 MB)
.\.venv\Scripts\python.exe -m wifi_optimizer --measure --speed

# 대상·표본 수·무선 인터페이스 지정
.\.venv\Scripts\python.exe -m wifi_optimizer --measure --target 1.1.1.1 --count 10 --interface "Wi-Fi"

# GUI
.\.venv\Scripts\python.exe "Wi-Fi Signal Strength Visualizer.py"
```

품질 측정 CLI 출력은 항상 JSON이다. 성공은 종료 코드 0, 부분 실패·실패는 1,
잘못된 인자는 2다. Ping 대상은 현재 IPv4 주소만 지원한다.

## 오류와 해석

- 응답 없는 패킷은 손실에 포함하지만 로컬 송신 오류는 별도 집계한다.
- 전부 타임아웃이면 손실 100%, RTT는 null이다. 송신 자체가 전부 실패하면 손실도 null이다.
- RTT는 Windows가 반환하는 정수 밀리초 해상도다. 0 ms는 1 ms 미만일 수 있다.
- Ping 기본 4회는 짧은 표본이다. 장기 품질 판단에는 반복 측정이 필요하다.
- 게이트웨이와 외부 대상 결과를 분리한다. ICMP 차단과 인터넷 경로 영향은 Wi-Fi 장애와 다를 수 있다.
- 속도는 payload bits / 전체 경과 시간이다. TCP 연결·TLS·서버 응답 시간을 포함하며
  단일 연결의 전송 처리량이다. 멀티 연결 방식의 최대 대역폭 테스트와 직접 비교하지 않는다.
- Ping을 먼저, 속도를 나중에 측정하여 자체 속도 측정 트래픽이 Ping에 섞이는 것을 줄인다.
- HTTP 실패·불완전 응답·시간 초과는 숫자 0을 반환하지 않는다. 성공한 방향의 값은 보존한다.
- HTTP 소켓 타임아웃은 15초, 전송 루프 제한은 30초, 속도 작업 전체 제한은 75초다.
- UI 종료 시 신규 작업을 중단한다. 진행 중 네트워크 작업은 설정된 제한 시간 내 종료하며
  Python 프로세스가 그동안 남아 있을 수 있다. 즉시 취소는 후속 통합 단계에서 개선한다.
- 인터페이스에 사용 가능한 IPv4가 여러 개이거나 없으면 명확한 오류로 반환한다.
- 출발 주소 지정은 일반 Windows 라우팅 환경을 대상으로 한다. VPN·특수 라우팅 및
  측정 중 변경됐다가 복구된 연결까지 완전히 추적하지는 않는다.

## 검증 결과

- 자동 테스트 총 22개 통과 (기존 12개 + 3주차 10개).
- 손실률/RTT 계산, 무응답·송신 실패, 인자 검증, 출발 IP 전달,
  Mbps 단위, HTTP 오류·응답 부족·전체 시간 초과, AP 변경을 검증했다.
- 유선 기본 경로가 존재하는 실환경에서 Wi-Fi 출발 주소로 ICMP 측정에 성공했다.
- 최종 GUI 통합 실측: 전체 상태 ok, 신호 그래프 6개 표본 갱신.
- 게이트웨이 평균 1.5 ms, 외부 평균 8.25 ms. 양쪽 각각 4회 응답, 손실 0%.
- 다운로드 약 47.56 Mbps, 업로드 약 45.15 Mbps, Cloudflare ICN 응답.
- 실측 JSON은 logs/week03-live.json에 로컬 저장했으며 Git에서는 제외한다.

## 근거 문서

- [Microsoft IcmpSendEcho2Ex](https://learn.microsoft.com/en-us/windows/win32/api/icmpapi/nf-icmpapi-icmpsendecho2ex)
- [Cloudflare speedtest 공식 프로젝트 및 다운로드/업로드 엔드포인트](https://github.com/cloudflare/speedtest)

본 프로젝트는 Cloudflare의 전체 측정 엔진을 사용하지 않고 공개된 시험 엔드포인트에
정해진 크기의 데이터를 전송하는 자체 단일 연결 측정기를 사용한다.
