# 트레이 사진 라벨링 편집기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 트레이 사진의 모든 빵에 정규화 박스를 그리고 같은 브랜드의 상품을 지정해 자동 저장·완료·다음 작업 이동까지 수행한다.

**Architecture:** 서버는 expected revision과 박스 전체 목록을 한 트랜잭션으로 교체해 부분 저장을 막는다. 프런트엔드는 정규화 좌표를 순수 함수로 관리하고 Konva view state와 서버 저장 state를 분리하며, 마지막 변경 500ms 후 autosave한다.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, TypeScript, Konva 10, react-konva, TanStack Query, Vitest, React Testing Library, Playwright

## Global Constraints

- 이 계획은 [이미지 업로드와 작업함](2026-07-15-image-management-upload-library.md)이 병합된 상태에서 시작한다.
- 박스 좌표는 원본 기준 0 이상 1 이하 `x1, y1, x2, y2`이며 `x1 < x2`, `y1 < y2`다.
- 박스는 `TRAY` 이미지에만 생성하고 상품은 이미지와 같은 브랜드여야 한다.
- 새 지정에는 활성 상품만 사용하고 기존 비활성 상품 연결은 유지할 수 있다.
- 자동 저장 debounce는 마지막 변경 후 500ms다.
- revision 불일치는 409이며 자동 병합하지 않는다.
- 완료에는 박스 한 개 이상과 모든 박스의 유효한 상품이 필요하다.
- 미지정 박스가 생기거나 모든 박스가 삭제되면 `UNLABELED`로 돌아간다.
- 라벨링 화면에서는 관리 사이드바를 숨기고 1024px 미만에는 데스크톱 안내를 표시한다.

---

### Task 1: 박스 스키마와 순수 도메인 규칙

**Files:**
- Modify: `backend/app/infrastructure/models.py`
- Create: `backend/migrations/versions/0003_bounding_boxes.py`
- Create: `backend/app/domain/labeling.py`
- Create: `backend/tests/domain/test_labeling.py`
- Create: `backend/tests/infrastructure/test_bounding_box_schema.py`

**Interfaces:**
- Produces: `BoundingBoxInput(id, product_id, x1, y1, x2, y2)`, `validate_boxes`, `derive_labeling_status(current_status, boxes)`

- [ ] **Step 1: 좌표와 상태 실패 테스트 작성**

0·1 경계 허용, 음수·1 초과·역전·zero-area 거부를 테스트한다. `UNLABELED` 사진은 모든 박스가 유효해져도 명시적 완료 전까지 `UNLABELED`를 유지하고, 기존 `COMPLETED` 사진은 유효한 편집 후 완료를 유지하며 빈 목록이나 미지정 박스가 생기면 `UNLABELED`로 돌아가는지 검증한다. DB에는 `(image_id)` index와 image delete cascade를 검증한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/domain/test_labeling.py backend/tests/infrastructure/test_bounding_box_schema.py -q`

Expected: FAIL because labeling domain and table are absent.

- [ ] **Step 3: 도메인과 마이그레이션 구현**

`BoundingBoxModel`은 UUID, image/product FK, 네 좌표, UTC timestamps를 가진다. `validate_boxes`는 박스별 field path를 포함한 `LabelingValidationError`를 반환하며 부동소수점 값을 임의 반올림하지 않는다. `derive_labeling_status`는 유효한 박스만으로 미완료 사진을 자동 완료하지 않고, 완료 사진을 계속 완료로 유지할 수 있는지만 판정한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run alembic upgrade head; uv run pytest backend/tests/domain/test_labeling.py backend/tests/infrastructure/test_bounding_box_schema.py -q`

Expected: all tests pass.

- [ ] **Step 5: 박스 도메인 커밋**

```powershell
git add backend/app/domain backend/app/infrastructure/models.py backend/migrations backend/tests/domain backend/tests/infrastructure
git commit -m "feat: add bounding box domain rules"
```

### Task 2: revision 기반 전체 저장과 완료 사용 사례

**Files:**
- Create: `backend/app/application/labeling.py`
- Modify: `backend/app/infrastructure/image_repository.py`
- Create: `backend/tests/application/test_labeling_service.py`

**Interfaces:**
- Produces: `get_session(image_id)`, `replace_boxes(image_id, expected_revision, boxes)`, `complete_image(image_id, expected_revision)`

- [ ] **Step 1: transaction과 충돌 실패 테스트 작성**

전체 교체가 기존 박스를 남기지 않는지, 한 박스 검증 실패 시 아무 변경도 commit하지 않는지, 성공 시 revision이 정확히 1 증가하는지, stale revision이 `REVISION_CONFLICT`인지 테스트한다. 다른 브랜드 상품, 신규 비활성 상품, PRODUCT 이미지 박스도 거부한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/application/test_labeling_service.py -q`

Expected: FAIL because labeling service is absent.

- [ ] **Step 3: 잠금·검증·전체 교체 구현**

하나의 짧은 transaction에서 image를 읽고 expected revision을 비교한 뒤 브랜드와 상품 상태를 한 번에 조회한다. 기존 비활성 상품은 요청 박스의 동일한 기존 box id에 이미 연결된 경우만 허용한다. 교체 후 derived 상태와 새 revision을 반환한다.

- [ ] **Step 4: 상태 전이 테스트 통과 확인**

Run: `uv run pytest backend/tests/application/test_labeling_service.py -q`

Expected: all tests pass.

- [ ] **Step 5: 라벨링 서비스 커밋**

```powershell
git add backend/app/application/labeling.py backend/app/infrastructure/image_repository.py backend/tests/application
git commit -m "feat: save labels with revision control"
```

### Task 3: 라벨 세션·저장·완료·작업 요약 API

**Files:**
- Create: `backend/app/api/labeling.py`
- Create: `backend/app/application/work_queue.py`
- Create: `backend/app/api/work_queue.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/api/test_labeling_api.py`
- Create: `backend/tests/api/test_work_queue_api.py`

**Interfaces:**
- Produces: `GET/PUT /api/v1/images/{id}/labels`, `POST /api/v1/images/{id}/complete`, `GET /api/v1/brands/{id}/work-summary`, `GET /api/v1/brands/{id}/next-unlabeled`

- [ ] **Step 1: API 계약 실패 테스트 작성**

세션 응답은 image metadata, original URL, boxes, revision을 포함한다. PUT은 `{expected_revision, boxes}`를 받고 새 revision과 labeling status를 반환한다. 완료 불가 422는 `IMAGE_NOT_COMPLETABLE`, stale 409는 최신 revision과 `최신 내용을 다시 불러와 주세요.` action을 반환한다. 작업 요약과 next 대상은 `kind=TRAY`만 집계하고, next는 `created_at ASC, id ASC`의 가장 오래된 미완료 사진이다. 이미지 목록의 상품 필터는 상품 사진에서는 이미지의 `product_id`, 트레이 사진에서는 박스의 `product_id`에 대해 일치 여부를 검사한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/api/test_labeling_api.py backend/tests/api/test_work_queue_api.py -q`

Expected: 404 for new routes.

- [ ] **Step 3: 라우터와 조회 구현**

PUT schema는 클라이언트 임시 UUID를 허용하고 서버가 그대로 box id로 보존한다. work summary는 `unlabeled_count`, `completed_count`, `next_image_id`를 반환한다. 모든 query는 brand scope를 필수로 확인한다.

- [ ] **Step 4: API 테스트 통과 확인**

Run: `uv run pytest backend/tests -q`

Expected: all backend tests pass.

- [ ] **Step 5: 라벨 API 커밋**

```powershell
git add backend/app/api backend/app/application backend/app/main.py backend/tests/api
git commit -m "feat: expose labeling workflow API"
```

### Task 4: 좌표 변환과 편집 상태 reducer

**Files:**
- Create: `frontend/src/features/labeling/types.ts`
- Create: `frontend/src/features/labeling/coordinates.ts`
- Create: `frontend/src/features/labeling/editor-reducer.ts`
- Create: `frontend/src/features/labeling/coordinates.test.ts`
- Create: `frontend/src/features/labeling/editor-reducer.test.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

**Interfaces:**
- Produces: `normalizeRect`, `denormalizeRect`, `clampRect`, `labelingReducer`, `LabelingEditorState`

- [ ] **Step 1: 순수 함수 실패 테스트 작성**

서로 다른 canvas scale에서 왕복 오차가 `1e-6` 이하인지, drag가 이미지 경계를 넘지 않는지, 음의 width drag가 좌표 순서를 바로잡는지 테스트한다. reducer는 create/select/move/resize/assign/delete와 dirty 상태를 검증한다.

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test -- --run src/features/labeling/coordinates.test.ts src/features/labeling/editor-reducer.test.ts`

Expected: FAIL because pure modules are absent.

- [ ] **Step 3: 좌표와 reducer 구현**

Konva 10과 `react-konva`를 설치해 잠금 파일에 고정한다. 정규화 값은 원본 width·height로 계산하고 stage zoom과 pan은 저장 값에 포함하지 않는다. 최소 화면 박스 크기는 4px이며 저장 전 `x1 < x2`, `y1 < y2`를 재검증한다. reducer는 mutation 없이 새 배열을 반환한다.

- [ ] **Step 4: 순수 함수 테스트 통과 확인**

Run: `npm --prefix frontend run test -- --run src/features/labeling/coordinates.test.ts src/features/labeling/editor-reducer.test.ts`

Expected: all tests pass.

- [ ] **Step 5: 편집 상태 커밋**

```powershell
git add frontend/src/features/labeling
git commit -m "feat: add normalized labeling state"
```

### Task 5: Konva 박스 캔버스와 상품 편집 패널

**Files:**
- Create: `frontend/src/features/labeling/labeling-canvas.tsx`
- Create: `frontend/src/features/labeling/box-layer.tsx`
- Create: `frontend/src/features/labeling/product-panel.tsx`
- Create: `frontend/src/features/labeling/labeling-canvas.test.tsx`
- Create: `frontend/src/features/labeling/product-panel.test.tsx`

**Interfaces:**
- Produces: `LabelingCanvas`, `ProductPanel`
- Consumes: editor reducer, active products, original image URL

- [ ] **Step 1: 상호작용 실패 테스트 작성**

pointer drag 생성, 선택 박스 Transformer 이동·resize, Delete 삭제, Esc 선택 취소, N 그리기 모드, 활성 상품 검색·지정, 최근 상품 유지, 비활성 기존 상품 표시를 테스트한다. 상품 미지정은 텍스트와 dashed style, 선택은 orange 3px style을 검사한다.

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test -- --run src/features/labeling/labeling-canvas.test.tsx src/features/labeling/product-panel.test.tsx`

Expected: FAIL because canvas and panel are absent.

- [ ] **Step 3: 캔버스와 패널 구현**

canvas 바깥은 `#1F1F1F`, 완료 박스는 흰색 2px, 선택 박스는 `#EE7203` 3px과 10px handle, 미지정은 `#FAB600` 2px 점선이다. 선택 박스를 마지막에 그려 z-order를 높인다. 상품명은 줄임표와 tooltip을 사용하고 색만으로 상태를 구분하지 않는다.

- [ ] **Step 4: 상호작용 테스트 통과 확인**

Run: `npm --prefix frontend run test -- --run src/features/labeling`

Expected: all labeling component tests pass.

- [ ] **Step 5: 캔버스 커밋**

```powershell
git add frontend/src/features/labeling
git commit -m "feat: add accessible bounding box editor"
```

### Task 6: 500ms 자동 저장과 이동 보호

**Files:**
- Create: `frontend/src/features/labeling/api.ts`
- Create: `frontend/src/features/labeling/use-autosave.ts`
- Create: `frontend/src/features/labeling/save-status.tsx`
- Create: `frontend/src/features/labeling/use-autosave.test.tsx`
- Create: `frontend/src/features/labeling/navigation-guard.test.tsx`

**Interfaces:**
- Produces: `useAutosave({imageId, revision, boxes, dirty})`, save states `idle|saving|saved|failed|conflict`

- [ ] **Step 1: 시간·실패·충돌 테스트 작성**

fake timer로 마지막 변경 499ms에는 저장하지 않고 500ms에 한 번 저장하는지, 저장 중 추가 변경은 성공 직후 새 revision으로 다시 저장하는지, 네트워크 실패는 boxes를 유지하고 재시도하는지 테스트한다. dirty 또는 failed 상태의 `beforeunload`와 router 이동 경고, 409 충돌의 reload 행동도 검증한다.

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test -- --run src/features/labeling/use-autosave.test.tsx src/features/labeling/navigation-guard.test.tsx`

Expected: FAIL because autosave is absent.

- [ ] **Step 3: 저장 상태 기계 구현**

동시에 PUT을 두 개 보내지 않고 pending change flag로 후속 저장을 예약한다. 일시적인 네트워크 오류는 1초 뒤 한 번 자동 재시도하고, 다시 실패하면 편집 내용을 메모리에 유지한 채 수동 `다시 시도`를 제공한다. 상태 문구는 `저장 중`, `저장됨`, `저장하지 못함`이며 conflict에는 `최신 내용 불러오기`만 제공한다. status는 `aria-live="polite"`로 알린다.

- [ ] **Step 4: 자동 저장 테스트 통과 확인**

Run: `npm --prefix frontend run test -- --run src/features/labeling`

Expected: all labeling tests pass.

- [ ] **Step 5: 자동 저장 커밋**

```powershell
git add frontend/src/features/labeling
git commit -m "feat: autosave labels with conflict recovery"
```

### Task 7: 라벨링 집중 페이지와 오늘의 작업

**Files:**
- Create: `frontend/src/pages/labeling-page.tsx`
- Create: `frontend/src/pages/today-page.tsx`
- Create: `frontend/src/pages/labeling-page.test.tsx`
- Create: `frontend/src/pages/today-page.test.tsx`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Produces: `/images/:imageId/label`, `/` today page

- [ ] **Step 1: 완료 흐름 실패 테스트 작성**

상단의 목록 이동·파일명·진행 순서·저장 상태·완료 버튼, 320px 패널, 하단 단축키를 검사한다. 박스 0개 또는 미지정 상품이 있으면 완료가 비활성이고 이유가 보이며, 완료 성공 후 next id로 이동하고 없으면 `라벨링을 모두 마쳤어요`를 표시하는지 테스트한다. 1024px 미만에서는 canvas 대신 데스크톱 안내를 확인한다.

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test -- --run src/pages/labeling-page.test.tsx src/pages/today-page.test.tsx`

Expected: FAIL because pages are absent.

- [ ] **Step 3: 집중 페이지와 작업 요약 구현**

라벨링 route는 AppShell 바깥 layout을 사용한다. Enter는 저장 완료·완료 가능할 때만 완료를 요청한다. 오늘의 작업은 라벨 필요 수, 완료 수, `이어서 라벨링하기`만 보여주고 그래프나 모델 지표를 추가하지 않는다.

- [ ] **Step 4: 프런트엔드 검증**

Run: `npm --prefix frontend run test -- --run; npm --prefix frontend run build`

Expected: all tests and build pass.

- [ ] **Step 5: 페이지 커밋**

```powershell
git add frontend/src/pages frontend/src/app/router.tsx
git commit -m "feat: complete tray labeling workflow"
```

### Task 8: 브라우저 전체 흐름

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/labeling-flow.spec.ts`
- Create: `frontend/tests/e2e/labeling-recovery.spec.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

**Interfaces:**
- Produces: `npm --prefix frontend run test:e2e`

- [ ] **Step 1: 실패하는 Playwright 흐름 작성**

실제 임시 DB·파일 루트 서버를 띄워 브랜드 생성 → 상품 등록 → 상품 사진 등록 → 트레이 사진 등록 → 두 박스 생성 → 상품 지정 → autosave → 새로고침 → 완료 → 다음 사진 이동을 실행한다. 별도 테스트는 PUT 한 번을 실패시켜 `저장하지 못함`과 재시도, stale revision으로 충돌 안내를 확인한다.

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test:e2e`

Expected: tests fail at the first unmet browser behavior.

- [ ] **Step 3: 테스트 환경의 누락된 연결만 보완**

Playwright webServer는 `BAKERY_DATA_DIR`을 테스트 임시 폴더로 지정하고 Uvicorn 단일 worker와 Vite를 시작한다. fixture 이미지는 저장소의 작은 테스트 자산만 사용하고 실제 업무 데이터에 접근하지 않는다.

- [ ] **Step 4: 단계 전체 검증**

Run:

```powershell
uv run pytest
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 5: E2E 커밋**

```powershell
git add frontend/playwright.config.ts frontend/tests/e2e frontend/package.json frontend/package-lock.json
git commit -m "test: cover end-to-end labeling workflow"
```
