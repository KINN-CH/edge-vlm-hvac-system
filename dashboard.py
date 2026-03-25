"""
[대시보드 UI 모듈]
카메라 화면 옆에 표시될 정보 패널을 PIL로 렌더링합니다.
한글/영문 혼용 폰트 자동 감지 (Windows: 맑은고딕, macOS: AppleSDGothicNeo, Linux: NanumGothic)
"""

import os
import platform
import cv2
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from state_machine import SystemState

# ── 패널 크기 ─────────────────────────────────────────────────────────────────
PANEL_W = 390

# ── 색상 팔레트 (RGB) ─────────────────────────────────────────────────────────
BG        = ( 22,  22,  32)   # 전체 배경
BG_SECT   = ( 32,  32,  46)   # 섹션 배경
BG_HDR    = ( 52,  48,  75)   # 섹션 헤더 배경
C_TITLE   = (185, 165, 255)   # 섹션 타이틀
C_LABEL   = (125, 125, 150)   # 라벨 (좌측)
C_VAL     = (215, 215, 228)   # 일반 값
C_GREEN   = ( 90, 210,  90)   # 쾌적/정상
C_ORANGE  = (255, 172,  55)   # 경고
C_RED     = (215,  72,  72)   # 위험
C_HEAT    = (255, 148,  55)   # 난방 모드
C_COOL    = ( 72, 165, 255)   # 냉방 모드
C_GOLD    = (255, 222,  88)   # 솔루션 텍스트
C_CYAN    = ( 95, 215, 208)   # 날씨 정보
C_ENERGY  = (150, 215, 255)   # 에너지 정보
C_TIME    = (140, 138, 170)   # 타임스탬프

# ── 폰트 캐시 ─────────────────────────────────────────────────────────────────
_font_cache: dict = {}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """OS별 한글 지원 폰트 자동 로드 (캐싱)"""
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]

    sys_name = platform.system()
    if sys_name == 'Windows':
        root = os.environ.get('SystemRoot', r'C:\Windows')
        cands = [
            os.path.join(root, 'Fonts', 'malgunbd.ttf' if bold else 'malgun.ttf'),
            os.path.join(root, 'Fonts', 'malgun.ttf'),
            os.path.join(root, 'Fonts', 'gulim.ttc'),
        ]
    elif sys_name == 'Darwin':
        cands = [
            '/System/Library/Fonts/AppleSDGothicNeo.ttc',
            '/System/Library/Fonts/Supplemental/AppleGothic.ttf',
            '/Library/Fonts/NanumGothic.ttf',
        ]
    else:  # Linux / Jetson
        cands = [
            '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf' if bold
            else '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ]

    for path in cands:
        try:
            f = ImageFont.truetype(path, size)
            _font_cache[key] = f
            return f
        except Exception:
            pass

    f = ImageFont.load_default()
    _font_cache[key] = f
    return f


# ── 색상 헬퍼 ─────────────────────────────────────────────────────────────────

def _pmv_color(pmv: float) -> tuple:
    if -0.5 <= pmv <= 0.5:
        return C_GREEN
    if -1.5 <= pmv <= 1.5:
        return C_ORANGE
    return C_RED


def _temp_color(temp: float, is_outdoor: bool = True) -> tuple:
    if is_outdoor:
        if temp < 5:   return C_COOL
        if temp < 15:  return C_VAL
        if temp < 28:  return C_GREEN
        return C_RED
    else:
        if temp < 18:  return C_COOL
        if temp < 27:  return C_GREEN
        return C_RED


# ── 섹션 드로잉 헬퍼 ──────────────────────────────────────────────────────────

def _sect_header(draw: ImageDraw.Draw, y: int, title: str) -> int:
    """섹션 헤더 바 그리기. 다음 y 반환."""
    draw.rectangle([(0, y), (PANEL_W, y + 26)], fill=BG_HDR)
    draw.text((10, y + 5), title, font=_font(13, bold=True), fill=C_TITLE)
    return y + 26


def _row2(draw: ImageDraw.Draw, y: int,
          lbl1: str, val1: str, col1: tuple,
          lbl2: str, val2: str, col2: tuple) -> int:
    """한 줄에 라벨+값 2쌍 그리기"""
    draw.text(( 10, y + 2), lbl1, font=_font(12), fill=C_LABEL)
    draw.text(( 65, y + 2), val1, font=_font(13, bold=True), fill=col1)
    draw.text((200, y + 2), lbl2, font=_font(12), fill=C_LABEL)
    draw.text((255, y + 2), val2, font=_font(13, bold=True), fill=col2)
    return y + 22


def _row1(draw: ImageDraw.Draw, y: int,
          lbl: str, val: str, col: tuple = None) -> int:
    """한 줄에 라벨+값 1쌍 그리기"""
    draw.text((10, y + 2), lbl, font=_font(12), fill=C_LABEL)
    draw.text((65, y + 2), val, font=_font(13), fill=col or C_VAL)
    return y + 22


# ── 솔루션 텍스트 생성 ────────────────────────────────────────────────────────

def _get_solution(state: SystemState, pmv: float, hvac,
                  out_temp: float, people: int) -> list:
    """현재 상황에 맞는 솔루션 2줄 반환"""
    if state == SystemState.EMPTY:
        return ["공실 감지 — 에어컨 OFF", "에너지 절약 대기 모드"]

    if state == SystemState.ARRIVAL:
        mode_str = "난방" if hvac.mode == 'heat' else "냉방"
        return [
            f"도착 감지 — {mode_str} 강화 (Fan {hvac.fan_speed})",
            f"실내 {hvac.indoor_temp:.1f}°C → 목표 {hvac.target_temp:.0f}°C",
        ]

    if state == SystemState.PRE_DEPARTURE:
        return ["퇴근 준비 맥락 감지!", "절전 모드 전환 — Fan 1 유지"]

    # STEADY
    if pmv > 1.5:
        return [f"PMV {pmv:.2f} — 매우 더움!", "냉방 최대 출력 가동 중"]
    if pmv > 0.5:
        return [f"PMV {pmv:.2f} — 조금 더움", f"냉방 가동 → 목표 {hvac.target_temp:.0f}°C"]
    if pmv < -1.5:
        return [f"PMV {pmv:.2f} — 매우 추움!", "난방 최대 출력 가동 중"]
    if pmv < -0.5:
        return [f"PMV {pmv:.2f} — 조금 추움", f"난방 가동 → 목표 {hvac.target_temp:.0f}°C"]
    return [f"PMV {pmv:.2f} — 쾌적 상태 유지 중", "최적 열환경 달성 완료"]


# ── 섹션별 드로잉 함수 ────────────────────────────────────────────────────────

def _draw_header(draw: ImageDraw.Draw, y: int) -> int:
    draw.rectangle([(0, y), (PANEL_W, y + 40)], fill=(40, 38, 62))
    draw.text((10,  y + 4),  'VLM HVAC SYSTEM',
              font=_font(15, bold=True), fill=C_TITLE)
    draw.text((10, y + 24), datetime.now().strftime('%Y-%m-%d  %H:%M:%S'),
              font=_font(11), fill=C_TIME)
    return y + 40


def _draw_outdoor(draw: ImageDraw.Draw, y: int,
                  temp: float, humid: float,
                  weather: str, wind: float) -> int:
    draw.rectangle([(0, y), (PANEL_W, y + 88)], fill=BG_SECT)
    y = _sect_header(draw, y, '  실외 환경')
    y = _row2(draw, y,
              '기온',  f'{temp:.1f}°C',  _temp_color(temp, True),
              '습도',  f'{humid:.0f}%',  C_VAL)
    y = _row1(draw, y, '날씨', weather[:24], C_CYAN)
    y = _row1(draw, y, '풍속', f'{wind:.1f} m/s')
    return y


def _draw_indoor(draw: ImageDraw.Draw, y: int, hvac, ds: dict) -> int:
    draw.rectangle([(0, y), (PANEL_W, y + 88)], fill=BG_SECT)
    y = _sect_header(draw, y, '  실내 환경')
    y = _row2(draw, y,
              '온도',  f'{hvac.indoor_temp:.1f}°C', _temp_color(hvac.indoor_temp, False),
              '습도',  f'{hvac.indoor_humid:.0f}%', C_VAL)
    pmv = ds.get('pmv_val', 0.0)
    y = _row2(draw, y,
              'PMV',   f'{pmv:+.2f}',           _pmv_color(pmv),
              '상태',  ds.get('comfort_msg', '-')[:14], _pmv_color(pmv))
    y = _row1(draw, y, '분석', ds.get('last_analysis', '--:--:--'), C_TIME)
    return y


def _draw_hvac(draw: ImageDraw.Draw, y: int, hvac, sm) -> int:
    draw.rectangle([(0, y), (PANEL_W, y + 90)], fill=BG_SECT)
    y = _sect_header(draw, y, '  에어컨 상태')

    # 모드 색상 및 텍스트
    mode_col  = C_HEAT if hvac.mode == 'heat' else C_COOL
    mode_str  = f"{'난방' if hvac.mode == 'heat' else '냉방'}  {'ON' if hvac.is_on else 'OFF'}"
    y = _row2(draw, y,
              '모드',    mode_str,                   mode_col,
              '설정온도', f'{hvac.target_temp:.0f}°C', C_VAL)
    y = _row2(draw, y,
              '풍량',    f'Fan {hvac.fan_speed}',    C_VAL,
              '창문',    '열림' if hvac.window_open else '닫힘', C_CYAN)
    state_str = sm.state.value
    score_str = f'(퇴근점수 {sm.departure_score})'
    y = _row1(draw, y, '상태', f'{state_str}  {score_str}',
              C_ORANGE if sm.state.value == 'PRE_DEPARTURE' else C_GREEN)
    return y


def _draw_occupancy(draw: ImageDraw.Draw, y: int, ds: dict) -> int:
    draw.rectangle([(0, y), (PANEL_W, y + 78)], fill=BG_SECT)
    y = _sect_header(draw, y, '  재실 상황')

    people = ds.get('people_count', 0)
    p_col  = C_GREEN if people > 0 else C_LABEL
    y = _row2(draw, y,
              '인원',    f'{people}명',                  p_col,
              '모션',   f"{ds.get('motion_score', 0.0):.1f}", C_VAL)
    act = ds.get('activity', '-')
    src = ds.get('met_source', 'vlm').upper()
    y = _row2(draw, y,
              '활동',    f"{act}",                        C_VAL,
              'MET',    f"{ds.get('met', 1.0):.1f} ({src})", C_VAL)
    return y


def _draw_solution(draw: ImageDraw.Draw, y: int, end_y: int,
                   state: SystemState, pmv: float, hvac, out_temp: float,
                   people: int) -> int:
    h = end_y - y
    draw.rectangle([(0, y), (PANEL_W, end_y)], fill=(28, 28, 42))
    y = _sect_header(draw, y, '  솔루션')

    lines = _get_solution(state, pmv, hvac, out_temp, people)
    for line in lines:
        draw.text((12, y + 3), f'▶  {line}', font=_font(12), fill=C_GOLD)
        y += 22
    return end_y


def _draw_energy(draw: ImageDraw.Draw, y: int, end_y: int, hvac, em) -> None:
    draw.rectangle([(0, y), (PANEL_W, end_y)], fill=(28, 32, 45))
    power_w  = em.get_current_power_w(hvac.is_on, hvac.fan_speed)
    save_pct = em.get_savings_pct()
    kwh      = em.get_energy_kwh()
    comfort  = em.get_comfort_rate()

    txt = (f'전력 {power_w}W   절약 {save_pct:.1f}%   '
           f'{kwh:.3f}kWh   쾌적율 {comfort:.1f}%')
    draw.text((8, y + 7), txt, font=_font(11), fill=C_ENERGY)


# ── 공개 API ──────────────────────────────────────────────────────────────────

def build(cam_h: int, hvac, sm, em,
          out_temp: float, out_humid: float,
          out_weather: str, out_wind: float,
          ds: dict) -> np.ndarray:
    """
    대시보드 패널 생성

    Args:
        cam_h       : 카메라 프레임 높이 (패널 높이에 맞춤)
        hvac        : HVACSimulator 인스턴스
        sm          : StateManager 인스턴스
        em          : EnergyMonitor 인스턴스
        out_temp    : 외부 기온 (°C)
        out_humid   : 외부 습도 (%)
        out_weather : 날씨 설명
        out_wind    : 풍속 (m/s)
        ds          : display_state dict (pmv_val, comfort_msg, people_count, ...)

    Returns:
        np.ndarray: BGR 이미지 (cam_h, PANEL_W, 3)
    """
    img  = Image.new('RGB', (PANEL_W, cam_h), BG)
    draw = ImageDraw.Draw(img)

    # ── 구분선 (세로) ─────────────────────────────────────────────────────────
    draw.line([(0, 0), (0, cam_h)], fill=(70, 60, 100), width=2)

    y  = 0
    y  = _draw_header(draw, y)                          # 40 px
    y  = _draw_outdoor(draw, y,                         # 88 px
                       out_temp, out_humid, out_weather, out_wind)
    y  = _draw_indoor(draw, y, hvac, ds)                # 88 px
    y  = _draw_hvac(draw, y, hvac, sm)                  # 90 px
    y  = _draw_occupancy(draw, y, ds)                   # 78 px

    energy_h   = 30
    solution_y = y
    solution_e = cam_h - energy_h
    _draw_solution(draw, solution_y, solution_e,
                   sm.state, ds.get('pmv_val', 0.0),
                   hvac, out_temp, ds.get('people_count', 0))
    _draw_energy(draw, cam_h - energy_h, cam_h, hvac, em)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
