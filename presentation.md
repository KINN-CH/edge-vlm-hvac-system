---
marp: true
theme: default
paginate: true
style: |
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');

  * { box-sizing: border-box; }

  section {
    font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    background: #f8f9fc;
    color: #1a1a2e;
    padding: 36px 56px;
    font-size: 15px;
  }

  h1 { font-size: 1.9em; color: #111838; line-height: 1.25; margin-bottom: 6px; }
  h2 { font-size: 1.45em; color: #111838; border-bottom: 3px solid #3a7bd5;
       padding-bottom: 8px; margin-bottom: 20px; }
  h3 { font-size: 1.05em; color: #3a7bd5; margin: 0 0 6px 0; }
  h4 { font-size: 0.9em; color: #555; margin: 0 0 4px 0; }
  strong { color: #c0392b; }
  em { color: #2980b9; font-style: normal; font-weight: bold; }
  code { background: #eef2f7; border-radius: 4px; padding: 1px 6px;
         font-size: 0.88em; color: #2c3e50; font-family: 'Fira Code', monospace; }
  pre {
    background: #1e2433;
    color: #e8eaf0;
    border-radius: 8px;
    padding: 14px 18px;
    font-size: 0.78em;
    margin: 8px 0;
    line-height: 1.55;
  }
  pre code { background: none; color: inherit; padding: 0; }

  .two { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }

  .card {
    background: #fff;
    border-radius: 10px;
    border: 1px solid #dde3ef;
    padding: 16px 18px;
  }
  .card-blue  { border-left: 4px solid #3a7bd5; }
  .card-red   { border-left: 4px solid #c0392b; background: #fdf5f5; }
  .card-green { border-left: 4px solid #27ae60; background: #f3fdf6; }
  .card-orange{ border-left: 4px solid #e67e22; background: #fdf9f3; }
  .card-purple{ border-left: 4px solid #8e44ad; background: #faf5ff; }
  .card-dark  { background: #1e2433; color: #e8eaf0; border: none; }

  .pill {
    display: inline-block; padding: 3px 12px; border-radius: 20px;
    font-size: 0.78em; font-weight: bold; margin: 3px 2px;
  }
  .pill-blue   { background:#dbeafe; color:#1d4ed8; }
  .pill-green  { background:#d1fae5; color:#065f46; }
  .pill-red    { background:#fee2e2; color:#991b1b; }
  .pill-orange { background:#ffedd5; color:#9a3412; }
  .pill-teal   { background:#d1f0eb; color:#0f766e; }
  .pill-gray   { background:#f1f5f9; color:#475569; }

  .badge {
    display: inline-block; background: #3a7bd5; color: #fff;
    border-radius: 6px; padding: 1px 8px; font-size: 0.75em;
    font-weight: bold; margin-right: 6px;
  }

  table { width:100%; border-collapse:collapse; font-size:0.85em; }
  th { background:#111838; color:#fff; padding:7px 12px; text-align:left; }
  td { border-bottom:1px solid #e2e8f0; padding:7px 12px; }
  tr:nth-child(even) td { background:#f8f9fc; }

  .note { font-size:0.75em; color:#94a3b8; margin-top:6px; }
  .center { text-align:center; }
  .arrow { color:#3a7bd5; font-size:1.3em; font-weight:bold; }
  .num { font-size:2em; font-weight:900; color:#3a7bd5; line-height:1; }

  section.title {
    background: linear-gradient(140deg, #0f1629 0%, #1a3a6e 60%, #0f2d55 100%);
    color: #fff;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    padding: 56px 72px;
  }
  section.title h1 { color:#fff; font-size:2em; line-height:1.3; }
  section.title .en { color:#7fa8d8; font-size:0.85em; margin-top:6px; }
  section.title .team { color:#a8c4e0; font-size:0.82em; margin-top:28px; line-height:1.9; }
  section.title .tag { background:rgba(255,255,255,0.12); border-radius:6px;
                       padding:3px 12px; font-size:0.8em; color:#c8ddf0;
                       margin-right:8px; }

  section.closing {
    background: linear-gradient(140deg, #0f1629 0%, #1a3a6e 100%);
    color: #fff;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
  }
  section.closing h2 { color:#fff; border-bottom:2px solid rgba(255,255,255,0.3); }
  section.closing td, section.closing th { color:#fff; }
  section.closing th { background:rgba(255,255,255,0.15); }
  section.closing tr:nth-child(even) td { background:rgba(255,255,255,0.06); }
  section.closing td { border-bottom:1px solid rgba(255,255,255,0.15); }
---

<!-- _class: title -->

# 엣지 VLM·IoT 융합 기반<br>완전 오프라인 지능형 공조 제어 시스템

<p class="en">Edge VLM-Driven Fully-Offline Intelligent HVAC Control System</p>

<div class="team">
<span class="tag">VLM / AI 추론</span> 김준경 &nbsp;·&nbsp;
<span class="tag">PM / 시스템 통합</span> 김철호<br>
<span class="tag">열환경 모델링</span> 김민서 &nbsp;·&nbsp;
<span class="tag">데이터 분석</span> 정윤찬
</div>

---

<!-- 발표자 노트: 30초 — "기존 에어컨은 온도만 봅니다. 사람이 몇 명인지, 무슨 옷을 입었는지, 점심 나갔는지를 모릅니다. 오늘은 카메라 하나로 그 맥락을 읽고 스스로 학습하는 시스템을 소개합니다." -->

## 문제 — 기존 공조 시스템의 구조적 한계

<div class="two">
<div>

<div class="card card-red">

### 온도 센서만 보는 에어컨
- 착의량·활동량 **완전 무시**
- 사람이 추워도 설정 온도면 정지
- 퇴근·점심 외출 감지 불가 → **빈 방 냉난방 지속**
- 재실자 개인 체감 차이 반영 불가

</div>

<div class="card card-red" style="margin-top:14px;">

### 클라우드 AI 기반 솔루션의 딜레마
- 카메라 이미지 외부 전송 → **프라이버시 침해**
- 네트워크 지연 → 실시간 제어 불가
- 보안 구역(군·연구소) **설치 불가**

</div>
</div>
<div>

<div class="card card-blue">

### 핵심 질문

> *"카메라 한 대와 엣지 보드 하나만으로,*
> *사람의 체감 쾌적도를 예측하고*
> *공조기를 자율 제어할 수 있는가?"*

</div>

<div class="card card-green" style="margin-top:14px;">

### 제약 조건
- 완전 오프라인 — 클라우드 **Zero**
- NVIDIA Jetson Orin Nano Super (8GB)
- 기존 공조기 **레트로핏** (교체 없이 부착)
- 실시간 제어 (30초 분석 주기)

</div>
</div>
</div>

---

<!-- 발표자 노트: 40초 — "세 가지 AI 모델이 역할을 나눠 맡습니다. YOLOv8n이 빠르게 인원을 세고, VLM이 옷차림과 상황을 파악하고, MotionDetector가 매 프레임 움직임을 잡습니다. 이 데이터들을 상태 머신이 통합해 PMV를 계산하고 PID가 제어합니다." -->

## 시스템 개요 — 3-Layer 인지·판단·제어 파이프라인

<div class="card card-dark" style="padding:18px 22px; margin-bottom:14px;">

```
시작  ──→  환경 선택 GUI (사무실 / 가정 / 체육시설 / 부대시설)
               └─ EnvProfile 로드: CLO·MET 기준값, 점심·퇴근 감지 여부

Layer 1  인지 (Perception)
  ├─ YOLOv8n        매 90프레임(≈3초)   인원 수 감지
  ├─ Qwen2-VL-2B    매 30초 백그라운드  CLO·MET·활동·외투·열원 분석
  └─ MotionDetector 매 프레임           프레임 차분 → motion_score

Layer 2  상황 판단 (Context)
  ├─ StateManager   5단계 상태 전이      EMPTY/ARRIVAL/STEADY/LUNCH_BREAK/PRE_DEPARTURE
  └─ ThermalEngine  ISO 7730 PMV 계산   온습도 + CLO + MET → 열쾌적 지수

Layer 3  제어 (Control)
  ├─ PIDController  PMV 오차 기반        팬 속도·목표 온도 연속 조정
  └─ HVACSimulator  물리 공조 모델       Jetson 이전 시 실제 공조기 연결
```

</div>

<div class="three">
<div class="card center"><div class="num">3초</div>YOLO 인원 감지 주기</div>
<div class="card center"><div class="num">30초</div>VLM 맥락 분석 주기</div>
<div class="card center"><div class="num">8GB</div>Jetson UMA — 완전 오프라인</div>
</div>

---

<!-- 발표자 노트: 45초 — "VLM과 YOLO의 역할 분리가 핵심입니다. YOLO는 빠르게 사람 수만 세고, VLM은 느리지만 옷차림·활동·상황까지 읽습니다. MotionDetector가 30초 VLM 공백을 채웁니다. 각 모델을 적재적소에 배치해 Jetson 8GB에서도 실시간 동작이 가능합니다." -->

## 알고리즘 ① — VLM + YOLO + MotionDetector 역할 분리

<div class="two">
<div>

<div class="card card-blue">

### YOLOv8n — 빠른 인원 카운팅

```python
# 매 90프레임마다 실행
if frame_count % 90 == 0:
    people = yolo.count_people(frame)
    # 감지 실패 시 -1 반환 → 이전값 유지
```

- `imgsz=320` (CPU) / `640+TRT FP16` (Jetson)
- 인원 수 **카운팅만** 담당 — 경량 고속

</div>

<div class="card card-orange" style="margin-top:14px;">

### MotionDetector — VLM 공백 보완

```python
# 매 프레임 실행
diff = cv2.absdiff(prev_gray, curr_gray)
motion_score = diff.mean()  # 0.0 ~ 1.0

# MET 보정
met = base_met + motion_score * 0.8
```

- VLM 추론 30초 공백을 **매 프레임** 보정
- 추가 하드웨어 불필요

</div>
</div>
<div>

<div class="card card-purple">

### Qwen2-VL-2B — 정성적 맥락 인지

```python
# 백그라운드 스레드, 30초 주기
prompt = """Analyze the room. Return JSON:
{
  "people_count": int,
  "clo": float,        # 착의량 0.3~1.5
  "met": float,        # 활동량 0.8~4.0
  "activity": str,     # sitting/standing/walking
  "outerwear": str,    # yes/no
  "heat_source": str   # none/computer/cooking
}"""
result = vlm.generate(frame, prompt)
```

- **완전 오프라인** — float16(MPS/CUDA) / float32(CPU)
- MPS → CUDA → CPU 자동 선택
- VLM 실패 시 → **계절별 CLO fallback** 자동 적용

</div>
</div>
</div>

---

<!-- 발표자 노트: 45초 — "PMV는 ISO 7730 국제 표준입니다. -3이 매우 춥고 +3이 매우 덥고 0이 최적입니다. 온도뿐 아니라 옷차림, 활동량, 복사온도까지 종합해서 계산합니다. 이 PMV 오차를 PID 제어기에 넣어 팬 속도와 목표 온도를 연속으로 조정합니다." -->

## 알고리즘 ② — ISO 7730 PMV 기반 PID 정밀 제어

<div class="two">
<div>

<div class="card card-blue">

### PMV 계산 (ISO 7730)

```python
# 6가지 변수로 열쾌적 지수 계산
pmv = thermal_engine.compute(
    ta  = indoor_temp,    # 공기 온도 (°C)
    tr  = radiant_temp,   # 복사 온도 (열원 보정)
    rh  = indoor_humid,   # 상대 습도 (%)
    va  = fan_speed/10,   # 기류 속도 (m/s)
    clo = eff_clo,        # 착의량 (VLM or fallback)
    met = eff_met         # 활동량 (VLM + MotionDetector)
)
# -3(매우 춥다) ~ 0(쾌적) ~ +3(매우 덥다)

# 사용자 선호도 반영
adjusted_pmv = pmv - pref_state['value']
```

</div>
</div>
<div>

<div class="card card-green">

### PID 제어기

```python
# PMV 오차 → 팬 속도·목표 온도 계산
error = 0.0 - adjusted_pmv  # 목표: PMV=0

# PID 항 계산
P = kp * error             # 0.8  현재 오차 즉각 반응
I += ki * error * dt       # 0.05 누적 오차 보정
D = kd * (error - prev)    # 0.3  급변 억제

output = P + I + D
# deadband=0.12: 미세 진동 방지
```

</div>

<div class="card card-orange" style="margin-top:14px;">

### 추워요 / 더워요 버튼 → PMV 선호도

```python
# 마우스 클릭 콜백
if clicked == 'cold':   # 추워요
    pref += 0.5  # PMV 기준 올려 더 따뜻하게
elif clicked == 'hot':  # 더워요
    pref -= 0.5  # PMV 기준 내려 더 시원하게
```

</div>
</div>
</div>

---

<!-- 발표자 노트: 50초 — "상태 머신이 이 시스템의 심장입니다. 5가지 상태가 있고 각각 제어 전략이 다릅니다. LUNCH_BREAK는 점심 시간대 인원 0을 감지해 AC를 끄고, 복귀 시 ARRIVAL로 보내 집중 냉난방을 재개합니다. 여름에 1시간 꺼놓으면 많이 더워지니까요. PRE_DEPARTURE는 사람이 있어도 퇴근 준비 맥락을 점수화해서 선제 절전합니다." -->

## 알고리즘 ③ — 5단계 맥락 인지 상태 머신

<div style="display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:16px; flex-wrap:wrap;">
<span class="pill pill-gray">EMPTY<br><small>공실·AC OFF</small></span>
<span class="arrow">→</span>
<span class="pill pill-orange">ARRIVAL<br><small>집중 냉난방 60s</small></span>
<span class="arrow">→</span>
<span class="pill pill-green">STEADY<br><small>PMV PID 제어</small></span>
<span class="arrow">⇄</span>
<span class="pill pill-teal">LUNCH_BREAK<br><small>점심 외출·AC OFF</small></span>
<span style="margin:0 4px; color:#888;">|</span>
<span class="pill pill-red">PRE_DEPARTURE<br><small>선제 절전</small></span>
</div>

<div class="two">
<div>

<div class="card card-blue">

### 상태 전이 핵심 로직

```python
# STEADY → LUNCH_BREAK
if (people == 0 and in_lunch_time
        and state in (STEADY, ARRIVAL)):
    transition(LUNCH_BREAK)  # AC OFF

# LUNCH_BREAK → ARRIVAL  ← 핵심
if people > 0:
    transition(ARRIVAL)  # 집중 냉난방 재개
    # NOT STEADY: 1시간 공실로 온도 변화 큼

# 90분 초과 → 진짜 EMPTY
if now - lunch_since >= 90 * 60:
    transition(EMPTY)
```

</div>
</div>
<div>

<div class="card card-red">

### 퇴근 맥락 점수 (0~75점)

```python
def _compute_departure_score(...):
    score = 0
    if people < prev_people: score += 30  # 인원 감소
    if outerwear == 'yes':   score += 25  # 외투 착용
    if activity == 'standing': score += 10 # 기립 자세
    if work_end-1 <= hour <= work_end+1:
                             score += 10  # 퇴근 시간대
    return min(score, 75)

# ≥ 55점 → PRE_DEPARTURE (선제 절전)
# < 30점 → STEADY 복귀  (오탐 복구)
```

</div>
</div>
</div>

---

<!-- 발표자 노트: 35초 — "환경별로 파라미터가 다릅니다. 헬스장은 겨울에도 반팔을 입으니 CLO를 고정하고, 가정은 점심·퇴근 개념이 없습니다. 시작 시 카드를 선택하면 모든 파라미터가 자동으로 세팅됩니다." -->

## 알고리즘 ④ — 환경 프로파일 + 계절별 CLO 자동 설정

<div class="two">
<div>

**시작 화면 — 환경 선택 GUI** (`startup_screen.py`)

<div class="card">

| 환경 | 점심 | 퇴근 | MET | CLO 여름/봄가을/겨울 |
|------|:----:|:----:|:---:|:------------------:|
| 사무실 | ✓ | ✓ | 1.2 | 0.6 / 0.9 / 1.2 |
| 가정 | — | — | 1.0 | 0.5 / 0.8 / 1.0 |
| 체육시설 | — | — | 2.5 | 0.4 / 0.4 / 0.5 |
| 부대시설 | ✓ | ✓ | 1.5 | 0.7 / 1.0 / 1.3 |

</div>

<div class="note">체육시설: 계절 무관 CLO 고정 — 겨울에도 운동복 착용</div>

</div>
<div>

**계절별 CLO Fallback** — VLM 미가동 시 자동 적용

```python
def _seasonal_clo(profile: EnvProfile) -> float:
    m = datetime.now().month
    if 6 <= m <= 8:            # 여름
        return profile.clo_summer
    if m in (3,4,5, 9,10,11): # 봄·가을
        return profile.clo_spring_fall
    return profile.clo_winter  # 겨울
```

<div class="card card-green" style="margin-top:12px;">

**우선순위:**
1. VLM 분석 성공 → VLM 값 사용
2. VLM 실패 / 미가동 → 계절×환경 fallback
3. → ThermalEngine PMV 계산 진행

</div>
</div>
</div>

---

<!-- 발표자 노트: 30초 — "화면은 두 개로 나뉩니다. 운영자 창은 카메라와 모든 AI 수치를 보여주고, 사용자 창은 삼성 시스템 에어컨 벽면 리모컨처럼 만들었습니다. 추워요·더워요 버튼 클릭으로 PMV 선호도가 실시간 반영됩니다." -->

## 구현 — 이중 창 UI 아키텍처

<div class="two">
<div>

<div class="card card-blue">

### 운영자 창 (Operator Window)
`dashboard.py`

- 실시간 카메라 영상
- VLM 분석 결과 (CLO / MET / 활동)
- 상태 머신 현황 + 퇴근 점수
- 실내외 온습도 · PM2.5
- PID 수치 · 팬 속도 · 목표 온도

</div>

<div class="card card-green" style="margin-top:14px;">

### 창 배치 및 마우스 콜백

```python
# 첫 프레임에서 창 위치 + 콜백 등록
if frame_count == 1:
    cv2.moveWindow("HVAC Operator", 0, 0)
    cv2.moveWindow("HVAC User",
                   combined.shape[1] + 10, 0)
    cv2.setMouseCallback(
        "HVAC User", _user_mouse_cb, pref_state)
```

</div>
</div>
<div>

<div class="card card-purple">

### 사용자 창 (User Window)
`user_display.py` — 삼성 AC 리모컨 스타일

```python
# 모듈 레벨 버튼 영역 등록
BUTTON_REGIONS: dict = {}

def get_clicked(x, y):
    for name, (x1,y1,x2,y2) \
            in BUTTON_REGIONS.items():
        if x1<=x<=x2 and y1<=y<=y2:
            return name
    return None
```

**표시 항목:**
- 현재 실내 온도 (대형)
- AC 상태 (냉방 / 난방 / OFF)
- **추워요 · 더워요** 클릭 버튼
- 공기질 5단계 · 창문 권고

</div>
</div>
</div>

---

<!-- 발표자 노트: 30초 — "전체 데이터가 어떻게 흐르는지 한눈에 보여드립니다." -->

## 전체 데이터 흐름

<div class="card card-dark" style="padding:18px 24px;">

```
[시작]
  startup_screen.py  →  환경 선택 (사무실/가정/체육시설/부대시설)
  env_profiles.py    →  파라미터 로드 (CLO·MET·점심·퇴근 플래그)

[매 프레임]
  MotionDetector     →  motion_score  →  MET 실시간 보정

[매 3초]
  YOLOv8n            →  people_count

[매 30초]
  Qwen2-VL-2B        →  clo, met, activity, outerwear, heat_source
  (실패 시)          →  _seasonal_clo(env_profile)  ← fallback

[매 제어 루프]
  StateManager       →  상태 전이 (EMPTY/ARRIVAL/STEADY/LUNCH_BREAK/PRE_DEPARTURE)
  ThermalEngine      →  pmv = ISO7730(ta, tr, rh, va, clo, met)
  adjusted_pmv       =  pmv - pref_state['value']
  PIDController      →  fan_speed, target_temp = PID(adjusted_pmv)
  HVACSimulator      →  공조기 제어 명령

[출력]
  Operator Window    ←  카메라 + 대시보드
  User Window        ←  AC 리모컨 UI (추워요·더워요 버튼)
  CSV Logger         ←  hvac_system_performance.csv
```

</div>

---

<!-- 발표자 노트: 40초 — "마지막으로 향후 계획입니다. 지금까지는 사전학습된 외부 모델을 가져다 쓰는 방식이었다면, 앞으로는 우리가 직접 설계하고 학습한 3개의 경량 ML 모델을 추가합니다." -->

## 향후 계획 — 자체 ML 모듈 3개 개발

<div class="three">

<div class="card card-blue">

### ① PMV 선호도 MLP
*온라인 학습*

```python
# 버튼 클릭 시 즉시 학습
# 입력: PMV, 온도, 습도, 시간, 계절
# 출력: 선호도 오프셋 예측
# 파라미터: ~700개 (< 10KB)
# 학습: 클릭마다 1 step SGD
```

- 실사용 데이터로 **즉시 시작**
- 사용할수록 개인 맞춤화

</div>

<div class="card card-green">

### ② 재실 예측 LSTM
*Sim-to-Real*

```python
# 입력: 과거 48h 인원 패턴
#        + 시간·요일 sin/cos
# 출력: 30분 뒤 재실 확률
# 파라미터: ~5,000개 (< 100KB)
# 사전학습: 시나리오 데이터
# 이후: 실데이터 자동 fine-tune
```

- 도착 **전** 선제 냉난방
- 새벽 자동 재학습

</div>

<div class="card card-red">

### ③ 퇴근 맥락 분류기
*룰베이스 대체*

```python
# 입력: 인원변화, 외투, 활동,
#        motion_score, 시간대
# 출력: 퇴근 확률 (0~1)
# 현재 고정 가중치 → 학습된 값
# 레이블: 상태 로그 자동 생성
```

- 고정 가중치의 한계 극복
- 환경별 패턴 자동 학습

</div>

</div>

<div class="card" style="margin-top:16px; padding:12px 18px;">

**공통 전략:** <span class="pill pill-blue">Sim-to-Real</span> 시나리오 사전학습 → 배포 즉시 동작 &nbsp;|&nbsp; <span class="pill pill-green">Continual Learning</span> 매일 새벽 3시 Jetson 자체 재학습 &nbsp;|&nbsp; <span class="pill pill-gray">ON/OFF + Reset</span> 테스트 환경 독립성 보장

</div>

---

<!-- _class: closing -->

## 정리

<br>

|  | 기존 시스템 | **본 시스템** |
|--|:--:|:--:|
| 인지 | 온도 센서 | VLM + YOLO + MotionDetector |
| 제어 | if/else 임계값 | ISO 7730 PMV + PID |
| 맥락 | 없음 | 5단계 상태 머신 (점심·퇴근·계절) |
| 개인화 | 없음 | 추워요·더워요 + MLP 학습 (예정) |
| 예측 | 사후 반응 | LSTM 선제 대응 (예정) |
| 프라이버시 | 클라우드 전송 | **완전 오프라인** |
| 도입 | 전체 교체 | **레트로핏** |

<br>

> *"설치하면 바로 동작하고, 쓸수록 똑똑해지는 자가 진화형 엣지 AI"*
