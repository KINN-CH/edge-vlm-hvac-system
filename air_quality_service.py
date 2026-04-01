import requests


class AirQualityService:
    """
    [공기질 데이터 서비스]
    역할: 에어코리아 API를 통해 미세먼지 정보 수집

    수신 항목:
        - pm10   : 미세먼지 (PM10)
        - pm25   : 초미세먼지 (PM2.5)
        - khai   : 통합대기환경지수
    """

    def __init__(self, service_key: str, station_name: str = "장림동"):
        """
        Args:
            service_key : 공공데이터포털 인증키
            station_name: 측정소 이름 (예: 장림동, 사하구 근처)
        """
        self.service_key = service_key
        self.station_name = station_name

        # 기본값
        self.pm10 = 0
        self.pm25 = 0
        self.khai = 0

    def fetch_air_quality(self):
        """
        실시간 미세먼지 데이터 조회

        Returns:
            tuple: (pm10, pm25, khai)
        """
        try:
            url = (
                "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/"
                "getMsrstnAcctoRltmMesureDnsty"
            )

            params = {
                "serviceKey": self.service_key,
                "returnType": "json",
                "numOfRows": "1",
                "pageNo": "1",
                "stationName": self.station_name,
                "dataTerm": "DAILY",
                "ver": "1.0"
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            items = data["response"]["body"]["items"]

            if not items:
                print("🌫 [Air] 데이터 없음")
                return self.pm10, self.pm25, self.khai

            item = items[0]

            # 값 파싱 (문자 → 숫자 변환)
            self.pm10 = int(item.get("pm10Value", 0))
            self.pm25 = int(item.get("pm25Value", 0))
            self.khai = int(item.get("khaiValue", 0))

        except requests.exceptions.HTTPError as e:
            print(f"🌫 [Air] HTTP 오류: {e}")
        except requests.exceptions.Timeout:
            print("🌫 [Air] 요청 시간 초과")
        except Exception as e:
            print(f"🌫 [Air] 예기치 않은 오류: {e}")

        return self.pm10, self.pm25, self.khai
