import time


class EnergyMonitor:
    """
    [전력 소비 모니터]
    공조기 운전 이력을 누적 기록하고, 전통 방식(베이스라인) 대비 에너지 절약량을 산출합니다.

    ── 공조기 소비전력 모델 (가정치, 추후 실측 보정 가능) ─────────────────
    OFF   :    0 W
    Fan 1 :  800 W  (냉·난방 약)
    Fan 2 : 1200 W  (냉·난방 중)
    Fan 3 : 1600 W  (냉·난방 강)

    ── 베이스라인 (전통 방식 가정) ───────────────────────────────────────────
    재실자가 있는 동안 풍량 2단계(1200 W)를 상시 가동하는 단순 온도 설정 방식.
    VLM 맥락 인지 없이 근무 시간 = 항상 운전.

    ── 논문 핵심 지표 ────────────────────────────────────────────────────────
    절약률(%) = (베이스라인 kWh - 실제 kWh) / 베이스라인 kWh × 100
    쾌적 유지율(%) = PMV ∈ (-0.5, 0.5) 인 분석 샘플 비율
    """

    POWER_W    = {0: 0, 1: 800, 2: 1200, 3: 1600}  # 팬 단계별 소비전력 (W)
    BASELINE_W = 1200                                # 전통 방식 기준 소비전력 (W)

    def __init__(self):
        self._energy_actual_wh   = 0.0   # 실제 누적 전력량 (Wh)
        self._energy_baseline_wh = 0.0   # 베이스라인 누적 전력량 (Wh)
        self._last_tick          = time.time()

        self._pmv_samples_total   = 0
        self._pmv_samples_comfort = 0    # PMV ∈ (-0.5, 0.5) 인 샘플 수

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def tick(self, is_on: bool, fan_speed: int,
             people_count: int, pmv_val: float = None):
        """
        1 스텝 경과 처리. 메인 루프 매 프레임마다 호출합니다.

        Args:
            is_on        : 공조기 가동 여부
            fan_speed    : 현재 풍량 단계 (1~3)
            people_count : 현재 재실 인원 수 (베이스라인 계산 기준)
            pmv_val      : 현재 PMV 값 (None 이면 쾌적도 통계 건너뜀)
        """
        now     = time.time()
        hours   = (now - self._last_tick) / 3600.0
        self._last_tick = now

        # 실제 소비
        actual_w = self.POWER_W.get(fan_speed, 0) if is_on else 0
        self._energy_actual_wh += actual_w * hours

        # 베이스라인: 재실자 있을 때만 가동
        if people_count > 0:
            self._energy_baseline_wh += self.BASELINE_W * hours

        # PMV 쾌적도 통계
        if pmv_val is not None:
            self._pmv_samples_total += 1
            if -0.5 <= pmv_val <= 0.5:
                self._pmv_samples_comfort += 1

    def get_energy_kwh(self) -> float:
        """실제 누적 소비 전력량 (kWh)"""
        return round(self._energy_actual_wh / 1000, 4)

    def get_baseline_kwh(self) -> float:
        """베이스라인 누적 전력량 (kWh)"""
        return round(self._energy_baseline_wh / 1000, 4)

    def get_savings_pct(self) -> float:
        """에너지 절약률 (%)"""
        if self._energy_baseline_wh < 1e-6:
            return 0.0
        saved = self._energy_baseline_wh - self._energy_actual_wh
        return round(saved / self._energy_baseline_wh * 100, 1)

    def get_comfort_rate(self) -> float:
        """쾌적 유지율 — PMV ∈ (-0.5, 0.5) 인 비율 (%)"""
        if self._pmv_samples_total == 0:
            return 0.0
        return round(self._pmv_samples_comfort / self._pmv_samples_total * 100, 1)

    def get_current_power_w(self, is_on: bool, fan_speed: int) -> int:
        """현재 스텝 소비전력 (W)"""
        return self.POWER_W.get(fan_speed, 0) if is_on else 0

    def print_summary(self):
        """종료 시 에너지 리포트 출력"""
        baseline = self.get_baseline_kwh()
        actual   = self.get_energy_kwh()
        saved_wh = (self._energy_baseline_wh - self._energy_actual_wh)
        print(f"\n{'=' * 58}")
        print(f"  [에너지 리포트]")
        print(f"  실제 소비량    : {actual:.4f} kWh  ({actual * 1000:.1f} Wh)")
        print(f"  베이스라인     : {baseline:.4f} kWh  ({baseline * 1000:.1f} Wh)")
        print(f"  절약량         : {saved_wh / 1000:.4f} kWh  ({saved_wh:.1f} Wh)")
        print(f"  절약률         : {self.get_savings_pct():.1f} %")
        print(f"  쾌적 유지율    : {self.get_comfort_rate():.1f} %  (PMV ±0.5 기준)")
        print(f"  분석 샘플 수   : {self._pmv_samples_total} 회")
        print(f"{'=' * 58}\n")
