# Wi-Fi 무선 네트워크 품질 분석 및 최적화 시스템

Windows에서 Wi-Fi 측정 데이터를 수집·저장하고 공간별 품질과 개선 방법을 보여주는 16주 프로젝트입니다.

GitHub 저장소: [mudkip0122/WIFI-NETWORK-OPTIMIZER](https://github.com/mudkip0122/WIFI-NETWORK-OPTIMIZER)

현재 단계: **1주차 기획 및 개발 기반 구성**. 실제 Wi-Fi 수집, Dashboard, Heatmap은 이후 주차에 구현합니다.

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

## 폴더 구조

```text
wifi_optimizer/
  __main__.py       환경 확인용 실행 진입점
  collectors/       Windows Wi-Fi / Ping / 속도 수집 (2~4주차)
  storage/          SQLite 저장 및 조회 (5주차)
  analysis/         품질 평가 및 규칙 진단 (8·11·12주차)
  visualization/    Dashboard·그래프·Heatmap (6·7·10주차)
  optimization/     AP 및 설정 개선 추천 (12주차)
docs/               요구사항·설계·조사·진행 기록
tests/              이후 구현 기능의 자동 검증
data/               로컬 측정 데이터 (Git 제외)
logs/               실행 로그 (Git 제외)
```

개발 우선순위: 측정 정확성 → 데이터 저장 → 시각화 → 공간 분석 → 자동 진단 → 최적화 추천.
