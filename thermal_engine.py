import math

class ThermalEngine:
    """
    [열쾌적성 판단 엔진]
    출처: ISO 7730:2005 - Ergonomics of the thermal environment
    ASHRAE Standard 55 - Thermal Environmental Conditions for Human Occupancy
    설명: PMV(Predicted Mean Vote) 모델을 기반으로 사용자의 온열감을 예측합니다.
    """

    def __init__(self):
        # 기본 물리 상수 (ASHRAE 표준 기준)
        self.STEFAN_BOLTZMANN = 5.67e-8  # W/(m2*K4)

    def calculate_pmv(self, ta, tr, rh, vel, met, clo):
        """
        PMV 지수 계산 함수
        """
        # 1. 기초 데이터 변환
        pa = (rh / 100) * 10 * math.exp(16.6536 - 4030.183 / (ta + 235)) # 수증기 분압 (kPa)
        icl = 0.155 * clo  # 착의 열저항 (m2*K/W)
        m = met * 58.15    # 대사율 (W/m2)
        w = 0              # 외부 작업 (보통 0)
        mw = m - w         # 인체 발생 열량
        
        # 2. 착의 표면적 계수 계산
        if icl <= 0.078:
            fcl = 1.00 + 1.290 * icl
        else:
            fcl = 1.05 + 0.645 * icl

        # 3. 착의 표면 온도(tcl) 반복 계산
        tcl = ta + (35.5 - ta) / (3.5 * (6.45 * icl + 0.1))
        p1 = icl * fcl
        p2 = p1 * 3.96
        p3 = p1 * 100
        p4 = p1 * (ta + 273)
        p5 = 308.7 - 0.028 * mw + p2 * ((tr + 273) / 100) ** 4
        
        # 수렴을 위한 반복 계산
        hc = 0 # 초기화
        for _ in range(150):
            hc = 2.38 * abs(tcl - ta) ** 0.25
            if 12.1 * math.sqrt(vel) > hc:
                hc = 12.1 * math.sqrt(vel)
            
            tcl_new = (p5 + p3 * hc - p2 * ((tcl + 273) / 100) ** 4) / (1 + p1 * hc)
            
            # --- [안정성 강화] tcl 값이 발산하는 것을 방지 ---
            if not (-50 < tcl_new < 150):
                # print("⚠️ [Thermal Engine] tcl 수렴 실패! 계산을 중단합니다.")
                break # 범위를 벗어나면 루프 중단

            if abs(tcl - tcl_new) < 0.0001:
                break
            tcl = tcl_new

        # 4. 열부하(L) 계산
        hl_skin = 3.05 * 0.001 * (5733 - 6.99 * mw - pa)
        hl_sweat = 0.42 * (mw - 58.15) if mw > 58.15 else 0
        hl_res_lat = 1.7 * 0.00001 * m * (5867 - pa)
        hl_res_dry = 0.0014 * m * (34 - ta)
        hl_rad = 3.96 * fcl * (((tcl + 273) / 100) ** 4 - ((tr + 273) / 100) ** 4)
        hl_conv = fcl * hc * (tcl - ta)
        
        ts = 0.303 * math.exp(-0.036 * m) + 0.028
        l = mw - hl_skin - hl_sweat - hl_res_lat - hl_res_dry - hl_rad - hl_conv
        
        pmv = ts * l
        
        # --- [안정성 강화] ASHRAE 표준 범위(-3.0 ~ 3.0) 준수 ---
        clipped_pmv = max(-3.0, min(3.0, pmv))
        
        # --- [데이터 타입 확인] 항상 float, 소수점 둘째 자리까지 반환 ---
        return round(clipped_pmv, 2)

    def get_comfort_status(self, pmv):
        """PMV 수치에 따른 상태 텍스트 반환"""
        if pmv > 2.5: return "매우 더움 (Hot)"
        elif pmv > 1.5: return "더움 (Warm)"
        elif pmv > 0.5: return "조금 더움 (Slightly Warm)"
        elif pmv > -0.5: return "쾌적 (Neutral)"
        elif pmv > -1.5: return "조금 추움 (Slightly Cool)"
        elif pmv > -2.5: return "추움 (Cool)"
        else: return "매우 추움 (Cold)"