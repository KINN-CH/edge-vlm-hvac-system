import cv2
import numpy as np
from collections import deque
from typing import Optional


class MotionDetector:
    """
    [실시간 모션 감지기]
    OpenCV 프레임 차분 + Gaussian blur + 롤링 평균으로
    실제 움직임 강도를 측정하여 PMV 대사율(MET)을 보정합니다.

    ── 알고리즘 ──────────────────────────────────────────────────────────────
    1. 연속 두 프레임의 그레이스케일 차분 (absdiff)
    2. Gaussian blur로 조명 깜빡임·카메라 노이즈(고주파) 제거
    3. 픽셀 평균 밝기 = motion_score (움직임 강도)
    4. 최근 N프레임 롤링 평균 → 순간 통행자에 의한 오탐 방지

    ── MET 변환 기준 ──────────────────────────────────────────────────────
    score ≥ MOTION_HIGH (15.0) : 3.0 met  (운동, exercising)
    score ≥ MOTION_MED  ( 5.0) : 1.5 met  (보행, walking)
    score ≥ MOTION_LOW  ( 1.5) : 1.2 met  (기립/서성임, standing)
    score <  MOTION_LOW        : None      (VLM 정적 판단 신뢰)

    ── VLM override 기준 ──────────────────────────────────────────────────
    score ≥ MOTION_MED (5.0) 이면 motion_met 우선 사용.
    그 이하에서는 VLM의 activity 기반 MET를 신뢰.
    (VLM의 clo·count·bags·heat_source는 motion과 무관하게 항상 VLM 값 사용)
    """

    MOTION_HIGH = 15.0   # MET 3.0 (운동) 임계값
    MOTION_MED  =  5.0   # MET 1.5 (보행) 임계값 / VLM override 기준
    MOTION_LOW  =  1.5   # MET 1.2 (기립) 임계값

    def __init__(self, history_len: int = 10, blur_ksize: int = 21):
        """
        Args:
            history_len : 롤링 평균 윈도우 크기 (프레임 수, 기본값: 10)
            blur_ksize  : Gaussian blur 커널 크기 (홀수, 기본값: 21)
        """
        self._prev_gray     = None
        self._score_history = deque(maxlen=history_len)
        self._current_score = 0.0
        self._blur_ksize    = (blur_ksize, blur_ksize)

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def update(self, frame) -> float:
        """
        새 프레임을 받아 motion_score를 갱신하고 반환합니다.
        메인 루프 매 프레임마다 호출합니다.

        Returns:
            float: 현재 롤링 평균 motion_score (0 이상)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            self._prev_gray = gray
            return 0.0

        diff      = cv2.absdiff(self._prev_gray, gray)
        blurred   = cv2.GaussianBlur(diff, self._blur_ksize, 0)
        raw_score = float(np.mean(blurred))

        self._score_history.append(raw_score)
        self._current_score = float(np.mean(self._score_history))
        self._prev_gray     = gray

        return self._current_score

    def get_motion_met(self) -> Optional[float]:
        """
        현재 motion_score를 ISO 7730 MET 값으로 변환합니다.

        Returns:
            float : motion 기반 MET 값 (score ≥ MOTION_LOW 일 때)
            None  : score < MOTION_LOW — VLM 정적 판단을 신뢰하라는 신호
        """
        s = self._current_score
        if s >= self.MOTION_HIGH:
            return 3.0
        elif s >= self.MOTION_MED:
            return 1.5
        elif s >= self.MOTION_LOW:
            return 1.2
        return None

    def should_override_vlm(self) -> bool:
        """
        motion_score ≥ MOTION_MED 이면 VLM activity-MET를 override합니다.
        """
        return self._current_score >= self.MOTION_MED

    @property
    def current_score(self) -> float:
        return self._current_score
