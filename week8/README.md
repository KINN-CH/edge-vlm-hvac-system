# Week 8 — 워크플로우 실행 최적화 (재사용/캐싱/조건부)

> **과목:** aioss실습  
> **마감:** 2026-04-30  
> **저장소:** https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system

---

## ✅ 구현 항목 체크리스트

| 항목 | 파일 | 상태 |
|------|------|------|
| Composite Action | `.github/actions/setup-env/action.yml` | ✅ |
| Reusable Workflow | `.github/workflows/reusable-setup.yml` | ✅ |
| Matrix 확장 테스트 | `.github/workflows/ci-matrix.yml` | ✅ |
| 캐시 전후 측정 | `ci-matrix.yml` (cache-benchmark job) | ✅ |
| 선택적 배포 파이프라인 | `.github/workflows/selective-pipeline.yml` | ✅ |

---

## 1. Composite Action — 환경 설정 재사용

**파일:** `.github/actions/setup-env/action.yml`

기존에 모든 워크플로우에서 반복되던 아래 3단계를 하나의 Composite Action으로 패키지화했습니다.

```
반복 제거 전 (각 workflow마다 복사):        → Composite Action 적용 후:
─────────────────────────────────────        ────────────────────────────
- uses: actions/setup-python@v5              - uses: ./.github/actions/setup-env
  with: python-version: "3.11"                with: python-version: ${{ matrix.python-version }}
- uses: actions/cache@v4
  with: path: pip cache ...
- run: pip install ...
```

**입력/출력:**
```yaml
inputs:
  python-version: (기본값 "3.11")
outputs:
  cache-hit: (캐시 히트 여부 — true/false)
```

---

## 2. Reusable Workflow — 임포트 검증 + 단위 테스트

**파일:** `.github/workflows/reusable-setup.yml`

7개 핵심 모듈 임포트 검증 + PMV/PID 단위 테스트를 담은 Reusable Workflow입니다.  
`ci-matrix.yml`에서 `workflow_call`로 호출해 중복을 제거합니다.

```yaml
# 호출 방법
jobs:
  lint:
    uses: ./.github/workflows/reusable-setup.yml
    with:
      python-version: "3.11"
```

**검증 항목:**
- `thermal_engine`, `pid_controller`, `state_machine`, `energy_monitor`, `motion_detector`, `yolo_detector`, `sensor_interface` 임포트
- PMV 계산값 범위 검증 (-3.0 ≤ PMV ≤ 3.0)
- PID deadband 동작 검증 (|output| < 0.12 when PMV ≈ 0)

---

## 3. Matrix 확장 테스트

**파일:** `.github/workflows/ci-matrix.yml`

| Python 버전 | Ubuntu | macOS |
|-------------|--------|-------|
| 3.10 | ✅ 테스트 | ❌ 제외 (MPS 미지원) |
| 3.11 | ✅ 테스트 | ✅ 테스트 |

```yaml
strategy:
  fail-fast: false        # 한 조합 실패해도 나머지 계속 실행
  matrix:
    python-version: ["3.10", "3.11"]
    os: [ubuntu-latest, macos-latest]
    exclude:
      - os: macos-latest
        python-version: "3.10"
```

**`fail-fast: false` 적용 이유:**  
OS별 환경 차이로 인한 부분 실패를 허용해 전체 매트릭스 결과를 한번에 확인하기 위함입니다.

---

## 4. 캐싱 전후 실행 시간 비교 리포트

**측정 방법:** `ci-matrix.yml`의 `cache-benchmark` job에서 Cold/Warm run 시간 자동 측정

### 실측 결과

| 구분 | 소요 시간 | 비고 |
|------|----------|------|
| **Cold run** (캐시 없음, 첫 실행) | 약 78초 | torch + requirements 전체 다운로드 |
| **Warm run** (캐시 있음) | 약 11초 | pip 캐시에서 복원 |
| **개선율** | **85.9%** | (78 - 11) / 78 × 100 |

### 캐시 키 전략

```yaml
key: pip-${{ runner.os }}-py${{ inputs.python-version }}-${{ hashFiles('requirements_mac.txt') }}
restore-keys: |
  pip-${{ runner.os }}-py${{ inputs.python-version }}-
```

- `requirements_mac.txt` 변경 시 → 새 캐시 생성 (정확한 의존성 보장)
- 버전별 캐시 분리 → Python 3.10 / 3.11 캐시 혼용 방지
- OS별 캐시 분리 → Ubuntu / macOS 바이너리 충돌 방지

---

## 5. 선택적 배포 파이프라인

**파일:** `.github/workflows/selective-pipeline.yml`

변경된 파일에 따라 관련 테스트 Job만 실행합니다. 불필요한 전체 테스트를 생략해 CI 비용과 시간을 절약합니다.

### 파일 변경 감지 → Job 실행 매핑

```
변경 파일                              실행되는 Job
──────────────────────────────────    ─────────────────
vlm_processor.py                  →  test-vlm
yolo_detector.py                  →  test-vlm
motion_detector.py                →  test-vlm

pid_controller.py                 →  test-control
state_machine.py                  →  test-control
thermal_engine.py                 →  test-control
hvac_simulator.py                 →  test-control

energy_monitor.py                 →  test-energy
sensor_interface.py               →  test-energy
weather_service.py                →  test-energy
air_quality_service.py            →  test-energy

docs/, *.md                       →  (테스트 생략)
.github/workflows/                →  (자기 자신 변경)
```

### 조건부 실행 예시

```yaml
test-vlm:
  needs: detect-changes
  if: needs.detect-changes.outputs.vlm == 'true'
  ...
```

### 절약 효과 (시나리오별)

| 변경 내용 | 기존 (전체 실행) | 선택적 실행 |
|----------|---------------|-----------|
| README.md만 수정 | 전체 테스트 (~3분) | 0분 (스킵) |
| energy_monitor.py 수정 | 전체 테스트 (~3분) | test-energy만 (~30초) |
| 전체 모듈 수정 | 전체 테스트 (~3분) | 전체 테스트 (~3분) |

---

## 6. 워크플로우 관계도

```
push / PR (*.py 변경)
        │
        ├─► ci-matrix.yml
        │       ├─ matrix-test (py3.10/ubuntu, py3.11/ubuntu, py3.11/macos)
        │       │       └─ uses: ./.github/actions/setup-env  ← Composite Action
        │       │       └─ uses: ./.github/workflows/reusable-setup.yml  ← Reusable
        │       └─ cache-benchmark (Cold vs Warm 측정)
        │
        └─► selective-pipeline.yml
                ├─ detect-changes (변경 파일 분류)
                ├─ test-vlm      (vlm 변경 시만)
                ├─ test-control  (제어 로직 변경 시만)
                ├─ test-energy   (에너지/날씨 변경 시만)
                └─ summary       (항상 실행, 결과 집계)
```

---

## 🔗 관련 링크

- Actions 실행 결과: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system/actions
- Composite Action: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system/blob/main/.github/actions/setup-env/action.yml
- Reusable Workflow: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system/blob/main/.github/workflows/reusable-setup.yml
- Matrix CI: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system/blob/main/.github/workflows/ci-matrix.yml
- Selective Pipeline: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system/blob/main/.github/workflows/selective-pipeline.yml
