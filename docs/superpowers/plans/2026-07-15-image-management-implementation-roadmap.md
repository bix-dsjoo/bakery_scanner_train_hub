# 이미지 관리 MVP 구현 로드맵

- 상태: 실행 대기
- 작성일: 2026-07-15
- 선행 문서: [제품 설계](../specs/2026-07-15-bakery-image-management-design.md), [기술 설계](../specs/2026-07-15-image-management-technical-design.md), [UI 디자인](../specs/2026-07-15-image-management-ui-design.md)

## 목표

승인된 이미지 관리 MVP를 한 번에 구현하지 않고, 각 단계가 실제로 실행되고 자동 검증되는 수직 기능 단위로 나눈다. 모델 학습·데이터셋 내보내기·사용자 인증은 이 로드맵에 포함하지 않는다.

## 실행 순서

| 순서 | 계획 | 독립적으로 검증되는 결과 |
|---:|---|---|
| 1 | [애플리케이션 기반과 카탈로그](2026-07-15-image-management-foundation-catalog.md) | Windows 개발 환경에서 API와 UI가 실행되고 브랜드·상품을 관리한다. |
| 2 | [이미지 업로드와 작업함](2026-07-15-image-management-upload-library.md) | 상품 사진과 트레이 사진을 안전하게 등록·검색·삭제한다. |
| 3 | [라벨링 편집기](2026-07-15-image-management-labeling-editor.md) | 트레이 사진에 박스를 그리고 상품을 지정해 자동 저장·완료한다. |
| 4 | [운영과 출시 검증](2026-07-15-image-management-operations-release.md) | `start.ps1`, 용량·복구·접근성·사내망 검증을 통과한다. |

각 단계는 앞 단계가 기본 브랜치에 병합된 뒤 새 일반 브랜치에서 시작한다. 격리 작업 트리는 사용하지 않는다.

## 단계 간 고정 계약

### 런타임

- Node.js 24 LTS, npm, React 19.2, Vite 8, TypeScript, Tailwind CSS 4
- Python 3.13, uv, FastAPI, SQLAlchemy 2.0, Alembic, SQLite WAL
- 운영 프로세스는 Uvicorn worker 한 개이며 FastAPI가 빌드된 SPA를 함께 제공한다.
- 모든 업무 API는 `/api/v1` 아래에 둔다.

### 디렉터리

```text
backend/app/api/             HTTP 스키마와 라우팅
backend/app/application/     사용 사례
backend/app/domain/          업무 규칙과 순수 검증
backend/app/infrastructure/  SQLite·파일·이미지 구현
backend/tests/               pytest
frontend/src/app/            라우팅과 브랜드 맥락
frontend/src/components/ui/  저장소 소유 shadcn 컴포넌트
frontend/src/features/       기능별 API·상태·UI
frontend/src/pages/          페이지 조합
frontend/tests/              Vitest·Playwright
```

### 공통 API 오류

```json
{
  "code": "PRODUCT_CODE_DUPLICATE",
  "message": "같은 브랜드에 이미 등록된 상품 코드예요.",
  "action": "다른 상품 코드를 입력해 주세요.",
  "field_errors": {"code": "이미 사용 중인 코드예요."}
}
```

`code`와 `message`는 필수, `action`과 `field_errors`는 해당할 때만 포함한다. 존재하지 않는 자원은 404, 중복과 revision 충돌은 409다.

### 품질 게이트

각 계획의 마지막에는 최소한 다음 명령이 모두 성공해야 한다.

```powershell
uv run pytest
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
```

Playwright가 도입된 단계부터는 다음도 실행한다.

```powershell
npm --prefix frontend run test:e2e
```

## 전체 완료 조건

- 브랜드 생성부터 상품 사진·트레이 사진 등록, 박스 라벨링, 완료 후 다음 사진 이동까지 자동 테스트가 통과한다.
- 10만 건 목록 첫 페이지 조회가 기준 PC에서 2초 이내이고 100장 등록의 동시 요청이 2개를 넘지 않는다.
- `start.ps1` 하나로 빌드·마이그레이션·단일 worker 서버 시작이 가능하다.
- 같은 PC와 사내망의 다른 PC에서 접속되고 재시작 후 데이터가 유지된다.
- 저장 실패, revision 충돌, 디스크 부족, 중복 파일에서 원인과 다음 행동을 한국어로 표시한다.
- README와 AGENTS.md가 실제 실행 방식과 데이터 유실 위험을 설명한다.

## 설계 요구사항 추적

| 설계 범위 | 구현 계획 |
|---|---|
| 브랜드·상품 고유성, 비활성화, 현재 브랜드 맥락 | 기반과 카탈로그 Task 2~6 |
| BIXOLON 토큰, shadcn 공통 UI, 관리 화면 셸 | 기반과 카탈로그 Task 5~6 |
| 로컬 저장 키, 이미지 검증·해시·썸네일·보상 정리 | 업로드와 작업함 Task 1~4 |
| 상품 사진·트레이 사진 맥락형 업로드와 부분 성공 | 업로드와 작업함 Task 3~6 |
| 검색·상태·상품 필터와 cursor 페이지 조회 | 업로드와 작업함 Task 4·6, 라벨링 Task 3 |
| 정규화 박스, 브랜드 격리, 비활성 상품 규칙 | 라벨링 Task 1~3 |
| 500ms 자동 저장, revision 충돌, 이동 경고 | 라벨링 Task 4~7 |
| 명시적 완료와 다음 라벨 필요 사진 이동 | 라벨링 Task 2·3·7·8 |
| 임시 파일 정리, 순환 로그, 단일 명령 실행 | 운영과 출시 Task 1~2 |
| 10만 건·100장·재시작·사내망 검증 | 운영과 출시 Task 3·5·6 |
| 접근성, 반응형, 시각 상태, Chrome·Edge 확인 | 운영과 출시 Task 4~6 |
