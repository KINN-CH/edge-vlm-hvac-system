import requests
import math
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class WeatherService:
    """
    [기상청 초단기실황 기반 날씨 서비스]

    수신 항목:
        - temp        : 기온 (°C) → T1H
        - humid       : 습도 (%) → REH
        - weather     : 강수 형태 → PTY
        - wind_speed  : 풍속 (m/s) → WSD
    """

    def __init__(self, lat=35.1044, lon=128.9750):
        self.lat = lat
        self.lon = lon
        self.service_key = os.getenv("WEATHER_API_KEY")

        # 기본값
        self.temp = 20.0
        self.humid = 50.0
        self.weather = "unknown"
        self.wind_speed = 0.0

    # ✅ 위경도 → 기상청 격자 변환
    def _latlon_to_grid(self, lat, lon):
        RE = 6371.00877
        GRID = 5.0
        SLAT1 = 30.0
        SLAT2 = 60.0
        OLON = 126.0
        OLAT = 38.0
        XO = 43
        YO = 136

        DEGRAD = math.pi / 180.0

        re = RE / GRID
        slat1 = SLAT1 * DEGRAD
        slat2 = SLAT2 * DEGRAD
        olon = OLON * DEGRAD
        olat = OLAT * DEGRAD

        sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
        sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)

        sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
        sf = math.pow(sf, sn) * math.cos(slat1) / sn

        ro = math.tan(math.pi * 0.25 + olat * 0.5)
        ro = re * sf / math.pow(ro, sn)

        ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
        ra = re * sf / math.pow(ra, sn)

        theta = lon * DEGRAD - olon
        if theta > math.pi:
            theta -= 2.0 * math.pi
        if theta < -math.pi:
            theta += 2.0 * math.pi

        theta *= sn

        nx = int(ra * math.sin(theta) + XO + 0.5)
        ny = int(ro - ra * math.cos(theta) + YO + 0.5)

        return nx, ny

    # ✅ base_date, base_time 생성
    def _get_base_datetime(self):
        from datetime import timedelta
        now = datetime.now()
        
        # 초단기실황은 시간 차이가 있을 수 있으므로 30분 전 데이터 요청
        past_time = now - timedelta(minutes=30)
        
        base_date = past_time.strftime("%Y%m%d")
        base_time = past_time.strftime("%H00")

        return base_date, base_time

    # ✅ 날씨 조회
    def fetch_current_weather(self):
        if not self.service_key:
            return self.temp, self.humid, self.weather, self.wind_speed

        try:
            nx, ny = self._latlon_to_grid(self.lat, self.lon)
            base_date, base_time = self._get_base_datetime()

            url = (
                "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/"
                "getUltraSrtNcst"
            )

            params = {
                "serviceKey": self.service_key,
                "pageNo": "1",
                "numOfRows": "10",
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": nx,
                "ny": ny
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            items = data["response"]["body"]["items"]["item"]

            # 카테고리별 파싱
            for item in items:
                category = item["category"]
                value = item["obsrValue"]

                if category == "T1H":
                    self.temp = float(value)
                elif category == "REH":
                    self.humid = float(value)
                elif category == "WSD":
                    self.wind_speed = float(value)
                elif category == "PTY":
                    self.weather = self._parse_weather(int(value))

        except Exception as e:
            print(f"🌤 [Weather] 오류: {e}")

        return self.temp, self.humid, self.weather, self.wind_speed

    # ✅ 강수 형태 변환
    def _parse_weather(self, pty):
        mapping = {
            0: "맑음",
            1: "비",
            2: "비/눈",
            3: "눈",
            4: "소나기"
        }
        return mapping.get(pty, "unknown")