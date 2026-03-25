class HVACSimulator:
    """
    [내부 공조기 및 실내 환경 시뮬레이터]
    역할: 가상 에어컨 제어 및 실내 온습도 변화 물리 시뮬레이션

    물리 가정:
    - 1 스텝 ≈ 실시간 루프 1프레임 (약 33ms, 데모용 타임스케일)
    - 기준 방 크기 20m²에서 냉·난방 속도 보정계수 = 1.0
    - 창문 열릴 때 외기 평형 속도 = 닫힌 상태의 10배
    - 재실 인원 1인당 체열 0.03°C/step 기여
    - 난방 속도: 0.015°C/step × fan_speed × size_factor
    - 냉방 속도: 0.020°C/step × fan_speed × size_factor
    """

    def __init__(self, room_size: float = 20.0):
        # --- 실내 환경 (학교 겨울철 초기값) ---
        self.indoor_temp  = 20.0   # °C — 난방 전 강의실 초기 온도
        self.indoor_humid = 45.0   # %  — 겨울철 건조 환경

        # --- 공간 특성 ---
        self.room_size   = room_size
        self.window_open = False

        # --- 에어컨 설정값 ---
        self.is_on       = False
        self.target_temp = 25.0    # °C — 학교 환경 기준 설정온도
        self.fan_speed   = 1       # 1: 약, 2: 중, 3: 강
        self.mode        = 'heat'  # 'heat' | 'cool'

    def set_control(self, power: bool, target: float, fan: int, mode: str = None):
        """공조기 제어 명령 설정"""
        self.is_on       = power
        self.target_temp = target
        self.fan_speed   = fan
        if mode is not None:
            self.mode = mode

    def set_room(self, size_m2: float, window_open: bool):
        """공간 특성 일괄 업데이트"""
        self.room_size   = size_m2
        self.window_open = window_open

    def simulate_step(self, outdoor_temp: float, outdoor_humid: float = 50.0,
                      people_count: int = 0):
        """
        1 스텝 동안의 실내 환경 변화 계산

        Args:
            outdoor_temp  : 현재 외부 기온 (°C)
            outdoor_humid : 현재 외부 습도 (%)
            people_count  : 현재 재실 인원 수
        """
        size_factor = 20.0 / max(self.room_size, 5.0)

        # 에어컨 난방 / 냉방
        if self.is_on:
            if self.mode == 'heat' and self.indoor_temp < self.target_temp:
                # 난방: 온도 상승 + 약간의 건조 효과
                self.indoor_temp  += 0.015 * self.fan_speed * size_factor
                self.indoor_humid  = max(20.0, self.indoor_humid - 0.01)
            elif self.mode == 'cool' and self.indoor_temp > self.target_temp:
                # 냉방: 온도 하강 + 제습
                self.indoor_temp  -= 0.020 * self.fan_speed * size_factor
                self.indoor_humid -= 0.05

        # 외기와의 온도 평형 (창문 개폐에 따라 속도 10배 차이)
        equil_rate = 0.05 if self.window_open else 0.005
        self.indoor_temp += (outdoor_temp - self.indoor_temp) * equil_rate

        # 창문 열릴 때 외부 습도 영향
        if self.window_open:
            self.indoor_humid += (outdoor_humid - self.indoor_humid) * 0.05

        # 재실 인원 체열 (1인당 약 70W → 0.03°C/step)
        self.indoor_temp += people_count * 0.03 * size_factor

        # 물리적 범위 클램핑
        self.indoor_temp  = round(max(10.0, min(45.0, self.indoor_temp)),  2)
        self.indoor_humid = round(max(15.0, min(95.0, self.indoor_humid)), 2)

        return self.indoor_temp, self.indoor_humid
