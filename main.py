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

# PMV 재계산 + PID 제어 주기 (초) — VLM 없이도 온도 변화에 반응
PMV_UPDATE_SEC = 5


def initialize_csv():
    if not os.path.exists(LOG_FILE):
        columns = [
            "timestamp", "scenario",
            "system_state",
            "out_temp", "out_humid", "out_weather", "out_wind",
            "in_temp", "in_humid",
            "people_count", "count_source", "met", "clo", "activity",
            "heat_source",
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


def decide_control(pmv_val: float, people_count: int, pid: PIDController,
                   hvac_is_on: bool = False, hvac_mode: str = "cool"):
    """
    순수 PMV 기반 제어 (히스테리시스 적용).

    목표온도는 항상 COMFORT_TEMP(24°C) 고정.
    ─ 켜는 임계값: PMV > +0.5 (냉방) / PMV < -0.5 (난방)
    ─ 끄는 임계값: PMV < +0.2 (냉방 종료) / PMV > -0.2 (난방 종료)
    → 경계 근처에서 켜졌다 꺼졌다 반복(oscillation) 방지
    """
    COMFORT_TEMP = 24.0
    PMV_ON  = 0.5    # AC 켜는 절대값 임계
    PMV_OFF = 0.2    # AC 끄는 절대값 임계 (히스테리시스 간격)

    if people_count == 0:
        pid.reset()
        return False, COMFORT_TEMP, 1, None

    pid_output = pid.compute(pmv_val)
    fan = max(1, PIDController.output_to_fan_speed(pid_output))

    # 냉방
    if pmv_val > PMV_ON:
        return True, COMFORT_TEMP, fan, "cool"
    if hvac_is_on and hvac_mode == "cool" and pmv_val > PMV_OFF:
        return True, COMFORT_TEMP, fan, "cool"   # 히스테리시스 유지

    # 난방
    if pmv_val < -PMV_ON:
        return True, COMFORT_TEMP, fan, "heat"
    if hvac_is_on and hvac_mode == "heat" and pmv_val < -PMV_OFF:
        return True, COMFORT_TEMP, fan, "heat"   # 히스테리시스 유지

    # 쾌적 구간 → OFF
    pid.reset()
    return False, COMFORT_TEMP, 1, None


def decide_window(pmv_val: float, outdoor_temp: float,
                  indoor_temp: float, heat_source: str,
                  hvac_mode: str, people_count: int):
    if people_count == 0:
        return False
    if heat_source == "yes":
        return True
    if hvac_mode == "heat":
        return None
    if pmv_val > 0.5 and outdoor_temp < indoor_temp - 2.0:
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
    if motion_det.should_override_vlm():
        effective_met = motion_det.get_motion_met()
        met_source    = "motion"
    else:
        effective_met = vlm_data["met"]
        met_source    = "vlm"

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

    window_cmd = decide_window(pmv_val, out_temp, sensor_temp,
                               vlm_data["heat_source"], hvac.mode, people_count)
    if window_cmd is not None and hvac.window_open != window_cmd:
        hvac.window_open = window_cmd

    hvac.set_room(vlm_data["room_size_m2"], hvac.window_open)

    power, target_temp, fan_speed, mode = decide_control(
        pmv_val, people_count, pid, hvac.is_on, hvac.mode)

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
        "room_size":     vlm_data["room_size"],
        "room_size_m2":  vlm_data["room_size_m2"],
        "outerwear":     vlm_data["outerwear"],
        "heat_source":   vlm_data["heat_source"],
        "met_source":    met_source,
        "last_analysis": datetime.now().strftime("%H:%M:%S"),
        "pm10":          pm10,
        "pm25":          pm25,
        "khai":          khai,
    })

    occupied = "occupied" if people_count > 0 else "empty"
    return {
        "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scenario":        SCENARIO_NAME,
        "system_state":    occupied,
        "out_temp":        out_temp, "out_humid":   out_humid,
        "out_weather":     out_weather, "out_wind": out_wind,
        "in_temp":         sensor_temp, "in_humid": sensor_humid,
        "people_count":    people_count,
        "count_source":    count_source,
        "met":             effective_met, "clo": vlm_data["clo"],
        "activity":        vlm_data["activity"],
        "heat_source": vlm_data["heat_source"],
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
        print("카메라를 열 수 없습니다. 시뮬레이션 모드로 전환합니다.")
        # 시뮬레이션용 더미 프레임 생성 (카메라 없음)
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(dummy_frame, "Simulation Mode", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(dummy_frame, "No Camera Available", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        use_camera = False
    else:
        print("카메라가 성공적으로 연결되었습니다.")
        use_camera = True

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
        "room_size": "medium", "room_size_m2": 30.0,
        "outerwear": "no", "heat_source": "no",
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
    last_pmv_update    = 0.0
    frame_count        = 0

    # ── 수동 제어 상태 ────────────────────────────────────────────────────────
    manual_ctrl = {
        "enabled":     False,
        "power":       False,
        "mode":        "cool",
        "target_temp": 24.0,
        "fan_speed":   2,
    }

    # ── 환경 강제 오버라이드 (개발/테스트용) ─────────────────────────────────
    _ENV_VARS  = ["indoor_temp", "outdoor_temp", "indoor_humid", "outdoor_humid"]
    _ENV_STEPS = {"indoor_temp": 1.0, "outdoor_temp": 1.0,
                  "indoor_humid": 5.0, "outdoor_humid": 5.0}
    _ENV_LABEL = {"indoor_temp": "실내온도", "outdoor_temp": "실외온도",
                  "indoor_humid": "실내습도", "outdoor_humid": "실외습도"}
    env_override = {
        "enabled":      False,
        "indoor_temp":  22.0,
        "outdoor_temp": 20.0,
        "indoor_humid": 50.0,
        "outdoor_humid": 60.0,
        "selected":     0,      # _ENV_VARS 인덱스
    }

    while True:
        if use_camera:
            ret, frame = cap.read()
            if not ret:
                print("카메라 프레임을 읽을 수 없습니다. 시뮬레이션으로 전환합니다.")
                use_camera = False
                frame = dummy_frame.copy()
            else:
                frame = frame
        else:
            frame = dummy_frame.copy()  # 시뮬레이션용 더미 프레임 사용

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

        # ── PMV 재계산 + PID 제어 (5초마다, VLM 없으면 기본값 사용) ─────────
        now = time.time()
        if (not manual_ctrl["enabled"]
                and now - last_pmv_update >= PMV_UPDATE_SEC):
            last_pmv_update = now
            s_temp  = env_override["indoor_temp"]  if env_override["enabled"] else hvac.indoor_temp
            s_humid = env_override["indoor_humid"] if env_override["enabled"] else hvac.indoor_humid
            eff_out = env_override["outdoor_temp"] if env_override["enabled"] else out_temp

            # VLM 데이터 없으면 기본값으로 PMV 계산
            if last_vlm_data is not None:
                heat_src = last_vlm_data["heat_source"]
                eff_met  = (motion_det.get_motion_met()
                            if motion_det.should_override_vlm()
                            else last_vlm_data["met"])
                eff_clo  = last_vlm_data["clo"]
                met_src  = "motion" if motion_det.should_override_vlm() else "vlm"
            else:
                heat_src = "no"
                eff_met  = 1.2    # 기본 기립 수준
                eff_clo  = 1.0    # 기본 긴 소매
                met_src  = "default"

            tr_c    = s_temp + (VLMProcessor.TR_HEAT_OFFSET if heat_src == "yes" else 0.0)
            air_vel = FAN_VELOCITY.get(hvac.fan_speed, 0.1)
            pmv_now = engine.calculate_pmv(ta=s_temp, tr=tr_c,
                                           rh=s_humid, vel=air_vel,
                                           met=eff_met, clo=eff_clo)
            display_state["pmv_val"]     = pmv_now
            display_state["comfort_msg"] = engine.get_comfort_status(pmv_now)
            display_state["met"]         = eff_met
            display_state["met_source"]  = met_src

            power, tgt, fan, mode = decide_control(
                pmv_now, last_people_count, pid, hvac.is_on, hvac.mode)
            if power is True:
                hvac.set_control(power=True, target=tgt, fan=fan, mode=mode)
            elif power is False:
                hvac.set_control(power=False, target=hvac.target_temp, fan=1)

        # ── 수동 모드: 자동 제어 대신 수동 설정 즉시 적용 ───────────────────
        if manual_ctrl["enabled"]:
            hvac.set_control(
                power  = manual_ctrl["power"],
                target = manual_ctrl["target_temp"],
                fan    = manual_ctrl["fan_speed"],
                mode   = manual_ctrl["mode"],
            )

        eff_out_temp  = env_override["outdoor_temp"]  if env_override["enabled"] else out_temp
        eff_out_humid = env_override["outdoor_humid"] if env_override["enabled"] else out_humid
        hvac.simulate_step(eff_out_temp, eff_out_humid, people_count=last_people_count)

        # 환경 오버라이드: 시뮬 결과 덮어쓰기
        if env_override["enabled"]:
            hvac.indoor_temp  = env_override["indoor_temp"]
            hvac.indoor_humid = env_override["indoor_humid"]

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
        panel = dash.build(cam_h, hvac, sm,
                           out_temp, out_humid, out_weather, out_wind,
                           display_state, manual_ctrl, env_override)
        panel_h = panel.shape[0]
        if cam_h < panel_h:
            pad = np.zeros((panel_h - cam_h, frame.shape[1], 3), dtype=np.uint8)
            frame_disp = np.vstack([frame, pad])
        else:
            frame_disp = frame
        combined = np.hstack([frame_disp, panel])
        cv2.imshow("VLM Intelligent HVAC System", combined)

        key = cv2.waitKey(1) & 0xFF

        # ── 공통 키 ───────────────────────────────────────────────────────────
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

        # ── 환경 오버라이드 키 ────────────────────────────────────────────────
        elif key == ord("e"):
            env_override["enabled"] = not env_override["enabled"]
            if env_override["enabled"]:
                env_override["indoor_temp"]   = round(hvac.indoor_temp, 1)
                env_override["outdoor_temp"]  = round(out_temp, 1)
                env_override["indoor_humid"]  = round(hvac.indoor_humid, 1)
                env_override["outdoor_humid"] = round(out_humid, 1)
                print(f"[환경 오버라이드 ON] 현재값으로 초기화")
            else:
                print(f"[환경 오버라이드 OFF] 실제 시뮬레이션 복귀")

        elif env_override["enabled"] and not manual_ctrl["enabled"]:
            sel_key = _ENV_VARS[env_override["selected"]]
            step    = _ENV_STEPS[sel_key]
            if key == ord("["):
                env_override["selected"] = (env_override["selected"] - 1) % len(_ENV_VARS)
                print(f"[환경] 선택: {_ENV_LABEL[_ENV_VARS[env_override['selected']]]}")
            elif key == ord("]"):
                env_override["selected"] = (env_override["selected"] + 1) % len(_ENV_VARS)
                print(f"[환경] 선택: {_ENV_LABEL[_ENV_VARS[env_override['selected']]]}")
            elif key == ord("=") or key == ord("+"):
                env_override[sel_key] = round(env_override[sel_key] + step, 1)
                print(f"[환경] {_ENV_LABEL[sel_key]} = {env_override[sel_key]}")
            elif key == ord("-"):
                env_override[sel_key] = round(env_override[sel_key] - step, 1)
                print(f"[환경] {_ENV_LABEL[sel_key]} = {env_override[sel_key]}")

        # ── 수동 제어 키 ──────────────────────────────────────────────────────
        elif key == ord("m"):
            # M: 수동/자동 모드 전환
            manual_ctrl["enabled"] = not manual_ctrl["enabled"]
            if manual_ctrl["enabled"]:
                # 자동→수동 전환 시 현재 hvac 상태를 수동 초기값으로 복사
                manual_ctrl["power"]       = hvac.is_on
                manual_ctrl["mode"]        = hvac.mode if hasattr(hvac.mode, '__len__') else "cool"
                manual_ctrl["target_temp"] = hvac.target_temp
                manual_ctrl["fan_speed"]   = max(1, hvac.fan_speed)
                print(f"[수동 모드 ON] 현재 설정 복사 완료")
            else:
                pid.reset()
                print(f"[자동 모드 복귀]")

        elif manual_ctrl["enabled"]:
            # 수동 모드 전용 키
            if key == ord("p"):
                # P: 전원 ON/OFF
                manual_ctrl["power"] = not manual_ctrl["power"]
                print(f"[수동] 전원 {'ON' if manual_ctrl['power'] else 'OFF'}")

            elif key == ord("c"):
                # C: 냉방 모드
                manual_ctrl["mode"]  = "cool"
                manual_ctrl["power"] = True
                print("[수동] 냉방 모드")

            elif key == ord("h"):
                # H: 난방 모드
                manual_ctrl["mode"]  = "heat"
                manual_ctrl["power"] = True
                print("[수동] 난방 모드")

            elif key == ord("=") or key == ord("+"):
                # +: 설정온도 +1°C
                manual_ctrl["target_temp"] = min(30.0, manual_ctrl["target_temp"] + 1.0)
                print(f"[수동] 설정온도 {manual_ctrl['target_temp']:.0f}°C")

            elif key == ord("-"):
                # -: 설정온도 -1°C
                manual_ctrl["target_temp"] = max(16.0, manual_ctrl["target_temp"] - 1.0)
                print(f"[수동] 설정온도 {manual_ctrl['target_temp']:.0f}°C")

            elif key == ord("f"):
                # F: 팬 속도 순환 (1→2→3→1)
                manual_ctrl["fan_speed"] = manual_ctrl["fan_speed"] % 3 + 1
                print(f"[수동] 팬 속도 Fan {manual_ctrl['fan_speed']}")

    if use_camera:
        cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VLM 기반 지능형 HVAC 제어 시스템")
    parser.add_argument("--interval", type=int, default=30,
                        help="VLM 분석 주기(초) 기본:30 / M5 Mac:10~15 / Jetson:5~10")
    args = parser.parse_args()
    main(analysis_interval=args.interval)
