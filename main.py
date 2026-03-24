import cv2
import os
import pandas as pd
from datetime import datetime

from vlm_processor import VLMProcessor
from weather_service import WeatherService
from hvac_simulator import HVACSimulator
from thermal_engine import ThermalEngine

# ─── 설정 상수 ───────────────────────────────────────────────────────────────
LOG_FILE      = "hvac_system_performance.csv"
SCENARIO_NAME = "Smart_Office_Initial_Test"

WEATHER_API_KEY = "97e9ad342e69a006e6c55886b18842c2"
WEATHER_LAT     = 35.1044   # 사하구, 부산 위도
WEATHER_LON     = 128.9750  # 사하구, 부산 경도

ROOM_SIZE_M2    = 20.0   # 방 면적 (m²) – 실제 공간에 맞게 조정
WINDOW_OPEN     = False  # 창문 초기 상태

# 풍량 단계 → 실내 기류 속도(m/s) 변환 (PMV vel 입력용)
FAN_VELOCITY = {1: 0.1, 2: 0.3, 3: 0.5}
# ─────────────────────────────────────────────────────────────────────────────


def initialize_csv():
    """CSV 로그 파일이 없으면 헤더 포함 신규 생성"""
    if not os.path.exists(LOG_FILE):
        columns = [
            'timestamp', 'scenario',
            'out_temp', 'out_humid', 'out_weather', 'out_wind',
            'in_temp', 'in_humid',
            'people_count', 'met', 'clo',
            'window_open', 'room_size', 'air_vel',
            'pmv_val', 'comfort_status',
            'target_temp', 'fan_speed',
        ]
        pd.DataFrame(columns=columns).to_csv(LOG_FILE, index=False)
        print(f"📁 [System] 새 로그 파일 생성: {LOG_FILE}")


def save_log(data: dict):
    """딕셔너리 한 행을 CSV에 추가"""
    pd.DataFrame([data]).to_csv(LOG_FILE, mode='a', index=False, header=False)


def decide_control(pmv_val: float, people_count: int):
    """
    PMV 지수와 인원수를 기반으로 공조기 제어값 결정

    Returns:
        (power: bool, target_temp: float, fan_speed: int)
        power=None이면 '현재 유지' (set_control 호출 불필요)
    """
    if pmv_val > 0.5:
        # 더운 상태: 인원 많을수록 목표온도 낮추고 풍량 높임 (최대 2°C 하향)
        occ_offset  = min(2.0, max(0, people_count - 1) * 0.5)
        target_temp = round(22.0 - occ_offset, 1)
        fan_speed   = min(3, 2 + (1 if people_count >= 3 else 0))
        return True, target_temp, fan_speed

    elif pmv_val < -0.5:
        # 추운 상태: 난방/절전 모드
        return True, 26.0, 1

    else:
        # 쾌적 상태: 변경 없음
        return None, None, None


def build_hud(hvac: HVACSimulator) -> str:
    """실시간 화면 표시용 상태 문자열 생성"""
    win  = "O" if hvac.window_open else "C"
    mode = "ON" if hvac.is_on else "OFF"
    return (f"Temp:{hvac.indoor_temp:.1f}C  Humid:{hvac.indoor_humid:.1f}%  "
            f"AC:{mode}({hvac.target_temp:.0f}C/Fan{hvac.fan_speed})  Win:{win}")


def main():
    print("⚙️ [System] 지능형 공조 제어 시스템 초기화 중...")
    initialize_csv()

    vlm     = VLMProcessor()
    weather = WeatherService(lat=WEATHER_LAT, lon=WEATHER_LON, api_key=WEATHER_API_KEY)
    hvac    = HVACSimulator(room_size=ROOM_SIZE_M2)
    hvac.set_room(ROOM_SIZE_M2, WINDOW_OPEN)
    engine  = ThermalEngine()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ [Error] 카메라를 열 수 없습니다.")
        return

    print("\n✅ 모든 모듈 준비 완료!")
    print(f"📍 날씨 조회: ({WEATHER_LAT}, {WEATHER_LON})  |  방 크기: {ROOM_SIZE_M2}m²  |  창문: {'열림' if WINDOW_OPEN else '닫힘'}")
    print("⌨️  's': 분석 및 제어  |  'w': 창문 개폐 토글  |  'q': 종료\n")

    last_people_count = 1  # VLM 분석 전 기본 재실 인원

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # HUD 오버레이
        cv2.putText(frame, build_hud(hvac),
                    (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow('VLM Intelligent HVAC System', frame)

        # 실시간 날씨 수신 및 시뮬레이션 업데이트
        out_temp, out_humid, out_weather, out_wind = weather.fetch_current_weather()
        hvac.simulate_step(out_temp, out_humid, people_count=last_people_count)

        key = cv2.waitKey(1) & 0xFF

        # ── 창문 개폐 토글 ('w') ──────────────────────────────────────────────
        if key == ord('w'):
            hvac.window_open = not hvac.window_open
            print(f"🪟 [Window] {'열림 (OPEN)' if hvac.window_open else '닫힘 (CLOSED)'}")

        # ── 분석 및 제어 루프 ('s') ───────────────────────────────────────────
        elif key == ord('s'):
            print("\n🔍 [Step 1] VLM 시각 분석 시작...")
            vlm_data = vlm.analyze_frame(frame)

            if not vlm_data:
                print("⚠️ [Warning] VLM 분석 실패. 's'를 다시 눌러 재시도하세요.")
                continue

            last_people_count = vlm_data['count']
            print(f"📊 [Step 2] 분석 결과: Met={vlm_data['met']}  Clo={vlm_data['clo']}  인원={last_people_count}명")

            # 풍량 단계 → 기류 속도 변환
            air_vel = FAN_VELOCITY.get(hvac.fan_speed, 0.1)

            # PMV 계산
            pmv_val = engine.calculate_pmv(
                ta=hvac.indoor_temp,
                tr=hvac.indoor_temp,
                rh=hvac.indoor_humid,
                vel=air_vel,
                met=vlm_data['met'],
                clo=vlm_data['clo'],
            )
            comfort_msg = engine.get_comfort_status(pmv_val)
            print(f"🌡️ [Step 3] PMV: {pmv_val:.2f}  ({comfort_msg})")

            # 인원 반영 시뮬레이션 재갱신
            hvac.simulate_step(out_temp, out_humid, people_count=last_people_count)

            # 공조기 제어 결정
            print("🎮 [Step 4] 공조기 제어 명령 하달")
            power, target_temp, fan_speed = decide_control(pmv_val, last_people_count)

            if power is True:
                label = "냉방 강화" if pmv_val > 0.5 else "난방/절전"
                print(f"  → {label}: 목표 {target_temp}°C, 풍량 {fan_speed}")
                hvac.set_control(power=True, target=target_temp, fan=fan_speed)
            else:
                print("  → 쾌적 상태 유지 (변경 없음)")
                target_temp = hvac.target_temp
                fan_speed   = hvac.fan_speed

            # CSV 로그 저장
            save_log({
                'timestamp':      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'scenario':       SCENARIO_NAME,
                'out_temp':       out_temp,
                'out_humid':      out_humid,
                'out_weather':    out_weather,
                'out_wind':       out_wind,
                'in_temp':        hvac.indoor_temp,
                'in_humid':       hvac.indoor_humid,
                'people_count':   last_people_count,
                'met':            vlm_data['met'],
                'clo':            vlm_data['clo'],
                'window_open':    hvac.window_open,
                'room_size':      hvac.room_size,
                'air_vel':        air_vel,
                'pmv_val':        pmv_val,
                'comfort_status': comfort_msg,
                'target_temp':    target_temp,
                'fan_speed':      fan_speed,
            })
            print(f"💾 [Log] {LOG_FILE} 에 저장 완료\n")

        # ── 종료 ('q') ────────────────────────────────────────────────────────
        elif key == ord('q'):
            print("\n👋 프로그램을 종료합니다.")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
