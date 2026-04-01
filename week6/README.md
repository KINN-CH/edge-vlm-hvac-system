# Week 6 — 오픈소스 실습 및 Inner Source 계획

> **과목:** aioss실습  
> **마감:** 2026-04-30  
> **저장소:** https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system

---

## ✅ 필수 과제: OSS 기본 구조 완성

Public 저장소에 아래 4개 파일이 모두 갖춰져 있습니다.

| 파일 | 상태 | 설명 |
|------|------|------|
| [LICENSE](../LICENSE) | ✅ 완료 | MIT License |
| [README.md](../README.md) | ✅ 완료 | 프로젝트 전체 문서 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | ✅ 완료 | 브랜치 전략, 커밋 컨벤션, PR 프로세스 |
| [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) | ✅ 완료 | Contributor Covenant 기반 행동 강령 |

**저장소:** Public (공개)  
**라이선스:** MIT License  
**URL:** https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system

---

## 📋 선택 과제 ①: 라이선스 비교 분석

### 주요 OSS 라이선스 비교

| 항목 | MIT | Apache 2.0 | GPL v3 |
|------|-----|------------|--------|
| **복사 허용** | ✅ | ✅ | ✅ |
| **수정 허용** | ✅ | ✅ | ✅ |
| **상업적 사용** | ✅ | ✅ | ✅ (소스 공개 조건) |
| **특허 조항** | ❌ 없음 | ✅ 명시적 특허 허여 | ⚠️ 묵시적 |
| **2차 저작물 공개 의무** | ❌ 불필요 | ❌ 불필요 | ✅ 필수 (Copyleft) |
| **라이선스 고지 의무** | ✅ 고지만 | ✅ 고지 + NOTICE | ✅ 고지 + 전체 소스 |
| **기업 채택 용이성** | ⭐⭐⭐ 매우 높음 | ⭐⭐⭐ 높음 | ⭐ 낮음 (소스 공개 부담) |
| **대표 프로젝트** | React, Vue, PyTorch | Kubernetes, TensorFlow | Linux, GCC |

### 본 프로젝트 선택 기준: MIT

**선택 이유:**

1. **학부 캡스톤 프로젝트 특성상 최대 개방성 확보**  
   MIT는 조건이 가장 단순하여 외부 기여자나 기업이 코드를 가져다 쓰는 데 가장 낮은 진입 장벽을 제공합니다.

2. **하드웨어 제품 연계 가능성 고려**  
   향후 Jetson 기반 상용화 시 라이선스 컴플라이언스 부담이 가장 적습니다. Apache 2.0도 고려했으나, 특허 리스크가 낮은 학술 프로젝트 단계에서는 MIT의 단순함이 더 적합합니다.

3. **의존 라이브러리 호환성**  
   PyTorch (BSD), ultralytics YOLOv8 (AGPL → 주의 필요), transformers (Apache 2.0) 등 주요 의존 라이브러리와의 라이선스 충돌이 없습니다.

> ⚠️ **주의:** ultralytics YOLOv8는 AGPL-3.0 라이선스입니다.  
> 상업적 제품으로 배포 시 별도 상용 라이선스 구매가 필요합니다.  
> 현재 프로젝트는 학술 연구 목적으로 AGPL 조건 범위 내에서 사용합니다.

---

## 📋 선택 과제 ②: Inner Source 도입 로드맵

### Inner Source란?

오픈소스 개발 방식(PR, 코드 리뷰, 이슈 트래킹)을 조직 내부 프로젝트에 적용하는 방법론입니다.  
코드가 외부에 공개되지 않지만, 내부 구성원 누구나 기여할 수 있는 구조를 만듭니다.

### 본 프로젝트에서 이미 적용된 Inner Source 요소

| 요소 | 적용 현황 |
|------|----------|
| GitHub Flow (브랜치 전략) | ✅ `feature/`, `fix/`, `docs/` 브랜치 분리 운영 |
| Protected main 브랜치 | ✅ 직접 push 차단, PR + 리뷰 필수 |
| PR 템플릿 | ✅ `.github/pull_request_template.md` |
| 이슈 템플릿 | ✅ Bug Report / Feature Request |
| Conventional Commits | ✅ `feat:`, `fix:`, `docs:` 등 |
| SLA 모니터링 | ✅ GitHub Actions `sla-check.yml` — 미응답 이슈 자동 감지 |
| DORA 메트릭 수집 | ✅ `metrics.yml` — 배포 빈도, 리드타임 추적 |
| 자동 응답 워크플로우 | ✅ `auto-response.yml` |

### Inner Source 확장 로드맵 (3단계)

#### Phase 1 — 기반 완성 (현재 ~ 8주차)
- [x] OSS 4대 파일 완비 (LICENSE, README, CONTRIBUTING, CODE_OF_CONDUCT)
- [x] Protected 브랜치 + PR 리뷰 프로세스 정착
- [x] GitHub Actions CI 파이프라인 구축
- [ ] 위키(Wiki) 기술 문서 보강 — Getting Started, API 명세

#### Phase 2 — 협업 고도화 (9~12주차)
- [ ] 이슈 라벨 체계화 (`good-first-issue`, `help-wanted`, `priority:high`)
- [ ] PR 리뷰 SLA 강화 — 48시간 내 첫 리뷰 의무화
- [ ] 코드 오너십 파일 (`.github/CODEOWNERS`) — 모듈별 담당자 지정
  ```
  # 예시
  vlm_processor.py   @junkyeong
  thermal_engine.py  @minseo
  energy_monitor.py  @yoonchan
  ```
- [ ] 자동화 테스트 추가 — PMV 계산, PID 출력값 단위 테스트

#### Phase 3 — 지식 공유 체계 (13~16주차)
- [ ] ADR(Architecture Decision Record) 문서화 지속  
  현재: `docs/adr/0001-use-vlm-for-context-awareness.md`, `0002-use-yolo-for-people-counting.md`
- [ ] 알고리즘 명세서 유지 관리 (`docs/algorithm_spec.txt`)
- [ ] 발표자료 및 논문 초안 저장소에 포함
- [ ] Jetson 배포 가이드 문서화

### Inner Source가 이 프로젝트에 가져온 효과

```
Before (단순 공유 폴더 방식)     After (Inner Source 적용)
─────────────────────────        ─────────────────────────
코드 충돌 빈번                    브랜치 전략으로 충돌 최소화
변경 이력 불분명                  git log로 누가 왜 바꿨는지 추적
"내 코드"만 관리                 PR 리뷰로 팀 전체 코드 품질 관리
문서 없음                        README, ADR, 알고리즘 명세 자동 갱신
```

---

## 🔗 관련 링크

- 저장소: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system
- LICENSE: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system/blob/main/LICENSE
- CONTRIBUTING: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system/blob/main/CONTRIBUTING.md
- CODE_OF_CONDUCT: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system/blob/main/CODE_OF_CONDUCT.md
- ADR 문서: https://github.com/KAJ-EdgeVLM-HVAC-Project/edge-vlm-hvac-system/tree/main/docs/adr
