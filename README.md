# Wi-Fi 무선 네트워크 품질 분석 및 최적화 시스템

Windows에서 Wi-Fi 측정 데이터를 수집·저장하고 공간별 품질과 개선 방법을 보여주는 16주 프로젝트입니다.

GitHub 저장소: [mudkip0122/WIFI-NETWORK-OPTIMIZER](https://github.com/mudkip0122/WIFI-NETWORK-OPTIMIZER)

현재 단계: **4주차 Wi-Fi Collector 및 자동 측정 통합·검증 완료**. 현재 연결된 무선 인터페이스의
SSID·BSSID·신호 %·RSSI·채널·대역을 수집하며 기존 Visualizer에도 표시합니다.
게이트웨이·외부 Ping, 패킷 손실, 수동 다운로드/업로드 측정을 지원합니다.
주기적 자동 측정·시작/중지·실행 로그를 지원합니다. DB·Heatmap은 이후 주차에 구현합니다.

```powershell
.\.venv\Scripts\python.exe -m wifi_optimizer --wifi
.\.venv\Scripts\python.exe -m wifi_optimizer --wifi --json
.\.venv\Scripts\python.exe -m wifi_optimizer --wifi --interface "Wi-Fi"
.\.venv\Scripts\python.exe -m wifi_optimizer --measure
.\.venv\Scripts\python.exe -m wifi_optimizer --measure --speed
.\.venv\Scripts\python.exe -m wifi_optimizer --monitor --interval 5 --samples 3
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

RSSI 출처 `native_wifi`는 드라이버 조회값, `estimated_from_signal`은 신호 % 환산값입니다.
연결된 무선 인터페이스가 여러 개면 이름을 지정해야 합니다. GUI 상단 입력란에서도 선택할 수 있습니다.
Wi-Fi가 끊기면 오류 상태를 표시하며 마지막 그래프를 현재 측정값으로 표시하지 않습니다.

GUI 실행 시 Wi-Fi·Ping·손실을 자동 측정합니다. 각 측정 완료 후 기본 5초 대기합니다.
**중지 / 자동 측정 시작**으로 제어하고 **속도 포함 1회 예약 (약 12 MB)**으로 속도를 측정합니다.
속도는 단일 HTTPS 처리량으로 최대 회선 속도와 다릅니다. **최근 결과 JSON 저장**으로 보관할 수 있습니다.
중지 또는 창 닫기 시 진행 중인 측정 단계의 종료를 기다립니다.

기존 프로그램 실행:

```powershell
.\.venv\Scripts\python.exe "Wi-Fi Signal Strength Visualizer.py"
```

Visualizer에는 Matplotlib와 NumPy가 필요합니다. 현재 개발 환경에서 확인했습니다.
새 환경에서는 `python -m pip install "matplotlib>=3.10,<4" "numpy>=2.2,<3"`로 설치합니다.

## 시작하기

Python 3.13을 기준으로 준비했습니다. 별도 외부 패키지 없이 환경 확인 명령을 실행할 수 있습니다.

```powershell
# 최초 한 번 (이미 .venv가 있으면 생략)
py -3.13 -m venv .venv

# 가상환경 활성화 없이 실행
.\.venv\Scripts\python.exe -m wifi_optimizer --check
```

VS Code에서 이 폴더를 열고 Python 인터프리터로 `.venv\Scripts\python.exe`를 선택합니다.
환경 확인 명령은 Python·SQLite·운영체제·Windows 측정 명령의 존재 여부만 확인합니다.

## 문서

- [16주 계획](plan.md)
- [요구사항 및 완료 기준](docs/requirements.md)
- [시스템 구조 및 데이터 설계](docs/architecture.md)
- [품질 평가 요소 조사](docs/quality-research.md)
- [기존 코드 검토 상태](docs/legacy-review.md)
- [개발 환경 및 GitHub 설정](docs/development.md)
- [1주차 진행 현황](docs/week01-status.md)
- [2주차 구현 및 검증](docs/week02-status.md)
- [3주차 구현 및 검증](docs/week03-status.md)
- [4주차 구현 및 검증](docs/week04-status.md)

## 폴더 구조

```text
wifi_optimizer/
  __main__.py       환경 확인용 실행 진입점
  collectors/       Windows Wi-Fi·ICMP Ping·HTTPS 속도 측정
  measurement.py    한 번의 수동 품질 측정 통합
  collector.py      자동 측정 주기·시작/중지·로그·결과 큐
  storage/          SQLite 저장 및 조회 (5주차)
  analysis/         품질 평가 및 규칙 진단 (8·11·12주차)
  visualization/    Dashboard·그래프·Heatmap (6·7·10주차)
  optimization/     AP 및 설정 개선 추천 (12주차)
docs/               요구사항·설계·조사·진행 기록
tests/              이후 구현 기능의 자동 검증
data/               로컬 측정 데이터 (Git 제외)
logs/               실행 로그 (Git 제외)
gui.py              Tkinter 모니터링 화면
```

개발 우선순위: 측정 정확성 → 데이터 저장 → 시각화 → 공간 분석 → 자동 진단 → 최적화 추천.
