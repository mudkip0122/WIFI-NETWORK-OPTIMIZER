# 2주차 - Wi-Fi 기본 정보 수집

## 구현

- `collectors/wifi.py`: 한글·영어 netsh 출력에서 인터페이스별 정보를 분리한다.
- SSID, BSSID, 신호 %, 채널, 명시된 주파수 대역, 인터페이스 이름·GUID·설명을 수집한다.
- `collectors/native.py`: Windows WlanQueryInterface RSSI opcode로 드라이버 RSSI를 조회한다.
- 드라이버 조회 실패 시 신호 %를 dBm으로 환산하고 출처 및 경고를 반환한다.
- 명시되지 않은 대역은 unknown(null)으로 남긴다. 6 GHz도 표시할 수 있다.
- 데이터는 UTC 측정 시각과 함께 반환한다. DB 저장은 5주차 범위다.
- CLI의 --wifi, --json, --interface 옵션과 GUI 연결 정보 표시를 추가했다.
- AP·인터페이스·대역이 바뀌면 GUI의 최근 표본을 초기화하여 서로 다른 연결의 추세를 섞지 않는다.
- 미연결·권한 거부·타임아웃·다중 연결·인터페이스 없음은 상태 코드로 구분한다.

## 검증

- 자동 테스트: 신호 수집 5개 + 기본 정보 7개, 총 12개 통과.
- 한국어/영어, UTF-8/CP949, SSID 내 콜론, AP BSSID/BSSID,
  손상·누락 값, 미연결, 다중 인터페이스 선택, 실측/추정 출처를 검증한다.
- 실제 환경에서 Wi-Fi 연결 해제 상태의 오류 반환을 확인했다.
- 예제 데이터로 실제 Tk 이벤트 루프에서 GUI 정보(SSID·RSSI·대역) 및 그래프 3개 점 반영을 확인했다.
- Wi-Fi 재연결 후 실제 SSID·BSSID·인터페이스·채널·대역 조회에 성공했다.
- 실측 예: 신호 100%, Native Wi-Fi RSSI -43 dBm, 채널 4, 2.4 GHz, 경고 없음.
- 실제 Tk 이벤트 루프에서 5개 표본과 그래프 점 5개를 확인했다. 연결 정보 라벨의
  SSID·BSSID·RSSI·채널·대역 표시도 검증했다. 이때 RSSI는 -40 dBm으로 관측됐다.
- 2주차 완료 기준인 현재 연결된 Wi-Fi 정보의 정상 출력과 GUI 반영을 충족했다.

## 제한

netsh 조회와 Native RSSI 조회는 별도 호출이므로 한 순간의 원자적 스냅샷은 아니다.
지원 출력 언어는 한국어·영어다. 다른 언어는 정보 확인 불가로 처리한다.
100%에서 환산 RSSI -50 dBm은 실제 값이 더 강한지 구분하지 못한다.
장치의 RSSI 지원 여부는 드라이버에 따라 다르며 실패를 숨기지 않고 warnings에 기록한다.
무선 연결 정보 표시가 인터넷 연결이나 속도·품질 평가를 의미하지는 않는다.

## API 근거

- [Microsoft WLAN_INTF_OPCODE](https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/ne-wlanapi-wlan_intf_opcode)
- [Microsoft WlanQueryInterface](https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/nf-wlanapi-wlanqueryinterface)
- [신호 % 환산 근거](https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/ns-wlanapi-wlan_association_attributes)

Native API가 반환한 메모리는 WlanFreeMemory로 해제하고 핸들은 finally에서 닫는다.
