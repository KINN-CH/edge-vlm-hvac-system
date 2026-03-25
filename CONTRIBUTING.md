# Contributing Guide

## 🌿 브랜치 전략 (GitHub Flow)

- `main` 브랜치는 항상 배포 가능한 상태 유지
- 새 작업은 항상 `main`에서 브랜치 생성
- 브랜치 네이밍 규칙:
  - `feature/작업내용`
  - `fix/버그내용`
  - `docs/문서내용`
  - `refactor/리팩토링내용`

## 📝 커밋 메시지 컨벤션 (Conventional Commits)
```
<type>(<scope>): <subject>
```

| Type | 설명 |
|------|------|
| `feat` | 새로운 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `refactor` | 코드 리팩토링 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드/설정 변경 |

## 🔍 코드 리뷰 가이드

### 리뷰 태그 시스템
- `[MUST]` 반드시 수정 필요 (로직 오류, 보안 취약점)
- `[SHOULD]` 수정 강력 권장
- `[NITS]` 사소한 제안 (수정 선택)
- `[QUESTION]` 코드 의도 확인
- `[PRAISE]` 잘 작성된 코드 칭찬

### 리뷰어 체크리스트
- [ ] 코드가 요구사항을 충족하는가?
- [ ] 테스트가 충분한가?
- [ ] 보안 취약점은 없는가?
- [ ] 코드가 읽기 쉬운가?
- [ ] 문서화가 충분한가?

## 🚀 PR 프로세스

1. `main`에서 feature 브랜치 생성
2. 작업 후 Conventional Commits 규칙으로 커밋
3. PR 생성 (템플릿 작성)
4. 리뷰어 지정
5. CI 통과 확인
6. 승인 후 Merge