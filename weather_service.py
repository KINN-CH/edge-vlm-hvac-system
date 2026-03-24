import requests


class WeatherService:
    """
    [외부 기상 데이터 서비스]
    역할: OpenWeatherMap API를 통해 실시간 실외 환경 정보 수집

    위도/경도 기반 쿼리 사용 → 구(district) 단위 지역도 정확하게 조회 가능
    (city 이름 방식은 행정구 단위에서 404 오류 발생)

    수신 항목:
        - temp        : 외부 기온 (°C)
        - humid       : 외부 습도 (%)
        - weather     : 날씨 상태 설명 (예: "clear sky", "light rain")
        - wind_speed  : 풍속 (m/s)  – 향후 외풍 계산 등에 활용 가능
    """

    def __init__(self, lat: float = 35.1044, lon: float = 128.9750, api_key: str = None):
        """
        Args:
            lat     : 위도  (기본값: 사하구, 부산)
            lon     : 경도  (기본값: 사하구, 부산)
            api_key : OpenWeatherMap API 키
        """
        self.lat     = lat
        self.lon     = lon
        self.api_key = api_key

        # 기본값 (API 장애 또는 키 없을 때 폴백)
        self.temp       = 20.0
        self.humid      = 50.0
        self.weather    = "unknown"
        self.wind_speed = 0.0

    def fetch_current_weather(self):
        """
        현재 날씨 데이터를 API에서 수신

        Returns:
            tuple: (temp: float, humid: float, weather: str, wind_speed: float)
                   API 실패 시 마지막 성공값(또는 기본값) 반환
        """
        if not self.api_key:
            return self.temp, self.humid, self.weather, self.wind_speed

        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?lat={self.lat}&lon={self.lon}"
                f"&appid={self.api_key}&units=metric"
            )
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if "main" not in data:
                print(f"🌐 [Weather] 예상치 못한 응답 형식: {data.get('message', data)}")
                return self.temp, self.humid, self.weather, self.wind_speed

            self.temp       = data['main']['temp']
            self.humid      = data['main']['humidity']
            self.weather    = data['weather'][0]['description'] if data.get('weather') else "unknown"
            self.wind_speed = data.get('wind', {}).get('speed', 0.0)

        except requests.exceptions.HTTPError as e:
            print(f"🌐 [Weather] HTTP 오류: {e}")
        except requests.exceptions.Timeout:
            print("🌐 [Weather] 요청 시간 초과 – 이전 값 유지")
        except Exception as e:
            print(f"🌐 [Weather] 예기치 않은 오류: {e}")

        return self.temp, self.humid, self.weather, self.wind_speed
