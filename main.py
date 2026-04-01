import cv2
import os
import queue
import threading
import time
import argparse
import numpy as np
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

from vlm_processor import VLMProcessor
from weather_service import WeatherService
from air_quality_service import AirQualityService
from hvac_simulator import HVACSimulator
from thermal_engine import ThermalEngine
from state_machine import StateManager, SystemState
from energy_monitor import EnergyMonitor
from motion_detector import MotionDetector
from yolo_detector import YOLODetector
from pid_controller import PIDController
from sensor_interface import SensorInterface
import dashboard as dash

# .env 파일 로드
load_dotenv()

LOG_FILE      = "hvac_system_performance.csv"
SCENARIO_NAME = "Smart_Office_Initial_Test"

WEATHER_API_KEY   = os.getenv("WEATHER_API_KEY", "97e9ad342e69a006e6c55886b18842c2")
WEATHER_LAT       = 35.1044
WEATHER_LON       = 128.9750
WEATHER_FETCH_SEC = 60

AIR_QUALITY_API_KEY = os.getenv("AIR_QUALITY_API_KEY", "")
AIR_QUALITY_STATION = os.getenv("AIR_QUALITY_STATION", "장림동")

ROOM_SIZE_M2    = 20.0
WINDOW_OPEN     = False
WORK_START_HOUR = 9
WORK_END_HOUR   = 18
FAN_VELOCITY    = {1: 0.1, 2: 0.3, 3: 0.5}

# YOLO 인원 감지 주기 (매 N프레임마다 실행)
YOLO_EVERY_N_FRAMES = 5


def initialize_csv():
    if not os.path.exists(LOG_FILE):
        columns = [
            "timestamp", "scenario",
            "system_state", "departure_score",
            "out_temp", "out_humid", "out_weather", "out_wind",
            "in_temp", "in_humid",
            "people_count", "count_source", "met", "clo", "activity",
            "bags", "heat_source",
            "motion_score", "met_source",
            "hvac_mode", "window_open", "room_size", "air_vel",
            "pmv_val", "comfort_status",
            "target_temp", "fan_speed",
            "power_w", "energy_kwh", "baseline_kwh", "savings_pct", "comfort_rate",
            "pm10", "pm25", "khai",
        ]
        pd.DataFrame(columns=columns).to_csv(LOG_FILE, index=False)


def save_log(data: dict):
    pd.DataFrame([data]).to_csv(LOG_FILE, mode="a", index=False, header=False)


def decide_control(state: SystemState, pmv_val: float,
                   people_count: int, outdoor_temp: float,
                   pid: PIDController):
    """
    시스템 상태별 제어 결정.
    STEADY 상태에서는 PID 출력으로 팬 속도를 결정합니다.
    """
    if state == SystemState.EMPTY:
        pid.reset()
        return False, None, None, None
    if state == SystemState.ARRIVAL:
        pid.reset()
        if outdoor_temp < 15.0:
            return True, 25.0, 3, "heat"
        elif outdoor_temp > 28.0:
            return True, 22.0, 3, "cool"
        else:
            mode = "heat" if outdoor_temp < 22.0 else "cool"
            return True, (25.0 if mode == "heat" else 23.0), 2, mode
    if state == SystemState.PRE_DEPARTURE:
        return True, 25.0, 1, None

    # STEADY: PID 제어
    pid_output = pid.compute(pmv_val)
    if abs(pid_output) < 0.01:   # deadband 내 — 현재 설정 유지
        return None, None, None, None
    if pid_output > 0:           # 난방 필요 (PMV 음수)
        fan = PIDController.output_to_fan_speed(pid_output)
        occ_offset = min(2.0, max(0, people_count - 1) * 0.5)
        return True, round(25.0 + occ_offset * 0.5, 1), fan, "heat"
    else:                        # 냉방 필요 (PMV 양수)
        fan = PIDController.output_to_fan_speed(pid_output)
        occ_offset = min(2.0, max(0, people_count - 1) * 0.5)
        return True, round(22.0 - occ_offset, 1), fan, "cool"


def decide_window(state: SystemState, pmv_val: float,
                  outdoor_temp: float, indoor_temp: float,
                  heat_source: str, hvac_mode: str):
    if state == SystemState.EMPTY:
        return False
    if heat_source == "yes":
        return True
    if state == SystemState.PRE_DEPARTURE:
        return False
    if hvac_mode == "heat":
        return None
    if state == SystemState.STEADY and pmv_val > 0.5 and outdoor_temp < indoor_temp - 2.0:
        return True
    return None


def vlm_worker(vlm, frame_lock, shared_frame_ref,
               result_queue, stop_event, interval):
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
        result = vlm.analyze_frame(frame_copy)
        if result is None:
            continue
        try:
            result_queue.get_nowait()
        except queue.Empty:
            pass
        result_queue.put_nowait(result)


def process_vlm_result(vlm_data, people_count, count_source,
                       motion_det, hvac, sm, engine, em, pid,
                       sensor, display_state,
                       out_temp, out_humid, out_weather, out_wind,
                       pm10, pm25, khai):
    """
    VLM 결과 + YOLO 인원 수를 받아 PMV 계산, 제어 결정, 로그 저장.

    Args:
        vlm_data     : VLMProcessor.analyze_frame() 반환값
        people_count : YOLODetector 또는 폴백 인원 수
        count_source : 'yolo' | 'vlm_fallback'
    """
    current_state = sm.update(people_count=people_count,
                              outerwear=vlm_data["outerwear"],
                              activity=vlm_data["activity"],
                              bags=vlm_data["bags"])

    if motion_det.should_override_vlm():
        effective_met = motion_det.get_motion_met()
        met_source    = "motion"
    else:
        effective_met = vlm_data["met"]
        met_source    = "vlm"

    # SensorInterface: 실내 온습도 읽기 (simulate 모드에서는 hvac 값 그대로)
    sensor_temp, sensor_humid = sensor.read_climate()

    tr_corrected = sensor_temp
    if vlm_data["heat_source"] == "yes":
        tr_corrected += VLMProcessor.TR_HEAT_OFFSET

    air_vel     = FAN_VELOCITY.get(hvac.fan_speed, 0.1)
    pmv_val     = engine.calculate_pmv(ta=sensor_temp, tr=tr_corrected,
                                       rh=sensor_humid, vel=air_vel,
                                       met=effective_met, clo=vlm_data["clo"])
    comfort_msg = engine.get_comfort_status(pmv_val)
    em.tick(hvac.is_on, hvac.fan_speed, people_count, pmv_val)

    window_cmd = decide_window(current_state, pmv_val, out_temp,
                               sensor_temp, vlm_data["heat_source"], hvac.mode)
    if window_cmd is not None and hvac.window_open != window_cmd:
        hvac.window_open = window_cmd

    hvac.simulate_step(out_temp, out_humid, people_count=people_count)

    power, target_temp, fan_speed, mode = decide_control(
        current_state, pmv_val, people_count, out_temp, pid)

    if power is False:
        hvac.set_control(power=False, target=hvac.target_temp, fan=1)
        target_temp = hvac.target_temp
        fan_speed   = hvac.fan_speed
    elif power is True:
        hvac.set_control(power=True, target=target_temp, fan=fan_speed, mode=mode)
    else:
        target_temp = hvac.target_temp
        fan_speed   = hvac.fan_speed

    display_state.update({
        "pmv_val":       pmv_val,
        "comfort_msg":   comfort_msg,
        "people_count":  people_count,
        "count_source":  count_source,
        "activity":      vlm_data["activity"],
        "met":           effective_met,
        "clo":           vlm_data["clo"],
        "bags":          vlm_data["bags"],
        "heat_source":   vlm_data["heat_source"],
        "met_source":    met_source,
        "last_analysis": datetime.now().strftime("%H:%M:%S"),
        "pm10":          pm10,
        "pm25":          pm25,
        "khai":          khai,
    })

    return {
        "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scenario":        SCENARIO_NAME,
        "system_state":    current_state.value,
        "departure_score": sm.departure_score,
        "out_temp":        out_temp, "out_humid":   out_humid,
        "out_weather":     out_weather, "out_wind": out_wind,
        "in_temp":         sensor_temp, "in_humid": sensor_humid,
        "people_count":    people_count,
        "count_source":    count_source,
        "met":             effective_met, "clo": vlm_data["clo"],
        "activity":        vlm_data["activity"],
        "bags":            vlm_data["bags"], "heat_source": vlm_data["heat_source"],
        "motion_score":    round(motion_det.current_score, 2),
        "met_source":      met_source, "hvac_mode": hvac.mode,
        "window_open":     hvac.window_open, "room_size": hvac.room_size,
        "air_vel":         air_vel, "pmv_val": pmv_val,
        "comfort_status":  comfort_msg,
        "target_temp":     target_temp, "fan_speed": fan_speed,
        "power_w":         em.get_current_power_w(hvac.is_on, hvac.fan_speed),
        "energy_kwh":      em.get_energy_kwh(),
        "baseline_kwh":    em.get_baseline_kwh(),
        "savings_pct":     em.get_savings_pct(),
        "comfort_rate":    em.get_comfort_rate(),
        "pm10":            pm10,
        "pm25":            pm25,
        "khai":            khai,
    }


def main(analysis_interval: int = 30):
    initialize_csv()
    vlm        = VLMProcessor()
    weather    = WeatherService(lat=WEATHER_LAT, lon=WEATHER_LON)
    air_quality = AirQualityService(service_key=AIR_QUALITY_API_KEY, station_name=AIR_QUALITY_STATION)
    hvac       = HVACSimulator(room_size=ROOM_SIZE_M2)
    hvac.set_room(ROOM_SIZE_M2, WINDOW_OPEN)
    engine     = ThermalEngine()
    sm         = StateManager(work_start_hour=WORK_START_HOUR, work_end_hour=WORK_END_HOUR)
    em         = EnergyMonitor()
    motion_det = MotionDetector(history_len=10, blur_ksize=21)
    yolo       = YOLODetector(imgsz=320, conf=0.35)
    pid        = PIDController(kp=0.8, ki=0.05, kd=0.3)
    sensor     = SensorInterface(simulator=hvac)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return

    frame_lock       = threading.Lock()
    shared_frame_ref = [None]
    result_queue     = queue.Queue(maxsize=1)
    stop_event       = threading.Event()

    vlm_thread = threading.Thread(
        target=vlm_worker,
        args=(vlm, frame_lock, shared_frame_ref,
              result_queue, stop_event, analysis_interval),
        daemon=True, name="VLM-Background",
    )
    vlm_thread.start()

    display_state = {
        "pmv_val": 0.0, "comfort_msg": "분석 대기 중",
        "people_count": 0, "count_source": "yolo",
        "activity": "-",
        "met": 1.0, "clo": 1.0,
        "bags": "no", "heat_source": "no",
        "motion_score": 0.0, "met_source": "vlm",
        "last_analysis": "--:--:--",
        "pm10": 0, "pm25": 0, "khai": 0,
    }

    last_people_count  = 0
    last_count_source  = "yolo"
    last_vlm_data      = None
    out_temp, out_humid, out_weather, out_wind = 20.0, 50.0, "unknown", 0.0
    pm10, pm25, khai = 0, 0, 0
    last_weather_fetch = 0.0
    frame_count        = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        with frame_lock:
            shared_frame_ref[0] = frame.copy()

        motion_det.update(frame)
        display_state["motion_score"] = motion_det.current_score

        # ── YOLO 인원 감지 (매 N프레임) ───────────────────────────────────────
        if frame_count % YOLO_EVERY_N_FRAMES == 0:
            yolo_count = yolo.count_people(frame)
            if yolo_count >= 0:
                last_people_count = yolo_count
                last_count_source = "yolo"
            # yolo_count == -1: YOLO 미사용 → last_people_count(VLM 폴백) 유지

        if time.time() - last_weather_fetch >= WEATHER_FETCH_SEC:
            out_temp, out_humid, out_weather, out_wind = weather.fetch_current_weather()
            pm10, pm25, khai = air_quality.fetch_air_quality()
            last_weather_fetch = time.time()

        hvac.simulate_step(out_temp, out_humid, people_count=last_people_count)
        em.tick(hvac.is_on, hvac.fan_speed, last_people_count)

        # ── VLM 결과 처리 ─────────────────────────────────────────────────────
        try:
            vlm_data = result_queue.get_nowait()
            last_vlm_data = vlm_data

            # YOLO 가용 시 YOLO 인원 수 사용, 불가 시 VLM 폴백 없음(인원 유지)
            if not yolo.available:
                last_count_source = "vlm_fallback"

            log_row = process_vlm_result(
                vlm_data, last_people_count, last_count_source,
                motion_det, hvac, sm, engine, em, pid,
                sensor, display_state,
                out_temp, out_humid, out_weather, out_wind,
                pm10, pm25, khai,
            )
            save_log(log_row)
        except queue.Empty:
            pass

        cam_h = frame.shape[0]
        panel = dash.build(cam_h, hvac, sm, em,
                           out_temp, out_humid, out_weather, out_wind,
                           display_state)
        combined = np.hstack([frame, panel])
        cv2.imshow("VLM Intelligent HVAC System", combined)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("w"):
            hvac.window_open = not hvac.window_open

        elif key == ord("s"):
            with frame_lock:
                frame_copy = shared_frame_ref[0].copy()
            vlm_data = vlm.analyze_frame(frame_copy)
            if vlm_data:
                last_vlm_data = vlm_data
                log_row = process_vlm_result(
                    vlm_data, last_people_count, last_count_source,
                    motion_det, hvac, sm, engine, em, pid,
                    sensor, display_state,
                    out_temp, out_humid, out_weather, out_wind,
                    pm10, pm25, khai,
                )
                save_log(log_row)

        elif key == ord("q"):
            stop_event.set()
            vlm_thread.join(timeout=5)
            em.print_summary()
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VLM 기반 지능형 HVAC 제어 시스템")
    parser.add_argument("--interval", type=int, default=30,
                        help="VLM 분석 주기(초) 기본:30 / M5 Mac:10~15 / Jetson:5~10")
    args = parser.parse_args()
    main(analysis_interval=args.interval)
