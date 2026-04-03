class HVACSimulator:
    """
    [내부 공조기 및 실내 환경 시뮬레이터]
    역할: 가상 에어컨 제어 및 실내 온습도 변화 물리 시뮬레이션

    물리 가정 (30fps 기준):
    - 난방 속도: 0.0008°C/step × fan_speed × size_factor  ≈ 1.4°C/min (Fan3)
    - 냉방 속도: 0.001°C/step  × fan_speed × size_factor  ≈ 1.8°C/min (Fan3)
    - 외기 평형: 닫힘 0.0003/step, 열림 0.005/step
    - 체열: 0.0003°C/step × 인원 × size_factor            ≈ 0.54°C/min (1인)
    """

    def __init__(self, room_size: float = 20.0):
        self.indoor_temp  = 22.0
        self.indoor_humid = 50.0

        self.room_size   = room_size
        self.window_open = False

        self.is_on       = False
        self.target_temp = 24.0
        self.fan_speed   = 1
        self.mode        = 'cool'

    def set_control(self, power: bool, target: float, fan: int, mode: str = None):
        self.is_on       = power
        self.target_temp = target
        self.fan_speed   = max(1, min(3, fan))
        if mode is not None:
            self.mode = mode

    def set_room(self, size_m2: float, window_open: bool):
        self.room_size   = size_m2
        self.window_open = window_open

    def simulate_step(self, outdoor_temp: float, outdoor_humid: float = 50.0,
                      people_count: int = 0):
        size_factor = 20.0 / max(self.room_size, 5.0)

        # ── 에어컨 냉난방 ──────────────────────────────────────────────────────
        if self.is_on:
            if self.mode == 'heat' and self.indoor_temp < self.target_temp:
                self.indoor_temp  += 0.0008 * self.fan_speed * size_factor
                self.indoor_humid  = max(25.0, self.indoor_humid - 0.001)
            elif self.mode == 'cool' and self.indoor_temp > self.target_temp:
                self.indoor_temp  -= 0.001 * self.fan_speed * size_factor
                self.indoor_humid -= 0.003

        # ── 외기와의 온도 평형 ─────────────────────────────────────────────────
        equil_rate = 0.005 if self.window_open else 0.0003
        self.indoor_temp += (outdoor_temp - self.indoor_temp) * equil_rate

        # ── 창문 열릴 때 외부 습도 영향 ───────────────────────────────────────
        if self.window_open:
            self.indoor_humid += (outdoor_humid - self.indoor_humid) * 0.01

        # ── 재실 인원 체열 ─────────────────────────────────────────────────────
        # 1인당 약 100W, 20m² 기준 ≈ 0.54°C/min
        self.indoor_temp += people_count * 0.0003 * size_factor

        self.indoor_temp  = round(max(10.0, min(45.0, self.indoor_temp)),  2)
        self.indoor_humid = round(max(15.0, min(95.0, self.indoor_humid)), 2)

        return self.indoor_temp, self.indoor_humid
