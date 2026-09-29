# 5주차 — 테이블 생성 및 저장 API

2026-09-29: SQLite 스키마 v1·저장 계층·Collector 자동 저장·조회 API·CLI·GUI 구현.
최종 상태 (2026-09-30): 5주차 완료. 자동 테스트 51개, 정상/미연결 실측 저장·재조회,
사용자의 실제 GUI 기록 조회 동작 확인을 반영했다. 6주차는 다음 작업으로 보류한다.

## DB 생성

프로젝트 폴더에서 실행한다. 기존 v1 DB는 데이터를 유지한 채 연다.

```powershell
.\.venv\Scripts\python.exe -m wifi_optimizer.storage
# 다른 파일을 지정할 수도 있다.
.\.venv\Scripts\python.exe -m wifi_optimizer.storage --db data/another.sqlite3
```

기본 위치는 프로젝트의 `data/wifi_optimizer.sqlite3`다. Space, Location, AP, Session,
Measurement, PingResult, SpeedResult, SpeedTransfer에 대응하는 8개 테이블을 생성한다.
실제 SQL 이름은 `space`, `location`, `ap`, `session`, `measurement`, `ping_result`,
`speed_result`, `speed_transfer`다. 알 수 없는 버전이나 기존의 무버전 DB에는 쓰지 않는다.

## Python에서 저장

아래 코드는 실제 Wi-Fi·Ping 측정을 한 번 실행하고 저장하는 사용 예다.
DB 초기화 명령 자체는 네트워크 측정이나 예제 데이터 삽입을 하지 않는다.

```python
from wifi_optimizer.measurement import measure_quality
from wifi_optimizer.storage import MeasurementStore

with MeasurementStore() as store:
    session_id = store.create_session(mode="manual", config={"target": "1.1.1.1"})
    result = measure_quality(target="1.1.1.1")
    measurement_id = store.save_measurement(session_id, result)
    store.finish_session(session_id)
    print(measurement_id)
```

`create_space()`와 `create_location()`으로 위치를 만들고 `save_measurement(..., location_id=...)`로
연결할 수 있다. 미지정 위치는 NULL이다. 예제 데이터를 저장할 때는 세션의 `data_kind="example"`을 쓴다.
같은 세션·순번·원본·위치 문맥으로 재시도하면 기존 ID를 반환하고, 다른 내용이면
`DuplicateMeasurementError`를 발생시킨다. 종료된 세션에 새 결과를 추가할 수 없다.

DB 연결은 생성한 스레드에서만 사용한다. 저장 API 호출은 각자 트랜잭션을 완료하며
AP·측정·하위 결과 중 하나라도 실패하면 해당 측정의 전체 저장을 롤백한다.
타임존 없는 시각, NaN·무한대, 음수 속도 등 유효하지 않은 입력은 거부한다.
원본은 JSON으로 보존하고 조회용 시각은 UTC로 정규화한다.

## 검증 범위

테이블·저장 API 구현 시 자동 테스트 38개 통과. 자동 저장 연결 후 추가 검증은 아래에 기록한다.
기본 경로에서 초기화 명령을 실행해 DB를 생성했고 Git 제외도 확인했다.

`tests/test_storage.py`는 임시 DB로 다음을 검증한다.

- 스키마 버전·외래 키·대기 시간 설정과 DB 재열기
- 위치·AP 관계, 한글 원본, UTC 시각 및 JSON 보존
- Ping 100% 손실·전송 실패, Wi-Fi 실패·취소, 속도 부분 실패·미요청
- 동일 결과 재시도와 다른 내용의 충돌, AP 재사용·세션 종료
- 하위 결과 실패 시 AP까지 롤백, 잘못된 위치·비유한값 거부
- 지원하지 않는 DB가 변경되지 않는지 확인

시간·AP·위치별 조회 API와 기록 조회 UI도 구현했다. 사용법과 검증 범위는 아래와 같다.

## Collector 자동 저장

GUI 자동 측정과 CLI `--monitor`는 기본 DB에 자동 저장한다. `--monitor --db <파일>`로 경로를
변경할 수 있다. `--measure`와 `--wifi`는 기존대로 DB 자동 저장 없이 결과를 출력한다.

- 측정 완료 → DB 트랜잭션 → 화면 큐 순서다. 화면 큐 초과로 버려진 결과도 DB에는 남는다.
- 결과 JSON의 `storage.status`는 `saved`/`error`다. 성공하면 measurement_id와 session_id를 포함한다.
  저장 상태는 측정 상태와 구분하며 DB 원본 JSON에는 저장 후 부가된 storage 필드를 넣지 않는다.
- 저장 실패 시 결과는 계속 전달하고 실패 횟수·오류를 별도로 기록한다. 다음 측정에서 DB를 다시 열어
  저장을 시도한다. 실패했던 과거 결과를 자동 재전송하지 않는다.
- GUI에는 저장 결과와 누적 오류를 표시한다. CLI는 결과별 저장 상태를 출력하고 저장/세션 종료 오류가
  한 번이라도 있으면 종료 코드 2와 stderr 요약을 반환한다. 측정 자체의 오류는 기존대로 결과 status로 확인한다.
- 같은 Collector의 중지·재시작은 세션과 순번을 유지한다. GUI에서 설정을 바꾸면 기존 세션을 닫고
  새 Collector를 만든다. 정상 close 시 종료 작업자가 세션 시각을 기록하고 연결을 닫는다.
- 종료는 진행 중인 저장까지 기다린다. GUI는 종료 작업도 비동기로 기다려 창의 이벤트 처리를 유지한다.
  비정상 종료 또는 종료 기록 실패 시 session.finished_at은 NULL로 남을 수 있다.
- 자동 저장의 위치는 현재 NULL이다. 위치 지정 기능은 이후 단계다.

통합 테스트는 임시 DB와 예제 결과로 큐 초과·재시작·세션 종료, 저장 중 종료 대기,
초기화/저장 실패 후 결과 전달·다음 주기 복구, CLI 출력·오류 종료 코드를 확인한다.
최종 자동 테스트는 기존 테스트를 포함해 43개 모두 통과했다.
GUI 실제 창에서의 표시와 실측 네트워크 저장은 이번 자동 테스트에 포함하지 않는다.

## 저장 기록 조회

GUI 하단의 **저장 기록 조회**를 누른다. 최근 실측 기록 100개를 보여주며 시간·BSSID·위치 ID와
실측/예제/전체 조건을 적용할 수 있다. **이전 기록 100개**로 과거 페이지를 읽고 **조회 / 최신 기록**으로
처음부터 다시 조회한다. 한 행을 선택하면 저장 문맥과 전체 원본 결과를 아래 JSON 영역에 표시한다.
위치 지정 기능은 아직 없으므로 현재 자동 측정의 위치는 미지정이다.

목록의 Ping·손실은 외부 대상 기준이다. 게이트웨이 Ping, 속도 방향별 상태, RSSI 출처,
오류·경고는 상세 결과에서 확인한다. 누락값은 `—`로 표시하며 실측과 예제는 종류 열에서 구분한다.
화면의 목록 시각은 PC 현지 시각, 상세 정규화 필드와 CLI 목록 시각은 UTC다.

```powershell
# 최신 실측 20개 (JSON)
.\.venv\Scripts\python.exe -m wifi_optimizer --history --limit 20
# 한국 시간 9시 이상 10시 미만
.\.venv\Scripts\python.exe -m wifi_optimizer --history --from "2026-09-29T09:00:00+09:00" --to "2026-09-29T10:00:00+09:00"
# AP/위치/세션별 필터를 조합 가능
.\.venv\Scripts\python.exe -m wifi_optimizer --history --bssid "aa:bb:cc:dd:ee:ff" --location-id 1
.\.venv\Scripts\python.exe -m wifi_optimizer --history --ap-id 1
# 저장 문맥과 전체 원본 결과 (개별 ID 조회는 실측/예제 모두 가능)
.\.venv\Scripts\python.exe -m wifi_optimizer --history --record-id 1
# 다른 DB의 예제까지 포함
.\.venv\Scripts\python.exe -m wifi_optimizer --history --db data/custom.sqlite3 --data-kind all
```

시각 입력은 `Z` 또는 `+09:00` 같은 시간대가 있는 ISO 8601 형식이다. 종료 시각은 포함하지 않는다.
기본 목록은 실측만 포함하며 `--data-kind example`으로 예제만 볼 수 있다. 조회 결과가 없으면
빈 배열과 종료 코드 0, 상세 ID가 없으면 코드 1, DB·입력 오류는 코드 2를 반환한다.
DB가 없으면 오류를 안내하고 파일을 새로 만들지 않는다. 먼저 자동 측정이나 DB 초기화를 실행한다.

Python API는 `MeasurementStore(path, readonly=True)`에서 `list_measurements(...)`와
`get_measurement(id)`를 사용한다. list의 `before=(마지막 started_at, 마지막 id)`로 다음 페이지를
조회할 수 있다. 예제 포함은 `data_kind=None`이다. 쿼리는 매개변수를 바인딩하고 모든 조회는
별도 읽기 전용 연결로 수행한다. GUI의 DB 작업은 작업자에서 실행하고 Tk 위젯은 메인 스레드에서 갱신한다.

조회 테스트는 파일 재열기, 시간 경계·AP·위치·세션 필터, 같은 시각의 정렬과 페이지 이동,
NULL·부분 실패·원본 보존, 예제 분리, 입력 검증, 읽기 전용 동작, CLI 출력과 종료 코드를 검증한다.
숨겨진 Tk 창으로 GUI 목록·선택 상세·빈 결과·DB 오류 처리도 테스트한다.
조회 기능 추가 후 최종 자동 테스트 51개가 모두 통과했다.
실제 표시 화면의 시각적 검수와 네트워크 실측 최종 인수 검증은 별도로 남아 있다.

위 문장은 조회 기능 구현 직후의 검증 범위다. 이후 실환경·사용자 확인 결과는 아래 최종 기록을 따른다.

## 2026-09-30 실환경 검증

- 전체 자동 테스트 51개 재실행 통과 (숨겨진 Tk 창 테스트 포함).
- `--monitor --samples 2 --interval 1 --db data/validation_sep30.sqlite3` 실행 완료.
  현재 연결된 Wi-Fi가 감지되지 않아 두 결과 모두 `status=error`, `error_code=disconnected`였다.
  두 결과의 `storage.status=saved`와 서로 다른 측정 ID를 확인했다.
- 별도 CLI 프로세스로 기록 2를 재조회해 오류 코드·시각·원본 보존과 Wi-Fi/Ping 미측정 상태를 확인했다.
- 검증 DB의 측정 수 2개, integrity_check=ok, foreign_key_check 위반 0개,
  세션 finished_at 기록을 확인했다. 실측 기록은 Git 제외 파일에 로컬 보관한다.
- GUI 프로세스는 실행했으나 Computer Use가 `native pipe is unavailable` 연결 오류를
  두 번 반환하여 화면 캡처·클릭 검수를 수행하지 못했다. 검수용 GUI 프로세스는 종료했다.
  GUI 자동 시작으로 기본 DB에 미연결 측정 기록이 추가될 수 있으며, 강제 종료한 GUI 세션의
  finished_at은 NULL로 남을 수 있다. 검증용 CLI 세션의 정상 종료와 구분한다.

남은 인수 검증: Wi-Fi 연결 상태에서 정상 RSSI·Ping의 저장/재조회, 실제 표시 화면의
목록·상세·필터 가독성과 클릭 흐름 확인. 현재 결과를 정상 연결 실측 또는 시각적 검수 통과로 보지 않는다.

### Wi-Fi 연결 후 추가 검증 (2026-09-30 00:05 KST)

- `--monitor --samples 2 --interval 1 --db data/validation_sep30_connected.sqlite3` 실행.
  두 측정 모두 status=ok, storage.status=saved, 경고 없음.
- 5 GHz·채널 149, 드라이버 실측 RSSI -54 dBm (두 표본), 신호 100% 확인.
- 게이트웨이 평균 Ping 1.00/1.25 ms, 외부 평균 Ping 8.00/8.25 ms.
  각 대상·표본의 송신/수신은 4/4, 손실률 0%. 속도 측정은 요청하지 않았다.
- 별도 프로세스의 읽기 전용 연결에서 해당 세션의 기록 2건과 상세 원본을 재조회했다.
  RSSI 출처·외부 Ping·손실률·게이트웨이 상태, 시간/AP/세션 조합 필터의 결과를 assertion으로 검증했다.
- integrity_check=ok, 외래 키 위반 없음, 세션 종료 시각 기록 확인.
- Computer Use 재확인도 native pipe 연결 오류로 실패했다. 정상 연결 실측 저장/조회 검증은
  완료했으며, 실제 화면의 시각적 검수·클릭 흐름 확인은 여전히 남아 있다.

### 사용자 화면 확인 및 작업 종료

- GUI 직접 실행 후 `Wi-Fi 품질 모니터링` 창 생성과 정상 응답을 확인했다.
- 사용자가 실제 화면에서 **저장 기록 조회도 잘 작동한다**고 확인했다.
- 자동화 도구로 스크린샷을 검사한 것은 아니며, 실제 GUI 동작 확인은 사용자 확인에 근거한다.
- 5주차 저장·조회 구현과 검증을 완료 처리한다. 위치 지정 기능은 9주차 범위다.
- 다음 작업: 6주차 Dashboard 정리·확장. 사용자 요청에 따라 이번에는 시작하지 않는다.
