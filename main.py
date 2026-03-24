import cv2
import os
import pandas as pd
from datetime import datetime

from vlm_processor import VLMProcessor
from weather_service import WeatherService
from hvac_simulator import HVACSimulator
from thermal_engine import ThermalEngine
from state_machine import StateManager, SystemState
from energy_monitor import EnergyMonitor

# ─── 설정 상수 ───────────────────────────────────────────────────────────────
LOG_FILE      = "hvac_system_performance.csv"
SCENARIO_NAME = "Smart_Office_Initial_Test"

WEATHER_API_KEY = "97e9ad342e69a006e6c55886b18842c2"
WEATHER_LAT     = 35.1044   # 사하구, 부산 위도
WEATHER_LON     = 128.9750  # 사하구, 부산 경도

ROOM_SIZE_M2    = 20.0   # 방 면적 (m²)
WINDOW_OPEN     = False  # 창문 초기 상태

WORK_START_HOUR = 9      # 근무 시작 시각
WORK_END_HOUR   = 18     # 근무 종료 시각

# 풍량 단계 → 실내 기류 속도(m/s) 변환 (PMV vel 입력용)
FAN_VELOCITY = {1: 0.1, 2: 0.3, 3: 0.5}
# ─────────────────────────────────────────────────────────────────────────────


def initialize_csv():
    """CSV 로그 파일이 없으면 헤더 포함 신규 생성"""
    if not os.path.exists(LOG_FILE):
        columns = [
            'timestamp', 'scenario',
            'system_state', 'departure_score',
            'out_temp', 'out_humid', 'out_weather', 'out_wind',
            'in_temp', 'in_humid',
            'people_count', 'met', 'clo', 'activity',
            'bags', 'heat_source',
            'window_open', 'room_size', 'air_vel',
            'pmv_val', 'comfort_status',
            'target_temp', 'fan_speed',
            'power_w', 'energy_kwh', 'baseline_kwh', 'savings_pct', 'comfort_rate',
        ]
        pd.DataFrame(columns=columns).to_csv(LOG_FILE, index=False)
        print(f"📁 [System] 새 로그 파일 생성: {LOG_FILE}")


def save_log(data: dict):
    """딕셔너리 한 행을 CSV에 추가"""
    pd.DataFrame([data]).to_csv(LOG_FILE, mode='a', index=False, header=False)


def decide_control(state: SystemState, pmv_val: float,
                   people_count: int, outdoor_temp: float):
    """
    상태 머신 + PMV 기반 공조기 제어 명령 결정

    ── 상태별 동작 ──────────────────────────────────────────────────────────
    EMPTY         : 전원 OFF (빈 공간 절전)
    ARRIVAL       : 도착 직후 적극적 냉·난방 (외기 온도 기반)
    PRE_DEPARTURE : 목표온도 완화 + 풍량 최소 (점진적 절전)
    STEADY        : ISO 7730 PMV 기반 미세 제어

    Returns:
        (power: bool|None, target_temp: float|None, fan_speed: int|None)
        power=None  이면 현재 설정 유지
        power=False 이면 공조기 OFF
    """
    if state == SystemState.EMPTY:
        return False, None, None

    if state == SystemState.ARRIVAL:
        if outdoor_temp > 25.0:          # 여름: 빠른 냉방
            return True, 20.0, 3
        elif outdoor_temp < 10.0:        # 겨울: 빠른 난방
            return True, 26.0, 3
        else:                            # 봄/가을: 표준
            return True, 22.0, 2

    if state == SystemState.PRE_DEPARTURE:
        # 잔열·잔냉 활용, 풍량 최소 → 에너지 절약
        return True, 25.0, 1

    # STEADY: PMV 기반 제어
    if pmv_val > 0.5:
        occ_offset  = min(2.0, max(0, people_count - 1) * 0.5)
        target_temp = round(22.0 - occ_offset, 1)
        fan_speed   = min(3, 2 + (1 if people_count >= 3 else 0))
        return True, target_temp, fan_speed
    elif pmv_val < -0.5:
        return True, 26.0, 1
    else:
        return None, None, None  # 쾌적 상태: 현재 유지


def decide_window(state: SystemState, pmv_val: float,
                  outdoor_temp: float, indoor_temp: float,
                  heat_source: str) -> bool | None:
    """
    자동 창문 제어 결정

    ── 우선순위 ─────────────────────────────────────────────────────────────
    1. EMPTY       → 닫기 (보안)
    2. 열원 감지    → 열기 (환기 우선)
    3. PRE_DEPARTURE → 닫기 (퇴근 준비)
    4. STEADY + 더움 + 외기가 내부보다 시원 → 열기 (자연환기)

    Returns:
        True  : 창문 열기
        False : 창문 닫기
        None  : 현재 상태 유지 (수동 조작 유지)
    """
    if state == SystemState.EMPTY:
        return False
    if heat_source == 'yes':
        return True
    if state == SystemState.PRE_DEPARTURE:
        return False
    if state == SystemState.STEADY and pmv_val > 0.5 and outdoor_temp < indoor_temp - 2.0:
        return True
    return None


def build_hud(hvac: HVACSimulator, state: SystemState,
              energy: EnergyMonitor, departure_score: int) -> list[str]:
    """실시간 HUD 텍스트 2줄 생성"""
    win  = "O" if hvac.window_open else "C"
    mode = "ON" if hvac.is_on else "OFF"

    line1 = (f"Temp:{hvac.indoor_temp:.1f}C  Humid:{hvac.indoor_humid:.1f}%  "
             f"AC:{mode}({hvac.target_temp:.0f}C/Fan{hvac.fan_speed})  Win:{win}")

    line2 = (f"State:{state.value}  Score:{departure_score}  "
             f"Save:{energy.get_savings_pct():.1f}%  "
             f"Comfort:{energy.get_comfort_rate():.1f}%  "
             f"Power:{energy.get_current_power_w(hvac.is_on, hvac.fan_speed)}W")

    return [line1, line2]


def main():
    print("⚙️ [System] 지능형 공조 제어 시스템 초기화 중...")
    initialize_csv()

    vlm     = VLMProcessor()
    weather = WeatherService(lat=WEATHER_LAT, lon=WEATHER_LON, api_key=WEATHER_API_KEY)
    hvac    = HVACSimulator(room_size=ROOM_SIZE_M2)
    hvac.set_room(ROOM_SIZE_M2, WINDOW_OPEN)
    engine  = ThermalEngine()
    sm      = StateManager(work_start_hour=WORK_START_HOUR, work_end_hour=WORK_END_HOUR)
    em      = EnergyMonitor()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ [Error] 카메라를 열 수 없습니다.")
        return

    print("\n✅ 모든 모듈 준비 완료!")
    print(f"📍 날씨 조회: ({WEATHER_LAT}, {WEATHER_LON})  |  방 크기: {ROOM_SIZE_M2}m²")
    print(f"🕐 근무 시간: {WORK_START_HOUR}:00 ~ {WORK_END_HOUR}:00")
    print("⌨️  's': 분석 및 제어  |  'w': 창문 수동 개폐  |  'q': 종료\n")

    last_people_count = 0
    pmv_val           = 0.0
    out_temp          = 20.0
    out_humid         = 50.0
    out_weather       = "unknown"
    out_wind          = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # ── 매 프레임 처리 ────────────────────────────────────────────────────
        out_temp, out_humid, out_weather, out_wind = weather.fetch_current_weather()
        hvac.simulate_step(out_temp, out_humid, people_count=last_people_count)
        em.tick(hvac.is_on, hvac.fan_speed, last_people_count)

        # HUD 오버레이 (2줄)
        hud_lines = build_hud(hvac, sm.state, em, sm.departure_score)
        cv2.putText(frame, hud_lines[0], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        cv2.putText(frame, hud_lines[1], (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)
        cv2.imshow('VLM Intelligent HVAC System', frame)

        key = cv2.waitKey(1) & 0xFF

        # ── 창문 수동 개폐 토글 ('w') ─────────────────────────────────────────
        if key == ord('w'):
            hvac.window_open = not hvac.window_open
            print(f"🪟 [Window] 수동 조작: {'열림 (OPEN)' if hvac.window_open else '닫힘 (CLOSED)'}")

        # ── 분석 및 제어 루프 ('s') ───────────────────────────────────────────
        elif key == ord('s'):
            print("\n🔍 [Step 1] VLM 시각 분석 시작...")
            vlm_data = vlm.analyze_frame(frame)

            if not vlm_data:
                print("⚠️ [Warning] VLM 분석 실패. 's'를 다시 눌러 재시도하세요.")
                continue

            last_people_count = vlm_data['count']
            print(f"📊 [Step 2] 분석 결과: "
                  f"Met={vlm_data['met']}  Clo={vlm_data['clo']}  "
                  f"인원={last_people_count}명  "
                  f"활동={vlm_data['activity']}  "
                  f"가방={vlm_data['bags']}  "
                  f"열원={vlm_data['heat_source']}")

            # ── 상태 머신 갱신 ────────────────────────────────────────────────
            current_state = sm.update(
                people_count=last_people_count,
                outerwear=vlm_data['outerwear'],
                activity=vlm_data['activity'],
                bags=vlm_data['bags'],
            )
            print(f"🔄 [State] 현재 상태: {current_state.value}  "
                  f"(퇴근 맥락 점수: {sm.departure_score})")

            # ── tr 보정 (열원 감지 시 복사온도 상향) ─────────────────────────
            tr_corrected = hvac.indoor_temp
            if vlm_data['heat_source'] == 'yes':
                tr_corrected += VLMProcessor.TR_HEAT_OFFSET
                print(f"🔥 [Thermal] 열원 감지 → 복사온도 보정: {hvac.indoor_temp:.1f}°C → {tr_corrected:.1f}°C")

            # ── PMV 계산 ──────────────────────────────────────────────────────
            air_vel = FAN_VELOCITY.get(hvac.fan_speed, 0.1)
            pmv_val = engine.calculate_pmv(
                ta=hvac.indoor_temp,
                tr=tr_corrected,
                rh=hvac.indoor_humid,
                vel=air_vel,
                met=vlm_data['met'],
                clo=vlm_data['clo'],
            )
            comfort_msg = engine.get_comfort_status(pmv_val)
            print(f"🌡️ [Step 3] PMV: {pmv_val:.2f}  ({comfort_msg})")

            # PMV 쾌적도 통계 업데이트
            em.tick(hvac.is_on, hvac.fan_speed, last_people_count, pmv_val)

            # ── 자동 창문 제어 ────────────────────────────────────────────────
            window_cmd = decide_window(
                state=current_state,
                pmv_val=pmv_val,
                outdoor_temp=out_temp,
                indoor_temp=hvac.indoor_temp,
                heat_source=vlm_data['heat_source'],
            )
            if window_cmd is not None:
                if hvac.window_open != window_cmd:
                    hvac.window_open = window_cmd
                    reason = ("열원/환기 필요" if vlm_data['heat_source'] == 'yes'
                              else "퇴근 준비" if current_state == SystemState.PRE_DEPARTURE
                              else "자연환기 조건 충족" if window_cmd
                              else "빈 공간")
                    print(f"🪟 [Window] 자동 {'열림' if window_cmd else '닫힘'} ({reason})")

            # ── 인원 반영 시뮬레이션 재갱신 ──────────────────────────────────
            hvac.simulate_step(out_temp, out_humid, people_count=last_people_count)

            # ── 공조기 제어 결정 ──────────────────────────────────────────────
            print("🎮 [Step 4] 공조기 제어 명령 하달")
            power, target_temp, fan_speed = decide_control(
                state=current_state,
                pmv_val=pmv_val,
                people_count=last_people_count,
                outdoor_temp=out_temp,
            )

            if power is False:
                print("  → 빈 공간 / 퇴근 완료: 공조기 OFF")
                hvac.set_control(power=False, target=hvac.target_temp, fan=1)
                target_temp = hvac.target_temp
                fan_speed   = hvac.fan_speed
            elif power is True:
                label = {
                    SystemState.ARRIVAL:       "도착 초기 강제 냉·난방",
                    SystemState.PRE_DEPARTURE: "퇴근 준비 절전 모드",
                    SystemState.STEADY:        "냉방 강화" if pmv_val > 0.5 else "난방/절전",
                }.get(current_state, "제어")
                print(f"  → {label}: 목표 {target_temp}°C, 풍량 {fan_speed}")
                hvac.set_control(power=True, target=target_temp, fan=fan_speed)
            else:
                print("  → 쾌적 상태 유지 (변경 없음)")
                target_temp = hvac.target_temp
                fan_speed   = hvac.fan_speed

            # ── CSV 로그 저장 ─────────────────────────────────────────────────
            save_log({
                'timestamp':      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'scenario':       SCENARIO_NAME,
                'system_state':   current_state.value,
                'departure_score': sm.departure_score,
                'out_temp':       out_temp,
                'out_humid':      out_humid,
                'out_weather':    out_weather,
                'out_wind':       out_wind,
                'in_temp':        hvac.indoor_temp,
                'in_humid':       hvac.indoor_humid,
                'people_count':   last_people_count,
                'met':            vlm_data['met'],
                'clo':            vlm_data['clo'],
                'activity':       vlm_data['activity'],
                'bags':           vlm_data['bags'],
                'heat_source':    vlm_data['heat_source'],
                'window_open':    hvac.window_open,
                'room_size':      hvac.room_size,
                'air_vel':        air_vel,
                'pmv_val':        pmv_val,
                'comfort_status': comfort_msg,
                'target_temp':    target_temp,
                'fan_speed':      fan_speed,
                'power_w':        em.get_current_power_w(hvac.is_on, hvac.fan_speed),
                'energy_kwh':     em.get_energy_kwh(),
                'baseline_kwh':   em.get_baseline_kwh(),
                'savings_pct':    em.get_savings_pct(),
                'comfort_rate':   em.get_comfort_rate(),
            })
            print(f"💾 [Log] {LOG_FILE} 에 저장 완료\n")

        # ── 종료 ('q') ────────────────────────────────────────────────────────
        elif key == ord('q'):
            print("\n👋 프로그램을 종료합니다.")
            em.print_summary()
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
