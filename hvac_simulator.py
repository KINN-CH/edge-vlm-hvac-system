class HVACSimulator:
    """
    [내부 공조기 및 실내 환경 시뮬레이터]
    역할: 가상 에어컨 제어 및 실내 온습도 변화 물리 시뮬레이션

    물리 가정 (30fps 기준, 20m² 기준 size_factor=1.0):
    - 난방 속도: 0.002°C/step  × fan_speed × size_factor  ≈ 3.6°C/min (Fan3, 20m²)
    - 냉방 속도: 0.001°C/step  × fan_speed × size_factor  ≈ 1.8°C/min (Fan3, 20m²)
    - 외기 평형: 닫힘 0.0001/step, 열림 0.005/step
      (닫힘 시 시상수 ≈ 10,000 step = 5.5분 → 단열 건물 근사치)
    - 체열: 0.0001°C/step × 인원 × size_factor            ≈ 0.18°C/min (1인, 20m²)
      (1인 100W 발열 기준 20m²×3m 공간 → 약 0.08~0.15°C/min 이 물리적으로 타당)

    평형 온도 계산 (닫힘, size_factor=1.0, 5인 기준 체열 포함):
    - 냉방 Fan2: T_ss = outdoor - (0.002 - body)/equil ≈ 35 - 9.3 = 25.7°C  (여름 ✓)
    - 난방 Fan2: T_ss = outdoor + (0.004 + body)/equil ≈ -3  + 30  = 27°C   (겨울 ✓)
      (실질 상·하한은 target_temp 도달 or PMV_OFF 히스테리시스가 먼저 차단)
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
                self.indoor_temp  += 0.002 * self.fan_speed * size_factor
                self.indoor_humid  = max(25.0, self.indoor_humid - 0.001)
            elif self.mode == 'cool' and self.indoor_temp > self.target_temp:
                self.indoor_temp  -= 0.001 * self.fan_speed * size_factor
                self.indoor_humid -= 0.003

        # ── 외기와의 온도 평형 ─────────────────────────────────────────────────
        equil_rate = 0.005 if self.window_open else 0.0001
        self.indoor_temp += (outdoor_temp - self.indoor_temp) * equil_rate

        # ── 창문 열릴 때 외부 습도 영향 ───────────────────────────────────────
        if self.window_open:
            self.indoor_humid += (outdoor_humid - self.indoor_humid) * 0.01

        # ── 재실 인원 체열 ─────────────────────────────────────────────────────
        # 1인당 약 100W, 20m²×3m 공간 기준 ≈ 0.18°C/min
        self.indoor_temp += people_count * 0.0001 * size_factor

        # 범위 클램핑만 수행 (round는 표시 시점에 처리 — 내부에서 round하면
        # 매 프레임 미소 변화량 0.001~0.002°C가 0.00으로 잘려 온도가 고정됨)
        self.indoor_temp  = max(10.0, min(45.0, self.indoor_temp))
        self.indoor_humid = max(15.0, min(95.0, self.indoor_humid))

        return round(self.indoor_temp, 2), round(self.indoor_humid, 1)
