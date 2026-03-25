import cv2
import os
import queue
import threading
import time
import argparse
import pandas as pd
from datetime import datetime

from vlm_processor import VLMProcessor
from weather_service import WeatherService
from hvac_simulator import HVACSimulator
from thermal_engine import ThermalEngine
from state_machine import StateManager, SystemState
from energy_monitor import EnergyMonitor
from motion_detector import MotionDetector

# ─── 설정 상수 ───────────────────────────────────────────────────────────────
LOG_FILE      = "hvac_system_performance.csv"
SCENARIO_NAME = "Smart_Office_Initial_Test"

WEATHER_API_KEY = "97e9ad342e69a006e6c55886b18842c2"
WEATHER_LAT     = 35.1044
WEATHER_LON     = 128.9750

ROOM_SIZE_M2    = 20.0
WINDOW_OPEN     = False

WORK_START_HOUR = 9
WORK_END_HOUR   = 18

FAN_VELOCITY = {1: 0.1, 2: 0.3, 3: 0.5}
# ─────────────────────────────────────────────────────────────────────────────


def initialize_csv():
    if not os.path.exists(LOG_FILE):
        columns = [
            'timestamp', 'scenario',
            'system_state', 'departure_score',
            'out_temp', 'out_humid', 'out_weather', 'out_wind',
            'in_temp', 'in_humid',
            'people_count', 'met', 'clo', 'activity',
            'bags', 'heat_source',
            'motion_score', 'met_source',
            'window_open', 'room_size', 'air_vel',
            'pmv_val', 'comfort_status',
            'target_temp', 'fan_speed',
            'power_w', 'energy_kwh', 'baseline_kwh', 'savings_pct', 'comfort_rate',
        ]
        pd.DataFrame(columns=columns).to_csv(LOG_FILE, index=False)
        print(f"📁 [System] 새 로그 파일 생성: {LOG_FILE}")


def save_log(data: dict):
    pd.DataFrame([data]).to_csv(LOG_FILE, mode='a', index=False, header=False)


def decide_control(state: SystemState, pmv_val: float,
                   people_count: int, outdoor_temp: float):
    if state == SystemState.EMPTY:
        return False, None, None
    if state == SystemState.ARRIVAL:
        if outdoor_temp > 25.0:
            return True, 20.0, 3
        elif outdoor_temp < 10.0:
            return True, 26.0, 3
        else:
            return True, 22.0, 2
    if state == SystemState.PRE_DEPARTURE:
        return True, 25.0, 1
    if pmv_val > 0.5:
        occ_offset  = min(2.0, max(0, people_count - 1) * 0.5)
        target_temp = round(22.0 - occ_offset, 1)
        fan_speed   = min(3, 2 + (1 if people_count >= 3 else 0))
        return True, target_temp, fan_speed
    elif pmv_val < -0.5:
        return True, 26.0, 1
    else:
        return None, None, None


def decide_window(state: SystemState, pmv_val: float,
                  outdoor_temp: float, indoor_temp: float,
                  heat_source: str):
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
              energy: EnergyMonitor, departure_score: int,
              motion_score: float) -> list:
    win  = "O" if hvac.window_open else "C"
    mode = "ON" if hvac.is_on else "OFF"
    line1 = (f"Temp:{hvac.indoor_temp:.1f}C  Humid:{hvac.indoor_humid:.1f}%  "
             f"AC:{mode}({hvac.target_temp:.0f}C/Fan{hvac.fan_speed})  Win:{win}")
    line2 = (f"State:{state.value}  Score:{departure_score}  "
             f"Motion:{motion_score:.1f}  "
             f"Save:{energy.get_savings_pct():.1f}%  "
             f"Power:{energy.get_current_power_w(hvac.is_on, hvac.fan_speed)}W")
    return [line1, line2]


# ── VLM 백그라운드 스레드 ─────────────────────────────────────────────────────

def vlm_worker(vlm, frame_lock, shared_frame_ref,
               result_queue, stop_event, interval):
    """
    interval초마다 VLM 분석을 실행하고 결과를 Queue에 적재합니다.
    CPU 개발환경: 30초 권장 / Jetson(TensorRT): 5~10초 가능.
    """
    while not stop_event.is_set():
        elapsed = 0.0
        while elapsed < interval and not stop_event.is_set():
            time.sleep(0.5)
            elapsed += 0.5

        if stop_event.is_set():
            break

        with frame_lock:
            if shared_frame_ref[0] is None:
                continue
            frame_copy = shared_frame_ref[0].copy()

        print("\n🤖 [VLM-Thread] 자동 분석 시작...")
        result = vlm.analyze_frame(frame_copy)

        if result is None:
            print("⚠️ [VLM-Thread] 분석 실패, 건너뜀")
            continue

        try:
            result_queue.get_nowait()
        except queue.Empty:
            pass
        result_queue.put_nowait(result)
        print("✅ [VLM-Thread] 결과 적재 완료")


# ── VLM 결과 처리 ─────────────────────────────────────────────────────────────

def process_vlm_result(vlm_data, motion_det, hvac, sm, engine, em,
                       out_temp, out_humid, out_weather, out_wind):
    people_count = vlm_data['count']

    print(f"📊 [VLM] Met={vlm_data['met']}  Clo={vlm_data['clo']}  "
          f"인원={people_count}명  활동={vlm_data['activity']}  "
          f"가방={vlm_data['bags']}  열원={vlm_data['heat_source']}")

    current_state = sm.update(
        people_count=people_count,
        outerwear=vlm_data['outerwear'],
        activity=vlm_data['activity'],
        bags=vlm_data['bags'],
    )
    print(f"🔄 [State] {current_state.value}  (퇴근 점수: {sm.departure_score})")

    # MET 결정: motion override 여부
    if motion_det.should_override_vlm():
        effective_met = motion_det.get_motion_met()
        met_source    = "motion"
    else:
        effective_met = vlm_data['met']
        met_source    = "vlm"
    print(f"🏃 [MET] {met_source} 기반: {effective_met} met  "
          f"(motion_score={motion_det.current_score:.1f})")

    # tr 보정 (열원 감지 시 +4°C)
    tr_corrected = hvac.indoor_temp
    if vlm_data['heat_source'] == 'yes':
        tr_corrected += VLMProcessor.TR_HEAT_OFFSET
        print(f"🔥 [Thermal] 열원 감지 → tr 보정: {hvac.indoor_temp:.1f} → {tr_corrected:.1f}°C")

    # PMV 계산
    air_vel = FAN_VELOCITY.get(hvac.fan_speed, 0.1)
    pmv_val = engine.calculate_pmv(
        ta=hvac.indoor_temp, tr=tr_corrected,
        rh=hvac.indoor_humid, vel=air_vel,
        met=effective_met, clo=vlm_data['clo'],
    )
    comfort_msg = engine.get_comfort_status(pmv_val)
    print(f"🌡️ [PMV] {pmv_val:.2f}  ({comfort_msg})")

    em.tick(hvac.is_on, hvac.fan_speed, people_count, pmv_val)

    # 자동 창문 제어
    window_cmd = decide_window(current_state, pmv_val, out_temp,
                               hvac.indoor_temp, vlm_data['heat_source'])
    if window_cmd is not None and hvac.window_open != window_cmd:
        hvac.window_open = window_cmd
        reason = ("열원/환기" if vlm_data['heat_source'] == 'yes'
                  else "퇴근 준비" if current_state == SystemState.PRE_DEPARTURE
                  else "자연환기" if window_cmd else "빈 공간")
        print(f"🪟 [Window] 자동 {'열림' if window_cmd else '닫힘'} ({reason})")

    hvac.simulate_step(out_temp, out_humid, people_count=people_count)

    # 공조기 제어
    print("🎮 [Control] 제어 명령 하달")
    power, target_temp, fan_speed = decide_control(
        current_state, pmv_val, people_count, out_temp)

    if power is False:
        print("  → 빈 공간: 공조기 OFF")
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

    return {
        'timestamp':       datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'scenario':        SCENARIO_NAME,
        'system_state':    current_state.value,
        'departure_score': sm.departure_score,
        'out_temp':        out_temp,
        'out_humid':       out_humid,
        'out_weather':     out_weather,
        'out_wind':        out_wind,
        'in_temp':         hvac.indoor_temp,
        'in_humid':        hvac.indoor_humid,
        'people_count':    people_count,
        'met':             effective_met,
        'clo':             vlm_data['clo'],
        'activity':        vlm_data['activity'],
        'bags':            vlm_data['bags'],
        'heat_source':     vlm_data['heat_source'],
        'motion_score':    round(motion_det.current_score, 2),
        'met_source':      met_source,
        'window_open':     hvac.window_open,
        'room_size':       hvac.room_size,
        'air_vel':         air_vel,
        'pmv_val':         pmv_val,
        'comfort_status':  comfort_msg,
        'target_temp':     target_temp,
        'fan_speed':       fan_speed,
        'power_w':         em.get_current_power_w(hvac.is_on, hvac.fan_speed),
        'energy_kwh':      em.get_energy_kwh(),
        'baseline_kwh':    em.get_baseline_kwh(),
        'savings_pct':     em.get_savings_pct(),
        'comfort_rate':    em.get_comfort_rate(),
    }


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(analysis_interval: int = 30):
    print("⚙️ [System] 지능형 공조 제어 시스템 초기화 중...")
    initialize_csv()

    vlm        = VLMProcessor()
    weather    = WeatherService(lat=WEATHER_LAT, lon=WEATHER_LON, api_key=WEATHER_API_KEY)
    hvac       = HVACSimulator(room_size=ROOM_SIZE_M2)
    hvac.set_room(ROOM_SIZE_M2, WINDOW_OPEN)
    engine     = ThermalEngine()
    sm         = StateManager(work_start_hour=WORK_START_HOUR, work_end_hour=WORK_END_HOUR)
    em         = EnergyMonitor()
    motion_det = MotionDetector(history_len=10, blur_ksize=21)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ [Error] 카메라를 열 수 없습니다.")
        return

    # ── 스레딩 공유 자원 ────────────────────────────────────────────────────
    frame_lock       = threading.Lock()
    shared_frame_ref = [None]               # Lock으로 보호되는 최신 프레임
    result_queue     = queue.Queue(maxsize=1)
    stop_event       = threading.Event()

    vlm_thread = threading.Thread(
        target=vlm_worker,
        args=(vlm, frame_lock, shared_frame_ref,
              result_queue, stop_event, analysis_interval),
        daemon=True,
        name="VLM-Background",
    )
    vlm_thread.start()

    print("\n✅ 모든 모듈 준비 완료!")
    print(f"📍 날씨 조회: ({WEATHER_LAT}, {WEATHER_LON})  |  방 크기: {ROOM_SIZE_M2}m²")
    print(f"🕐 근무 시간: {WORK_START_HOUR}:00 ~ {WORK_END_HOUR}:00")
    print(f"⏱️  자동 VLM 분석: {analysis_interval}초마다  (수동: 's' 키)")
    print("⌨️  's': 즉시 분석  |  'w': 창문 수동 개폐  |  'q': 종료\n")

    last_people_count = 0
    out_temp    = 20.0
    out_humid   = 50.0
    out_weather = "unknown"
    out_wind    = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # ── 공유 프레임 갱신 ────────────────────────────────────────────────
        with frame_lock:
            shared_frame_ref[0] = frame.copy()

        # ── 모션 감지 (매 프레임) ────────────────────────────────────────────
        motion_det.update(frame)

        # ── 기상·시뮬·에너지 갱신 ───────────────────────────────────────────
        out_temp, out_humid, out_weather, out_wind = weather.fetch_current_weather()
        hvac.simulate_step(out_temp, out_humid, people_count=last_people_count)
        em.tick(hvac.is_on, hvac.fan_speed, last_people_count)

        # ── VLM 결과 Queue 폴링 (비블로킹) ──────────────────────────────────
        try:
            vlm_data = result_queue.get_nowait()
            last_people_count = vlm_data['count']
            log_row = process_vlm_result(
                vlm_data, motion_det, hvac, sm, engine, em,
                out_temp, out_humid, out_weather, out_wind,
            )
            save_log(log_row)
            print(f"💾 [Log] {LOG_FILE} 저장 완료\n")
        except queue.Empty:
            pass

        # ── HUD 렌더링 ───────────────────────────────────────────────────────
        hud_lines = build_hud(hvac, sm.state, em, sm.departure_score,
                              motion_det.current_score)
        cv2.putText(frame, hud_lines[0], (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        cv2.putText(frame, hud_lines[1], (10, 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 200, 255), 1)
        cv2.imshow('VLM Intelligent HVAC System', frame)

        key = cv2.waitKey(1) & 0xFF

        # ── 창문 수동 토글 ('w') ─────────────────────────────────────────────
        if key == ord('w'):
            hvac.window_open = not hvac.window_open
            print(f"🪟 [Window] 수동: {'열림' if hvac.window_open else '닫힘'}")

        # ── 즉시 수동 분석 ('s') ─────────────────────────────────────────────
        elif key == ord('s'):
            print("\n🔍 [Manual] 즉시 VLM 분석 시작 (블로킹)...")
            with frame_lock:
                frame_copy = shared_frame_ref[0].copy()
            vlm_data = vlm.analyze_frame(frame_copy)
            if vlm_data:
                last_people_count = vlm_data['count']
                log_row = process_vlm_result(
                    vlm_data, motion_det, hvac, sm, engine, em,
                    out_temp, out_humid, out_weather, out_wind,
                )
                save_log(log_row)
                print(f"💾 [Log] {LOG_FILE} 저장 완료\n")
            else:
                print("⚠️ [Manual] 분석 실패\n")

        # ── 종료 ('q') ───────────────────────────────────────────────────────
        elif key == ord('q'):
            print("\n👋 프로그램 종료 중...")
            stop_event.set()
            vlm_thread.join(timeout=5)
            em.print_summary()
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='VLM 기반 지능형 HVAC 제어 시스템')
    parser.add_argument(
        '--interval', type=int, default=30,
        help='자동 VLM 분석 주기 (초, 기본값: 30 / M5 Mac MPS 권장: 10~15 / Jetson TensorRT 권장: 5~10)'
    )
    args = parser.parse_args()
    main(analysis_interval=args.interval)
