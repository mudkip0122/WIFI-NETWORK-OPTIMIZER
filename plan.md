# Wi-Fi 무선 네트워크 품질 분석 및 최적화 시스템

## 1. 프로젝트 개요

### 프로젝트명

**Wi-Fi 무선 네트워크 품질 분석 및 최적화 시스템**

### 영문명

**Wi-Fi Network Quality Analysis and Optimization System**

### 개발 기간

**4개월 / 총 16주**

### 프로젝트 목표

Wi-Fi 환경에서 RSSI, Ping, Packet Loss, Download/Upload Speed,
Channel, Frequency Band 등의 데이터를 수집하여 무선 네트워크의
품질을 분석하고 시각화하는 시스템을 개발한다.

공간별 측정 데이터를 기반으로 Wi-Fi 품질 Heatmap을 생성하고,
신호 음영지역 및 품질 저하 구간을 탐지한다.

최종적으로 측정 결과를 분석하여 Wi-Fi 품질 저하 원인을 진단하고,
AP 위치 및 네트워크 설정 개선 방안을 사용자에게 제안하는 것을 목표로 한다.

기존 Wi-Fi 측정 프로그램을 발전시키고, Heatmap → 품질 분석 →
AP 최적화 추천 → 최종 시연으로 완성한다.

---

## 2. 주요 기능

### 2.1 Wi-Fi 정보 수집

수집 대상 데이터

- SSID
- BSSID
- RSSI (dBm)
- Signal Strength (%)
- Ping (ms)
- Packet Loss (%)
- Download Speed (Mbps)
- Upload Speed (Mbps)
- Channel
- Frequency Band (2.4 GHz / 5 GHz)
- 측정 시간
- 측정 위치

### 2.2 실시간 네트워크 모니터링

- 현재 Wi-Fi 연결 상태 표시
- RSSI 실시간 그래프
- Ping 실시간 그래프
- Packet Loss 표시
- 네트워크 속도 측정
- 현재 AP 정보 표시

### 2.3 데이터 저장 및 관리

- Wi-Fi 측정 결과 저장
- 측정 위치 저장
- 측정 시간 저장
- 측정 기록 조회
- 위치별 평균 품질 계산

초기 개발에서는 SQLite를 사용한다.

### 2.4 Wi-Fi 품질 분석

측정 데이터를 기반으로 Wi-Fi 품질을 분석한다.

예시 평가 항목

- 신호 세기
- 네트워크 지연시간
- 패킷 손실률
- 다운로드 속도
- 업로드 속도
- 채널 상태

분석 결과는 다음과 같이 표시한다.

- 매우 좋음
- 좋음
- 보통
- 나쁨
- 매우 나쁨

### 2.5 공간별 Wi-Fi Heatmap

사용자가 공간 또는 평면도에서 측정 위치를 지정하면
각 위치의 Wi-Fi 측정 결과를 저장한다.

여러 위치의 측정 데이터를 기반으로 Wi-Fi 품질 Heatmap을 생성한다.

Heatmap을 통해 다음 정보를 확인할 수 있도록 한다.

- 신호 강도가 높은 영역
- 신호 강도가 낮은 영역
- 네트워크 품질이 낮은 영역
- Wi-Fi 음영지역

### 2.6 Wi-Fi 품질 자동 진단

측정된 여러 지표를 분석하여 네트워크 상태를 자동으로 진단한다.

| 측정 상태 | 예상 원인 |
|---|---|
| RSSI가 낮고 Ping이 정상인 경우 | AP와의 거리 또는 장애물로 인한 신호 감쇠 가능성 |
| RSSI가 높지만 Ping이 높은 경우 | 네트워크 혼잡 또는 채널 간섭 가능성 |
| Packet Loss가 높은 경우 | 무선 간섭 또는 연결 불안정 가능성 |

### 2.7 Wi-Fi 최적화 추천

분석 결과를 기반으로 사용자에게 개선 방법을 제공한다.

- AP 위치 이동 권장
- 추가 AP 설치 권장
- 2.4 GHz / 5 GHz 대역 변경 권장
- Wi-Fi 채널 변경 권장
- 장애물 영향을 고려한 AP 위치 조정
- 특정 지역의 Wi-Fi 음영지역 개선

자동 진단 및 AP 최적화 추천은 **규칙 기반 알고리즘으로 먼저 구현**한다.
머신러닝 기반 품질 예측은 핵심 기능을 완성한 이후 추가 기능으로 고려한다.

---

## 3. 전체 시스템 구조

```text
Wi-Fi Network
    ↓
Wi-Fi Data Collector
    ├─ RSSI
    ├─ Ping
    ├─ Packet Loss
    ├─ Download / Upload
    ├─ Channel
    └─ Frequency Band
    ↓
Data Processing
    ↓
Database
    ↓
Quality Analysis Engine
    ├─ Signal Analysis
    ├─ Latency Analysis
    ├─ Packet Loss Analysis
    └─ Channel Analysis
    ↓
Visualization
    ├─ Real-time Graph
    ├─ Dashboard
    └─ Wi-Fi Heatmap
    ↓
Optimization Engine
    ↓
Wi-Fi Optimization Recommendation
```

---

## 4. 4개월 개발 일정

### 1개월차 - 기획 및 Wi-Fi 측정 시스템 개발

#### 1주차 - 프로젝트 기획 및 요구사항 정의

진행 기록 및 산출물: [1주차 진행 현황](docs/week01-status.md).

**목표**

프로젝트의 전체적인 개발 범위와 기능을 결정한다.

**주요 작업**

- 프로젝트 목표 정의
- 기존 Wi-Fi Signal Strength Visualizer 코드 분석
- 기존 프로젝트에서 재사용 가능한 기능 확인
- 주요 기능 선정
- Wi-Fi 품질 평가 요소 조사
- 개발 환경 구성
- GitHub Repository 생성
- 프로젝트 폴더 구조 설계

**개발 환경**

- Python
- Git / GitHub
- VS Code
- SQLite

**산출물**

- 프로젝트 요구사항 문서
- 시스템 구성도
- GitHub Repository
- 초기 프로젝트 구조

#### 2주차 - Wi-Fi 기본 정보 수집 기능 개발

**목표**

현재 연결된 Wi-Fi의 기본 정보를 가져오는 기능을 구현한다.

**주요 작업**

- SSID 확인
- BSSID 확인
- RSSI 측정
- Signal Strength 측정
- Wi-Fi Channel 확인
- Frequency Band 확인
- 네트워크 인터페이스 확인
- Windows netsh 명령어 연동

**출력 예시**

```text
SSID       : Campus_WiFi
BSSID      : XX:XX:XX:XX:XX:XX
RSSI       : -58 dBm
Signal     : 82 %
Channel    : 36
Band       : 5 GHz
```

**완료 기준**

현재 연결된 Wi-Fi 정보를 프로그램에서 정상적으로 출력할 수 있어야 한다.

#### 3주차 - 네트워크 품질 측정 기능 개발

**목표**

Wi-Fi 신호뿐만 아니라 실제 네트워크 품질을 측정한다.

**주요 작업**

- Ping 측정
- 평균 Ping 계산
- 최소/최대 Ping 계산
- Packet Loss 측정
- Download Speed 측정
- Upload Speed 측정
- 측정 오류 처리

**완료 기준**

다음 데이터를 하나의 측정 결과로 생성할 수 있어야 한다.

```text
RSSI
Ping
Packet Loss
Download Speed
Upload Speed
Channel
Band
```

#### 4주차 - Wi-Fi Collector 통합

**목표**

1개월 동안 개발한 측정 기능을 하나의 모듈로 통합한다.

**주요 작업**

- Wi-Fi Collector 클래스 설계
- RSSI 측정 모듈 통합
- Ping 측정 모듈 통합
- Packet Loss 측정 모듈 통합
- Speed 측정 모듈 통합
- 일정 시간 간격 자동 측정
- 예외 처리
- 로그 기록

**완료 기준**

프로그램 실행 시 Wi-Fi 상태를 일정 주기로 자동 측정할 수 있어야 한다.

---

### 2개월차 - 데이터 저장 및 Dashboard 개발

#### 5주차 - 데이터베이스 구축

**목표**

Wi-Fi 측정 데이터를 저장할 수 있는 구조를 만든다.

**주요 작업**

- SQLite DB 설계
- Measurement Table 생성
- Location Table 생성
- AP Table 생성
- 측정 결과 저장
- 측정 기록 조회
- 시간 정보 저장

**데이터 예시**

```text
measurement_id
timestamp
location_x
location_y
ssid
bssid
rssi
ping
packet_loss
download_speed
upload_speed
channel
band
```

**완료 기준**

측정 결과가 자동으로 DB에 저장되고 다시 조회되어야 한다.

#### 6주차 - 실시간 Wi-Fi Dashboard 개발

**목표**

Wi-Fi 상태를 한 화면에서 확인할 수 있도록 한다.

**주요 작업**

- 현재 Wi-Fi 정보 표시
- RSSI 표시
- Ping 표시
- Packet Loss 표시
- Download / Upload 표시
- Channel 표시
- Frequency Band 표시
- 기본 Dashboard UI 제작

**완료 기준**

현재 네트워크 상태를 Dashboard에서 실시간으로 확인할 수 있어야 한다.

#### 7주차 - 실시간 그래프 구현

**목표**

시간에 따른 네트워크 품질 변화를 시각화한다.

**주요 작업**

- RSSI 그래프
- Ping 그래프
- Packet Loss 그래프
- Download Speed 그래프
- 시간축 구현
- 그래프 자동 업데이트
- 최근 N개 데이터 표시

**완료 기준**

Wi-Fi 품질 변화가 실시간 그래프로 표현되어야 한다.

#### 8주차 - Wi-Fi 품질 평가 알고리즘 개발

**목표**

측정된 데이터를 기반으로 Wi-Fi 품질을 평가한다.

**주요 작업**

- RSSI 평가 기준 정의
- Ping 평가 기준 정의
- Packet Loss 평가 기준 정의
- 네트워크 속도 평가 기준 정의
- 종합 Wi-Fi Quality Score 설계
- 품질 등급 계산

**결과 예시**

```text
Wi-Fi Quality Score

RSSI          : 85
Ping          : 92
Packet Loss   : 95
Speed         : 88

Total Score   : 89

Quality       : GOOD
```

**완료 기준**

측정 데이터를 입력하면 자동으로 Wi-Fi 품질 등급이 계산되어야 한다.

---

### 3개월차 - 공간 분석 및 Wi-Fi 최적화

#### 9주차 - 공간별 측정 기능 개발

**목표**

Wi-Fi 데이터를 공간 위치와 함께 저장한다.

**주요 작업**

- 공간 좌표 시스템 구현
- 측정 위치 선택 기능
- 위치별 Wi-Fi 측정
- 위치별 데이터 저장
- 동일 위치 반복 측정
- 위치별 평균값 계산

**완료 기준**

각 측정 데이터에 공간 좌표가 함께 저장되어야 한다.

#### 10주차 - Wi-Fi Heatmap 개발

**목표**

공간별 Wi-Fi 품질을 Heatmap으로 표현한다.

**주요 작업**

- 좌표 기반 데이터 처리
- RSSI Heatmap 생성
- Ping Heatmap 생성
- Wi-Fi Quality Heatmap 생성
- 측정 지점 표시
- Heatmap 보간 방법 적용

**결과 예시**

```text
┌───────────────────────────┐
│ GOOD   GOOD   FAIR   BAD   │
│ GOOD   GOOD   FAIR   BAD   │
│ GOOD   GOOD   GOOD   FAIR  │
│                       AP  │
└───────────────────────────┘
```

**완료 기준**

여러 위치에서 측정한 Wi-Fi 데이터를 공간 Heatmap으로 확인할 수 있어야 한다.

#### 11주차 - Wi-Fi 음영지역 탐지

**목표**

Wi-Fi 품질이 일정 기준 이하인 지역을 자동 탐지한다.

**주요 작업**

- RSSI 임계값 설정
- 품질 점수 임계값 설정
- 음영지역 판별
- 연속된 저품질 영역 탐지
- Heatmap에서 음영지역 표시
- 음영지역 비율 계산

**결과 예시**

```text
Wi-Fi Coverage Analysis

전체 측정 영역 : 100 %

GOOD          : 64 %
FAIR          : 23 %
BAD           : 13 %

Wi-Fi 음영지역 : 13 %
```

**완료 기준**

품질이 낮은 위치를 시스템이 자동으로 판별할 수 있어야 한다.

#### 12주차 - Wi-Fi 자동 진단 및 최적화 추천

**목표**

측정 결과를 분석하여 Wi-Fi 환경 개선 방법을 제공한다.

**구현 원칙**

AP 최적화 추천은 처음부터 AI를 적용하지 않고 **규칙 기반 알고리즘으로 먼저 완성**한다.
측정 지표와 임계값의 조합으로 예상 원인과 개선 방법을 제시한다.
머신러닝 기반 품질 예측은 16주 핵심 기능 완성 후 시간이 남으면 추가한다.

**주요 작업**

- RSSI 기반 문제 분석
- Ping 기반 문제 분석
- Packet Loss 기반 문제 분석
- Channel 분석
- Frequency Band 분석
- 문제 원인 분류
- 개선 방법 추천
- AP 위치 변경 추천 로직 구현

**결과 예시**

```text
[Wi-Fi Analysis]

Quality : BAD

문제점
- RSSI가 낮음
- 특정 지역에서 신호 품질 급격히 감소

예상 원인
- AP와 측정 위치 사이의 거리
- 벽 또는 장애물에 의한 신호 감쇠

추천
- AP를 공간 중앙 방향으로 이동
- 추가 AP 설치 검토
- 5 GHz 신호 도달 범위 확인
```

**완료 기준**

Wi-Fi 품질 문제를 자동으로 분석하고 개선 방법을 출력할 수 있어야 한다.

---

### 4개월차 - 시스템 통합 및 최종 완성

#### 13주차 - 전체 시스템 통합

**목표**

개별적으로 개발한 기능을 하나의 시스템으로 통합한다.

**통합 대상**

- Wi-Fi Collector
- Database
- Dashboard
- 실시간 Graph
- Quality Score
- Location Measurement
- Heatmap
- 자동 진단
- Optimization Recommendation

**주요 작업**

- 모듈 연결
- 데이터 흐름 점검
- UI 통합
- 오류 처리
- 성능 개선

**완료 기준**

프로그램 하나에서 전체 기능을 사용할 수 있어야 한다.

#### 14주차 - 실제 환경 테스트

**목표**

실제 Wi-Fi 환경에서 시스템의 성능을 검증한다.

**테스트 장소 예시**

- 강의실
- 동아리방
- 복도
- 실습실

**주요 작업**

- 장소별 Wi-Fi 측정
- AP 근처 측정
- AP에서 먼 위치 측정
- 벽이 있는 환경 측정
- 2.4 GHz / 5 GHz 비교
- 반복 측정을 통한 결과 비교
- Heatmap 정확도 확인
- 오류 및 버그 수정

**완료 기준**

실제 공간에서 Wi-Fi 품질 차이가 시스템 결과에 정상적으로 반영되어야 한다.

#### 15주차 - 시스템 개선 및 UI 완성

**목표**

테스트 결과를 기반으로 프로그램의 완성도를 높인다.

**주요 작업**

- 버그 수정
- UI 개선
- Dashboard 정리
- 그래프 가독성 개선
- Heatmap 개선
- 품질 분석 알고리즘 보정
- 최적화 추천 알고리즘 보정
- 예외 처리 강화
- 프로그램 안정성 테스트

**완료 기준**

최종 발표에서 안정적으로 시연할 수 있는 버전을 완성한다.

#### 16주차 - 최종 발표 및 문서화

**목표**

프로젝트 결과를 정리하고 최종 발표를 준비한다.

**주요 작업**

- 최종 README 작성
- 프로젝트 소개 작성
- 시스템 구성도 작성
- 기능 설명 작성
- 테스트 결과 정리
- Wi-Fi Heatmap 결과 정리
- 프로젝트 발표 PPT 제작
- 시연 영상 제작
- GitHub Repository 정리
- 코드 주석 및 구조 정리

**최종 시연 시나리오**

1. 프로그램 실행
2. 현재 Wi-Fi 연결 정보 확인
3. RSSI / Ping / Packet Loss 실시간 측정
4. 여러 위치에서 Wi-Fi 품질 측정
5. 측정 데이터 저장
6. 공간별 Wi-Fi Heatmap 생성
7. Wi-Fi 음영지역 탐지
8. Wi-Fi 품질 자동 분석
9. AP 배치 및 설정 개선 방법 출력

---

## 5. 월별 목표

| 기간 | 목표 | 핵심 결과물 |
|---|---|---|
| 1개월차 | Wi-Fi 측정 시스템 구축 | Wi-Fi Collector |
| 2개월차 | 데이터 저장 및 시각화 | DB + Dashboard |
| 3개월차 | 공간 분석 및 최적화 | Heatmap + 분석 엔진 |
| 4개월차 | 통합 및 검증 | 최종 프로그램 |

---

## 6. 프로젝트 최종 결과물

프로젝트 종료 시 다음 결과물을 완성한다.

- Wi-Fi 실시간 측정 프로그램
- Wi-Fi 품질 Dashboard
- Wi-Fi 측정 데이터베이스
- RSSI / Ping / Packet Loss 분석
- Wi-Fi Quality Score
- 공간별 Wi-Fi Heatmap
- Wi-Fi 음영지역 탐지
- Wi-Fi 자동 진단
- AP 배치 및 설정 최적화 추천
- 프로젝트 GitHub Repository
- 프로젝트 README
- 최종 발표 자료
- 시연 영상

---

## 7. 프로젝트 성공 기준

다음 조건을 만족하면 프로젝트의 핵심 목표를 달성한 것으로 판단한다.

1. Wi-Fi RSSI를 실시간으로 측정할 수 있다.
2. Ping과 Packet Loss를 측정할 수 있다.
3. Wi-Fi Channel 및 Frequency Band를 확인할 수 있다.
4. 측정 데이터를 데이터베이스에 저장할 수 있다.
5. 시간에 따른 Wi-Fi 품질 변화를 그래프로 확인할 수 있다.
6. 공간별 Wi-Fi 측정이 가능하다.
7. 측정 데이터를 기반으로 Wi-Fi Heatmap을 생성할 수 있다.
8. Wi-Fi 품질이 낮은 음영지역을 탐지할 수 있다.
9. Wi-Fi 품질을 자동으로 평가할 수 있다.
10. 측정 결과를 기반으로 Wi-Fi 환경 개선 방법을 제안할 수 있다.

---

## 8. 추가 개발 가능 기능

16주 내 핵심 기능이 조기에 완성된 경우 다음 기능을 추가로 고려한다.

- 여러 AP 동시 비교
- Wi-Fi Channel 혼잡도 분석
- 주변 AP Scan
- 2.4 GHz / 5 GHz 품질 비교
- Wi-Fi Roaming 분석
- Raspberry Pi 기반 이동형 측정 장치
- 웹 기반 Dashboard
- 머신러닝 기반 Wi-Fi 품질 예측
- 이상 네트워크 상태 자동 탐지
- AP 최적 위치 자동 계산
- 측정 결과 PDF Report 생성

---

## 9. 개발 우선순위

프로젝트 개발 과정에서는 다음 우선순위를 따른다.

**측정 정확성 > 데이터 저장 > 시각화 > 공간 분석 > 자동 진단 > 최적화 추천**

Heatmap이나 최적화 기능보다 정확한 Wi-Fi 측정 데이터를 확보하는 것을
우선하며, 핵심 기능이 안정적으로 동작한 이후 추가 기능을 구현한다.
