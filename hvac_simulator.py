class HVACSimulator:
    """
    [내부 공조기 및 실내 환경 시뮬레이터]
    역할: 가상 에어컨 제어 및 실내 온습도 변화 물리 시뮬레이션
    """
    def __init__(self):
        # 현재 실내 상태 (가상 센서값)
        self.indoor_temp = 27.0
        self.indoor_humid = 60.0
        
        # 에어컨 설정값
        self.is_on = False
        self.target_temp = 24.0
        self.fan_speed = 1 # 1: 약, 2: 중, 3: 강

    def set_control(self, power, target, fan):
        self.is_on = power
        self.target_temp = target
        self.fan_speed = fan

    def simulate_step(self, outdoor_temp):
        """1스텝(예: 10초) 동안의 실내 환경 변화 계산"""
        if self.is_on:
            # 냉방 로직: 설정 온도와 현재 온도의 차이에 따라 하강
            diff = self.indoor_temp - self.target_temp
            if diff > 0:
                self.indoor_temp -= (0.02 * self.fan_speed) # 풍속에 따른 냉방 가속
                self.indoor_humid -= 0.05 # 제습 효과
        else:
            # 에어컨 종료 시: 외기 온도와 서서히 평형을 이룸 (단열 성능 99% 가정)
            temp_diff = outdoor_temp - self.indoor_temp
            self.indoor_temp += temp_diff * 0.005
            
        return round(self.indoor_temp, 2), round(self.indoor_humid, 2)