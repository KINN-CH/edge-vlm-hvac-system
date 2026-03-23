import requests

class WeatherService:
    """
    [외부 기상 데이터 서비스]
    역할: OpenWeatherMap API를 통해 실시간 실외 환경 정보 수집
    """
    def __init__(self, city="Busan", api_key=None):
        self.city = city
        self.api_key = api_key
        self.temp = 20.0  # 기본값
        self.humid = 50.0

    def fetch_current_weather(self):
        if not self.api_key:
            # print("🌐 [Weather Service] API 키가 없어 기본값을 사용합니다.")
            return self.temp, self.humid

        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={self.city}&appid={self.api_key}&units=metric"
            response = requests.get(url, timeout=5)
            response.raise_for_status() # HTTP 오류 발생 시 예외 발생
            data = response.json()

            # --- [수정] API 응답 구조 확인 ---
            if "main" in data and "humidity" in data["main"]:
                self.temp = data['main']['temp']
                self.humid = data['main']['humidity']
                # print(f"🌐 [Weather Service] 실시간 날씨 수신: {self.temp}°C, {self.humid}%")
            else:
                # API가 에러 메시지를 보냈을 경우
                error_msg = data.get("message", "알 수 없는 응답 형식")
                print(f"🌐 [Weather Service] API 응답 오류: {error_msg}")

        except requests.exceptions.HTTPError as http_err:
            print(f"🌐 [Weather Service] HTTP 오류: {http_err}")
        except Exception as e:
            print(f"🌐 [Weather Service] API 호출 중 예기치 않은 오류: {e}")
            
        return self.temp, self.humid