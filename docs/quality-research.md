# Wi-Fi 품질 평가 요소 조사

조사일: 2026-09-24. 아래 초기 기준은 프로젝트 가설이며 8주차 설계 및 14주차 실측으로 보정한다.

## 근거와 측정상의 의미

Microsoft WLAN 문서는 signal quality 0~100과 RSSI -100~-50 dBm 사이의 관계 및 중간값 선형 보간을 설명한다.
따라서 signal / 2 - 100은 추정 변환에 사용할 수 있지만 원래 수신한 실측 dBm과 구별해야 한다.
[Microsoft WLAN_ASSOCIATION_ATTRIBUTES](https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/ns-wlanapi-wlan_association_attributes)

최근 Windows의 일부 BSSID 관련 API는 위치 접근 동의가 없으면 접근 거부를 반환한다.
이 상태는 Wi-Fi 미연결이나 신호 약함과 별도로 처리한다.
[Microsoft Wi-Fi access and location](https://learn.microsoft.com/en-us/windows/win32/nativewifi/wi-fi-access-location-changes)

Cisco 사이트 서베이 문서의 음성 단말 설계 사례는 -67 dBm 및 SNR 25 dB를 사용한다.
이는 용도별 설계 사례이며 모든 네트워크의 보편적인 합격 기준으로 사용하지 않는다.
[Cisco Site Survey Guidelines](https://www.cisco.com/c/en/us/support/docs/wireless/5500-series-wireless-controllers/116057-site-survey-guidelines-wlan-00.html)

## 지표별 설계

| 지표 | 해석 | 함께 기록할 조건 |
|---|---|---|
| RSSI / 신호 % | 무선 수신 강도, 값이 높을수록 강함 | 장치·AP·대역·실측/추정 출처 |
| RTT (Ping) | 대상까지 왕복 지연 | 게이트웨이/외부 대상, 패킷 수·타임아웃 |
| Packet Loss | 송신 대비 미수신 비율 | 표본 수, ICMP 응답 제한 가능성 |
| Download/Upload | 서버까지 경로의 실제 전송 성능 | 서버·측정 시각·동시 트래픽 |
| Channel / Band | 연결 맥락과 AP 비교 근거 | 중심 주파수, 확인 불가 여부 |

외부 Ping과 인터넷 속도는 ISP·서버·유선 경로 영향도 받으므로 Wi-Fi 원인으로 단정하지 않는다.
게이트웨이 Ping과 외부 Ping을 분리해 원인 후보를 좁힌다.
링크 속도와 실측 다운로드 속도는 다른 지표로 저장한다.

## 초기 평가 후보

RSSI 후보 구간: -55 이상 / -55 미만~-67 이상 / -67 미만~-75 이상 /
-75 미만~-85 이상 / -85 미만을 매우 좋음~매우 나쁨에 대응한다.
이 구간은 Cisco 표준이 아니라 프로젝트 초기 가설이다.

Ping은 게이트웨이와 외부 대상에 서로 다른 기준을 적용한다.
손실률은 100 × (sent - received) / sent이며 sent가 0이면 산출하지 않는다.
짧은 표본의 손실률은 불안정하므로 표본 수와 측정 창을 함께 표시한다.
속도는 일률적인 절대 등급보다 사용자 목표 Mbps 대비 달성률을 검토한다.

종합 점수는 RSSI·지연·손실·속도별 0~100 점수를 만든 후 가중 결합하는 방향이다.
가중치·세부 임계값은 8주차에 확정한다. 미측정 속도를 0점으로 간주하지 않으며,
누락 지표와 점수 산출에 사용한 지표를 공개하고 서로 다른 측정 조건의 점수 비교를 제한한다.

## 규칙 기반 진단 초안

- 약한 RSSI + 정상 지연: 거리·장애물 가능성, 위치 변경 후 반복 측정 제안.
- 강한 RSSI + 높은 게이트웨이 지연/손실: 혼잡·간섭·AP 처리 문제 가능성.
- 정상 게이트웨이 + 높은 외부 지연: 인터넷 경로·서버 영향 가능성.
- 특정 위치에서 반복적인 약한 RSSI: AP 이동 또는 추가 설치 검토.

각 추천에 관측값과 불확실성을 표시한다. 채널 번호만으로 간섭이나 최적 채널을 단정하지 않는다.
