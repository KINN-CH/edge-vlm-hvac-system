import time
import datetime
from enum import Enum


class SystemState(Enum):
    EMPTY         = "EMPTY"          # 빈 공간 (인원 없음)
    ARRIVAL       = "ARRIVAL"        # 도착 직후 (적극적 냉·난방)
    STEADY        = "STEADY"         # 안정 운전 (PMV 기반 제어)
    PRE_DEPARTURE = "PRE_DEPARTURE"  # 퇴근 준비 감지 (선제 절전)


class StateManager:
    """
    [시스템 상태 관리자]
    실내 상황 맥락을 시계열로 추적하여 공조 제어 모드를 결정합니다.

    ── 상태 전이 규칙 ────────────────────────────────────────────────────────
    EMPTY         → ARRIVAL       : 인원 최초 감지
    ARRIVAL       → STEADY        : 도착 후 ARRIVAL_DURATION_SEC 경과
    STEADY        → PRE_DEPARTURE : 퇴근 맥락 점수 ≥ DEPARTURE_SCORE_ON
    PRE_DEPARTURE → EMPTY         : 인원 = 0
    PRE_DEPARTURE → STEADY        : 맥락 점수 < DEPARTURE_SCORE_OFF (오탐 복귀)
    ANY           → EMPTY         : 인원 0 상태 EMPTY_CONFIRM_SEC 지속

    ── 퇴근 맥락 점수 (0~75) ────────────────────────────────────────────────
    인원 감소    : +30  (이전 분석 대비 count 감소)
    아우터 착용  : +25  (VLM outerwear = 'yes')
    기립 자세    : +10  (VLM activity = 'standing')
    퇴근 시간대  : +10  (설정 퇴근 시각 ±1시간)
    최대 점수    : 75점
    """

    ARRIVAL_DURATION_SEC = 60    # 도착 후 강제 제어 지속 시간 (1분, 개발환경)
    EMPTY_CONFIRM_SEC    = 30    # 인원 0 확인 후 EMPTY 전환까지 대기 (30초)
    DEPARTURE_SCORE_ON   = 55    # PRE_DEPARTURE 진입 임계값
    DEPARTURE_SCORE_OFF  = 30    # STEADY 복귀 임계값 (히스테리시스)

    def __init__(self, work_start_hour: int = 9, work_end_hour: int = 18):
        self.state             = SystemState.EMPTY
        self.work_start_hour   = work_start_hour
        self.work_end_hour     = work_end_hour

        self._arrival_time      = None   # ARRIVAL 진입 시각 (time.time())
        self._empty_since       = None   # 인원 0 감지 시작 시각
        self._prev_people_count = 0
        self._departure_score   = 0

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def update(self, people_count: int, outerwear: str = 'no',
               activity: str = 'sitting') -> SystemState:
        """
        VLM 분석 결과를 받아 상태를 갱신하고 현재 상태를 반환합니다.

        Args:
            people_count : VLM 감지 인원 수
            outerwear    : 아우터 착용 여부 ('yes'|'no')
            activity     : 활동 분류 ('sitting'|'standing'|'walking'|...)

        Returns:
            SystemState: 갱신된 현재 상태
        """
        now = time.time()

        # ── 인원 0 지속 → EMPTY 전환 ─────────────────────────────────────────
        if people_count == 0:
            if self._empty_since is None:
                self._empty_since = now
            elif now - self._empty_since >= self.EMPTY_CONFIRM_SEC:
                self._transition(SystemState.EMPTY)
        else:
            self._empty_since = None

        # ── 상태별 전이 ───────────────────────────────────────────────────────
        if self.state == SystemState.EMPTY:
            if people_count > 0:
                self._transition(SystemState.ARRIVAL)

        elif self.state == SystemState.ARRIVAL:
            if (self._arrival_time is not None and
                    now - self._arrival_time >= self.ARRIVAL_DURATION_SEC):
                self._transition(SystemState.STEADY)

        elif self.state == SystemState.STEADY:
            self._departure_score = self._compute_departure_score(
                people_count, outerwear, activity, now
            )
            if self._departure_score >= self.DEPARTURE_SCORE_ON:
                self._transition(SystemState.PRE_DEPARTURE)

        elif self.state == SystemState.PRE_DEPARTURE:
            if people_count == 0:
                self._transition(SystemState.EMPTY)
            else:
                self._departure_score = self._compute_departure_score(
                    people_count, outerwear, activity, now
                )
                if self._departure_score < self.DEPARTURE_SCORE_OFF:
                    self._transition(SystemState.STEADY)  # 오탐 복귀

        self._prev_people_count = people_count
        return self.state

    @property
    def departure_score(self) -> int:
        return self._departure_score

    def arrival_elapsed_sec(self) -> float:
        """ARRIVAL 상태 진입 후 경과 시간 (초)"""
        if self._arrival_time is None:
            return 0.0
        return time.time() - self._arrival_time

    # ── 내부 메서드 ───────────────────────────────────────────────────────────

    def _transition(self, new_state: SystemState):
        if new_state == self.state:
            return
        print(f"[State] {self.state.value} -> {new_state.value}")
        self.state = new_state
        if new_state == SystemState.ARRIVAL:
            self._arrival_time    = time.time()
            self._departure_score = 0
        elif new_state == SystemState.EMPTY:
            self._arrival_time    = None
            self._departure_score = 0

    def _compute_departure_score(self, people_count: int, outerwear: str,
                                  activity: str, now: float) -> int:
        score = 0
        if people_count < self._prev_people_count:
            score += 30   # 인원 감소 추세
        if outerwear == 'yes':
            score += 25   # 외투 착용
        if activity == 'standing':
            score += 10   # 기립 자세
        hour = datetime.datetime.fromtimestamp(now).hour
        if self.work_end_hour - 1 <= hour <= self.work_end_hour + 1:
            score += 10   # 퇴근 시간대
        return min(score, 75)
