# 개발 환경

## 기준

- OS: Windows
- Python: 3.13, 프로젝트별 .venv
- SQLite: Python 표준 sqlite3 모듈
- Git / GitHub
- VS Code
- 1주차 외부 Python 의존성: 없음

## 실행

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m wifi_optimizer --check
.\.venv\Scripts\python.exe -m wifi_optimizer --version
```

첫 명령은 이미 가상환경이 생성되어 있으면 생략한다.
PowerShell 실행 정책을 변경할 필요 없이 가상환경 Python을 직접 실행한다.
VS Code Python 확장이 설치되어 있지 않다면 Microsoft Python 확장을 설치하고 인터프리터를 선택한다.

## GitHub 연결

사용자 지정 저장소: https://github.com/mudkip0122/WIFI-NETWORK-OPTIMIZER.git
기존 원격 저장소의 공개 범위를 유지한다.
기존 개인 홈의 Git 저장소를 상속하지 않도록 이 폴더에 독립 저장소를 초기화한다.

GitHub CLI 또는 브라우저 인증을 준비한 뒤 새 원격 저장소를 생성하고 origin으로 연결한다.
비밀 토큰은 문서·소스·채팅에 기록하지 않는다.
원격 생성 및 push가 완료되면 README와 진행 현황에 실제 URL을 기록한다.

## 검증

환경 확인 명령은 메모리 SQLite 쿼리를 실행하고 netsh/ping 명령 존재를 확인한다.
실제 Wi-Fi 측정·권한·연결 여부 검증은 2주차에 수행한다.
추후 테스트는 tests 폴더에 추가하며 현재 빈 테스트를 통과 결과로 보고하지 않는다.
