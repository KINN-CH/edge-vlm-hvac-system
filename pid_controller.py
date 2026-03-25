"""
[PID 제어기]
PMV(Predicted Mean Vote) 오차를 기반으로 공조기 제어 출력을 계산합니다.

목표 PMV = 0.0 (ISO 7730 중립 쾌적 기준)

출력 해석:
  output > 0  → 난방 필요 (PMV 음수, 추운 상태)
  output < 0  → 냉방 필요 (PMV 양수, 더운 상태)
  |output|    → 제어 강도 (→ 팬 속도 1~3으로 매핑)

기존 단순 if/else 대비 이점:
  - 오차 크기에 비례한 세밀한 팬 속도 조절 (P항)
  - 오랫동안 추웠던 방은 더 강하게 난방 (I항)
  - 온도가 급격히 변하면 선제 대응 (D항)
"""

import time


class PIDController:
    """
    PMV 기반 PID 열쾌적 제어기

    파라미터 가이드:
      kp = 0.8  : PMV 1.0 오차 → 출력 0.8 (팬 1단계)
      ki = 0.05 : 20초 지속 오차 → 추가 출력 1.0 (누적 보정)
      kd = 0.3  : 빠른 변화 시 오버슈트 억제
    """

    PMV_TARGET    = 0.0    # 목표 PMV
    INTEGRAL_MAX  = 10.0   # 적분 Anti-windup 클램프
    OUTPUT_MAX    = 3.0    # 최대 출력 (팬 3단계 매핑)
    DEADBAND      = 0.12   # 이 범위 안에선 제어 출력 0 (불필요한 on/off 방지)

    def __init__(self, kp: float = 0.8, ki: float = 0.05, kd: float = 0.3):
        self.kp = kp
        self.ki = ki
        self.kd = kd

        self._integral   = 0.0
        self._prev_error = 0.0
        self._last_time: float | None = None

    def compute(self, pmv_val: float) -> float:
        """
        PID 출력 계산

        Args:
            pmv_val : 현재 PMV 값

        Returns:
            float : 제어 출력 [-3.0, +3.0]
                    deadband 이내이면 0.0 반환
        """
        error = self.PMV_TARGET - pmv_val

        now = time.time()
        dt  = max(0.1, now - self._last_time) if self._last_time else 1.0
        self._last_time = now

        # 적분항 (Anti-windup)
        self._integral += error * dt
        self._integral  = max(-self.INTEGRAL_MAX, min(self.INTEGRAL_MAX, self._integral))

        # 미분항
        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        output = (self.kp * error
                  + self.ki * self._integral
                  + self.kd * derivative)
        output = max(-self.OUTPUT_MAX, min(self.OUTPUT_MAX, output))

        # Deadband: 미세한 오차는 무시 (불필요한 제어 방지)
        if abs(output) < self.DEADBAND:
            return 0.0

        return float(output)

    def reset(self):
        """상태 전이(EMPTY 진입 등) 시 PID 상태 초기화"""
        self._integral   = 0.0
        self._prev_error = 0.0
        self._last_time  = None

    @property
    def integral(self) -> float:
        """현재 적분값 (디버그/대시보드용)"""
        return round(self._integral, 3)

    @staticmethod
    def output_to_fan_speed(output: float) -> int:
        """PID 출력 강도 → 팬 속도(1~3) 변환"""
        return min(3, max(1, round(abs(output))))
