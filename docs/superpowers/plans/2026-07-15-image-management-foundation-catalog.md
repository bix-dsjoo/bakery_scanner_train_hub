# 이미지 관리 애플리케이션 기반과 카탈로그 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** React·FastAPI 애플리케이션을 실행하고 현재 브랜드 맥락에서 브랜드와 상품을 등록·수정·비활성화할 수 있는 첫 수직 기능을 만든다.

**Architecture:** FastAPI API 계층은 application 사용 사례만 호출하고, SQLAlchemy 저장소는 infrastructure에 둔다. React는 TanStack Query의 서버 상태와 `BrandProvider`의 현재 브랜드 상태를 분리하며, shadcn/ui 원본 컴포넌트와 BIXOLON 토큰으로 관리 화면 셸을 구성한다.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLAlchemy 2.0, Alembic, SQLite, pytest, React 19.2, TypeScript, Vite 8, Tailwind CSS 4, shadcn/ui, Base UI, Lucide, TanStack Query, Vitest, React Testing Library

## Global Constraints

- 일반 작업은 격리 작업 트리 없이 일반 기능 브랜치에서 수행한다.
- 데이터 루트 기본값은 `C:\BakeryScannerData`, 테스트에서는 `tmp_path`를 사용한다.
- SQLite 연결 시 WAL, foreign keys, busy timeout을 활성화하고 서버 worker는 한 개만 사용한다.
- 사용자 문구는 `브랜드`, `상품`, `활성`, `비활성`을 사용하며 내부 enum 이름을 노출하지 않는다.
- BIXOLON Orange는 `#EE7203`, 기본 배경은 `#F5F5F5`, 대표 행동은 검정 배경과 흰색 글자를 사용한다.
- UI는 Pretendard 400·500·600·700만 사용하고 다크 모드는 만들지 않는다.
- 한 화면의 대표 행동은 하나다.
- 기능 구현은 실패하는 테스트를 먼저 확인한 뒤 최소 구현으로 통과시킨다.

---

### Task 1: 백엔드 실행 기반과 설정

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/errors.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`
- Create: `.gitignore`

**Interfaces:**
- Produces: `Settings(data_dir: Path, database_url: str)`, `create_app(settings: Settings | None = None) -> FastAPI`, `GET /api/v1/health`

- [ ] **Step 1: 프로젝트 메타데이터와 실패 테스트 작성**

`pyproject.toml`은 `requires-python = ">=3.13,<3.14"`로 두고 FastAPI, Uvicorn, SQLAlchemy, Alembic, pydantic-settings를 runtime 의존성으로, pytest, pytest-asyncio, httpx를 dev 의존성으로 선언한다. `.python-version`은 `3.13`이다. `backend/tests/test_health.py`를 다음 계약으로 작성한다.

```python
def test_health_returns_ready(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
```

- [ ] **Step 2: 실패 확인**

Run: `uv sync --all-groups; uv run pytest backend/tests/test_health.py -q`

Expected: collection fails because `backend.app.main` does not exist.

- [ ] **Step 3: 설정과 앱 팩토리 구현**

`Settings`는 `BAKERY_DATA_DIR` 환경 변수를 읽고 `database/app.db`, `originals`, `thumbnails`, `imports`, `trash`, `logs` 경로를 계산한다. `create_app`은 lifespan에서 디렉터리를 만들고 `/api/v1/health`가 정확히 `{"status": "ready"}`를 반환하게 한다. 오류 응답 모델은 아래 형태로 고정한다.

```python
class ApiError(BaseModel):
    code: str
    message: str
    action: str | None = None
    field_errors: dict[str, str] | None = None
```

- [ ] **Step 4: 테스트 통과와 잠금 파일 생성 확인**

Run: `uv lock; uv run pytest backend/tests/test_health.py -q`

Expected: `1 passed` and `uv.lock` exists.

- [ ] **Step 5: 기반 커밋**

```powershell
git add pyproject.toml uv.lock .python-version .gitignore backend
git commit -m "build: scaffold FastAPI backend"
```

### Task 2: SQLite 연결과 초기 스키마

**Files:**
- Create: `backend/app/infrastructure/database.py`
- Create: `backend/app/infrastructure/models.py`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/0001_catalog.py`
- Create: `alembic.ini`
- Create: `backend/tests/infrastructure/test_database.py`

**Interfaces:**
- Produces: `create_engine_for(settings) -> Engine`, `session_scope(session_factory)`, tables `brands`, `products`

- [ ] **Step 1: 연결 정책과 제약 테스트 작성**

테스트는 새 연결에서 `PRAGMA journal_mode`가 `wal`, `PRAGMA foreign_keys`가 `1`, `PRAGMA busy_timeout`이 5,000 이상인지 확인한다. 같은 브랜드 이름과 같은 브랜드의 상품 코드 중복 insert가 `IntegrityError`를 내는 테스트도 작성한다.

```python
assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() >= 5000
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/infrastructure/test_database.py -q`

Expected: FAIL because database module and tables are absent.

- [ ] **Step 3: 엔진, 모델과 마이그레이션 구현**

`BrandModel`은 UUID 문자열 `id`, unique `name`, `status`, UTC `created_at`, `updated_at`을 가진다. `ProductModel`은 같은 공통 필드와 `brand_id`, `code`, `name`을 가지며 `UniqueConstraint("brand_id", "code")`를 둔다. SQLite connect event에서 다음을 실행한다.

```python
cursor.execute("PRAGMA foreign_keys=ON")
cursor.execute("PRAGMA busy_timeout=5000")
cursor.execute("PRAGMA journal_mode=WAL")
```

- [ ] **Step 4: 마이그레이션과 테스트 통과 확인**

Run: `uv run alembic upgrade head; uv run pytest backend/tests/infrastructure/test_database.py -q`

Expected: all tests pass and `brands`, `products`, `alembic_version` exist.

- [ ] **Step 5: DB 기반 커밋**

```powershell
git add alembic.ini backend/app/infrastructure backend/migrations backend/tests/infrastructure
git commit -m "feat: add catalog database schema"
```

### Task 3: 브랜드와 상품 업무 규칙

**Files:**
- Create: `backend/app/domain/catalog.py`
- Create: `backend/app/application/catalog.py`
- Create: `backend/app/infrastructure/catalog_repository.py`
- Create: `backend/tests/application/test_catalog.py`

**Interfaces:**
- Produces: `CatalogService.create_brand`, `update_brand`, `deactivate_brand`, `create_product`, `update_product`, `deactivate_product`, `list_brands(status, query)`, `list_products(brand_id, status, query)`
- Consumes: SQLAlchemy `Session`, `BrandModel`, `ProductModel`

- [ ] **Step 1: 업무 규칙 실패 테스트 작성**

다음 사례를 각각 이름이 드러나는 테스트로 작성한다.

```python
def test_duplicate_brand_name_is_rejected(...): ...
def test_product_code_is_unique_inside_brand(...): ...
def test_same_product_code_is_allowed_in_another_brand(...): ...
def test_deactivation_keeps_existing_product(...): ...
```

중복은 `CatalogConflict(code, message, action, field_errors)`로, 없는 자원은 `CatalogNotFound`로 표현한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/application/test_catalog.py -q`

Expected: FAIL because catalog service is absent.

- [ ] **Step 3: 최소 서비스와 저장소 구현**

서비스는 입력 양끝 공백을 제거하고 빈 이름·코드를 거부한다. 브랜드 이름 중복 코드는 `BRAND_NAME_DUPLICATE`, 상품 코드 중복 코드는 `PRODUCT_CODE_DUPLICATE`다. 비활성화는 row 삭제가 아니라 `status="INACTIVE"` 갱신이다.

- [ ] **Step 4: 업무 규칙 테스트 통과 확인**

Run: `uv run pytest backend/tests/application/test_catalog.py -q`

Expected: all catalog tests pass.

- [ ] **Step 5: 도메인 커밋**

```powershell
git add backend/app/domain backend/app/application backend/app/infrastructure/catalog_repository.py backend/tests/application
git commit -m "feat: enforce brand and product rules"
```

### Task 4: 카탈로그 API

**Files:**
- Create: `backend/app/api/dependencies.py`
- Create: `backend/app/api/catalog.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/api/test_catalog_api.py`

**Interfaces:**
- Produces: `GET/POST /api/v1/brands`, `PATCH /api/v1/brands/{brand_id}`, `GET/POST /api/v1/brands/{brand_id}/products`, `PATCH /api/v1/brands/{brand_id}/products/{product_id}`
- Consumes: `CatalogService`

- [ ] **Step 1: API 계약 실패 테스트 작성**

브랜드 생성 `POST /api/v1/brands`는 `201`, 상품 생성은 `201`, 목록은 `200`, 비활성화 PATCH는 갱신된 자원을 반환한다. 브랜드와 상품 목록은 `status`와 이름·코드 `query`를 적용하며 다른 브랜드의 상품을 반환하지 않는다. 중복 응답은 다음 값까지 검사한다.

```python
assert response.status_code == 409
assert response.json()["code"] == "PRODUCT_CODE_DUPLICATE"
assert response.json()["field_errors"] == {"code": "이미 사용 중인 코드예요."}
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/api/test_catalog_api.py -q`

Expected: 404 for catalog routes.

- [ ] **Step 3: Pydantic 스키마, 라우터와 예외 매핑 구현**

요청 스키마는 이름 1~100자, 상품 코드 1~50자를 검증한다. API 계층은 세션을 주입받아 서비스를 호출하고 `CatalogConflict`를 409 `ApiError`, `CatalogNotFound`를 404로 변환한다. 응답의 날짜는 UTC ISO 8601 문자열이다.

- [ ] **Step 4: API와 전체 백엔드 테스트 통과 확인**

Run: `uv run pytest backend/tests -q`

Expected: all backend tests pass.

- [ ] **Step 5: API 커밋**

```powershell
git add backend/app/api backend/app/main.py backend/tests/api
git commit -m "feat: expose catalog API"
```

### Task 5: 프런트엔드·디자인 시스템 기반

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/components.json`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/app/providers.tsx`
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/dialog.tsx`
- Create: `frontend/src/components/ui/select.tsx`
- Create: `frontend/src/components/ui/label.tsx`
- Create: `frontend/src/components/ui/sidebar.tsx`
- Create: `frontend/src/components/ui/sheet.tsx`
- Create: `frontend/src/components/ui/alert-dialog.tsx`
- Create: `frontend/src/components/ui/dropdown-menu.tsx`
- Create: `frontend/src/components/ui/table.tsx`
- Create: `frontend/src/components/ui/tabs.tsx`
- Create: `frontend/src/components/ui/badge.tsx`
- Create: `frontend/src/components/ui/progress.tsx`
- Create: `frontend/src/components/ui/skeleton.tsx`
- Create: `frontend/src/components/ui/tooltip.tsx`
- Create: `frontend/src/components/ui/sonner.tsx`
- Create: `frontend/src/components/ui/separator.tsx`
- Create: `frontend/src/components/ui/popover.tsx`
- Create: `frontend/src/components/ui/command.tsx`
- Create: `frontend/src/components/ui/combobox.tsx`
- Create: `frontend/src/shared/api/client.ts`
- Create: `frontend/tests/setup.ts`
- Create: `frontend/src/app/app-shell.test.tsx`

**Interfaces:**
- Produces: `apiClient<T>(path, init?)`, `AppProviders`, `AppRouter`, shadcn 공통 컴포넌트

- [ ] **Step 1: Vite 프로젝트와 실패 테스트 작성**

React 19.2, Vite 8, TypeScript, Tailwind CSS 4, React Router, TanStack Query, Base UI, Lucide, 공식 `pretendard@1.3.9`, Vitest, Testing Library, MSW를 설치하고 lockfile을 만든다. `components.json`은 style `base-nova`, base color `neutral`, CSS variables 사용, RSC 비사용으로 고정한다. 테스트는 앱 이름과 세 메뉴를 요구한다.

```tsx
render(<AppRouter />)
expect(screen.getByText("Bakery Scanner Train Hub")).toBeVisible()
expect(screen.getByRole("link", { name: "상품 관리" })).toBeVisible()
```

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test -- --run src/app/app-shell.test.tsx`

Expected: FAIL because shell and router are absent.

- [ ] **Step 3: 토큰, provider와 관리 셸 구현**

`main.tsx`에서 `pretendard/dist/web/variable/pretendardvariable.css`를 import해 variable font를 self-host하고 실제 사용 굵기는 400·500·600·700으로 제한한다. `index.css`에 승인된 색상, 6px radius, 36px 일반 컨트롤, 2px 오렌지 focus ring을 CSS 변수로 정의한다. 1280px 이상은 224px 사이드바, 그 미만은 Sheet 탐색을 사용한다. 메뉴는 `오늘의 작업`, `상품 관리`, `트레이 사진`만 둔다. 공식 로고 자산이 없으므로 앱 이름은 일반 텍스트로 표시한다. `apiClient`는 오류 JSON을 `ApiClientError`로 보존한다.

- [ ] **Step 4: 테스트와 production build 통과 확인**

Run: `npm --prefix frontend run test -- --run; npm --prefix frontend run build`

Expected: tests pass and `frontend/dist` is produced.

- [ ] **Step 5: 프런트엔드 기반 커밋**

```powershell
git add frontend
git commit -m "build: scaffold branded React application"
```

### Task 6: 브랜드 맥락과 상품 관리 화면

**Files:**
- Create: `frontend/src/features/brands/api.ts`
- Create: `frontend/src/features/brands/brand-provider.tsx`
- Create: `frontend/src/features/brands/brand-selector.tsx`
- Create: `frontend/src/features/brands/brand-form-dialog.tsx`
- Create: `frontend/src/features/brands/brand-management-dialog.tsx`
- Create: `frontend/src/features/products/api.ts`
- Create: `frontend/src/features/products/product-form-dialog.tsx`
- Create: `frontend/src/pages/products-page.tsx`
- Create: `frontend/src/features/brands/brand-provider.test.tsx`
- Create: `frontend/src/pages/products-page.test.tsx`
- Modify: `frontend/src/app/app-shell.tsx`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Produces: `useCurrentBrand() -> {brand, setBrandId}`, `ProductsPage`
- Consumes: 카탈로그 API와 `apiClient`

- [ ] **Step 1: 상태와 화면 실패 테스트 작성**

MSW로 API를 가로채 다음을 검증한다: 첫 활성 브랜드 자동 선택, `localStorage`의 `bakery.currentBrandId` 복원, 다른 브랜드로 전환할 때 상품 재조회, 상품 추가 dialog의 접근 가능한 이름, 중복 코드의 입력 아래 오류, 비활성 상품 badge.

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test -- --run src/features/brands src/pages/products-page.test.tsx`

Expected: FAIL because provider and page are absent.

- [ ] **Step 3: 브랜드 맥락과 상품 화면 구현**

현재 브랜드가 없으면 브랜드 생성 dialog 하나만 대표 행동으로 제공한다. 브랜드 선택기의 `브랜드 관리` dialog에서 이름 수정과 비활성화를 제공하고, 현재 브랜드를 비활성화하면 다음 활성 브랜드로 전환하거나 활성 브랜드가 없다는 빈 상태를 표시한다. 상품 페이지는 제목, `상품 추가`, 검색 입력, 상태 필터, 52~64px 목록 행 순서로 구성한다. 생성·수정 성공 시 query를 무효화하고, 비활성화는 명시적인 확인 dialog를 거친다. 현재 메뉴 앞에는 짧은 오렌지 대각선 표시를 사용한다.

- [ ] **Step 4: 접근성·기능 테스트와 build 통과 확인**

Run: `npm --prefix frontend run test -- --run; npm --prefix frontend run build`

Expected: all frontend tests pass and TypeScript build succeeds.

- [ ] **Step 5: 카탈로그 UI 커밋**

```powershell
git add frontend/src frontend/tests
git commit -m "feat: add brand-scoped product management"
```

### Task 7: 개발 실행 계약과 단계 검증

**Files:**
- Create: `backend/app/static.py`
- Modify: `backend/app/main.py`
- Modify: `frontend/vite.config.ts`
- Create: `start-dev.ps1`
- Modify: `README.md`
- Create: `backend/tests/test_spa_fallback.py`

**Interfaces:**
- Produces: 개발 API proxy, production SPA 정적 제공, `start-dev.ps1`

- [ ] **Step 1: 정적 제공 실패 테스트 작성**

임시 `frontend/dist`에 `index.html`과 asset을 만들고 `/products`가 index를, `/assets/app.js`가 asset을 반환하며 `/api/v1/unknown`은 SPA로 fallback하지 않는지 테스트한다. 운영 API 응답에 wildcard `Access-Control-Allow-Origin`이 없다는 것도 확인한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/test_spa_fallback.py -q`

Expected: FAIL because static mounting is absent.

- [ ] **Step 3: 정적 제공, 개발 스크립트와 README 구현**

개발 Vite는 `/api`를 `http://127.0.0.1:8000`으로 proxy한다. `start-dev.ps1`은 uv sync 후 FastAPI reload 프로세스와 npm dev server를 시작하고 종료 시 두 프로세스를 정리한다. README에는 Python 3.13·uv·Node 24 선행 조건과 `./start-dev.ps1`을 기록한다.

- [ ] **Step 4: 단계 전체 검증**

Run:

```powershell
uv run pytest
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 5: 실행 계약 커밋**

```powershell
git add backend/app backend/tests frontend/vite.config.ts start-dev.ps1 README.md
git commit -m "feat: serve application in development and production"
```
