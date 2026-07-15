# 이미지 관리 운영과 출시 검증 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows PC 한 대와 사내망에서 이미지 관리 MVP를 반복 실행하고, 파일 정리·로그·용량·접근성·데이터 유지 조건을 검증해 첫 내부 출시 기준을 충족한다.

**Architecture:** FastAPI lifespan이 데이터 디렉터리와 오래된 임시·trash 파일을 정리하고 rotating file log를 구성한다. 루트 `start.ps1`은 선행 도구 확인, 잠금 설치, 프런트 빌드, DB migration, Uvicorn 단일 worker 시작을 순서대로 수행하며 운영 검증은 자동 테스트와 Windows 수동 체크리스트로 분리한다.

**Tech Stack:** PowerShell 7/Windows PowerShell 5.1 호환 문법, Uvicorn, Alembic, pytest, Playwright, axe-core, SQLite

## Global Constraints

- 이 계획은 [트레이 사진 라벨링 편집기](2026-07-15-image-management-labeling-editor.md)가 병합된 상태에서 시작한다.
- 운영 bind 기본값은 `0.0.0.0:8000`, worker는 정확히 1개다.
- `start.ps1`은 관리자 권한을 요구하거나 Windows 방화벽을 변경하지 않는다.
- 24시간보다 오래된 `imports`와 `trash` 잔여 파일만 시작 시 정리한다.
- 로그는 파일당 10MB, backup 최대 5개이며 원본 이미지 내용과 불필요한 전체 사용자 경로를 기록하지 않는다.
- 자동 백업·복구, HTTPS, 외부 인터넷 공개, 로그인은 범위 밖이다.
- 기준 용량은 이미지 metadata 10만 건, 일괄 등록 100장이다.

---

### Task 1: 시작 정리와 순환 로그

**Files:**
- Create: `backend/app/infrastructure/maintenance.py`
- Create: `backend/app/logging_config.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/infrastructure/test_maintenance.py`
- Create: `backend/tests/test_logging.py`

**Interfaces:**
- Produces: `cleanup_stale_files(settings, now)`, `configure_logging(settings)`

- [ ] **Step 1: 보존 기간과 로그 실패 테스트 작성**

23시간 파일은 유지하고 25시간 파일은 imports·trash에서 삭제하며 다른 디렉터리는 건드리지 않는지 테스트한다. RotatingFileHandler의 `maxBytes=10*1024*1024`, `backupCount=5`와 시작·종료·업로드 실패·revision 충돌 log event를 검증한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/infrastructure/test_maintenance.py backend/tests/test_logging.py -q`

Expected: FAIL because maintenance and logging configuration are absent.

- [ ] **Step 3: 정리와 구조화 로그 구현**

정리 실패는 앱 시작을 막지 않고 상대 storage key와 오류 종류만 기록한다. lifespan은 설정·logging → 디렉터리 생성 → stale cleanup → DB 준비 순서로 실행한다. logger는 전체 원본 경로나 이미지 bytes를 extra에 넣지 않는다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest backend/tests/infrastructure/test_maintenance.py backend/tests/test_logging.py -q`

Expected: all tests pass.

- [ ] **Step 5: 유지보수 커밋**

```powershell
git add backend/app backend/tests
git commit -m "feat: clean stale files and rotate logs"
```

### Task 2: 운영용 start.ps1

**Files:**
- Create: `start.ps1`
- Create: `scripts/Test-StartScript.ps1`
- Modify: `backend/app/config.py`
- Create: `backend/tests/test_runtime_config.py`

**Interfaces:**
- Produces: `./start.ps1 [-Host <string>] [-Port <int>]`, env `BAKERY_HOST`, `BAKERY_PORT`, `BAKERY_DATA_DIR`

- [ ] **Step 1: 스크립트 계약 실패 검사 작성**

`scripts/Test-StartScript.ps1`은 PowerShell parser 오류 없음, Python 3.13·uv·Node 24 검사 문구, `uv sync --frozen`, `npm ci`, `npm run build`, `alembic upgrade head`, `uvicorn ... --workers 1` 순서를 정규식과 위치 비교로 검증한다. 누락 도구 simulation에서는 한국어 조치 문구와 non-zero exit를 요구한다.

- [ ] **Step 2: 실패 확인**

Run: `pwsh -NoProfile -File scripts/Test-StartScript.ps1`

Expected: FAIL because `start.ps1` is absent.

- [ ] **Step 3: start.ps1 구현**

스크립트는 저장소 루트를 `$PSScriptRoot`로 고정하고 현재 작업 디렉터리에 의존하지 않는다. lockfile이 바뀌는 명령을 사용하지 않으며 프런트 빌드 실패나 migration 실패 시 서버를 시작하지 않는다. 기본 bind는 `0.0.0.0:8000`이고 실행 전에 실제 접속 주소와 데이터 경로, 자동 백업이 없다는 경고를 출력한다.

- [ ] **Step 4: 정적 검사와 runtime config 테스트 통과 확인**

Run: `pwsh -NoProfile -File scripts/Test-StartScript.ps1; uv run pytest backend/tests/test_runtime_config.py -q`

Expected: both commands exit 0.

- [ ] **Step 5: 운영 실행 커밋**

```powershell
git add start.ps1 scripts backend/app/config.py backend/tests/test_runtime_config.py
git commit -m "feat: add single-command Windows startup"
```

### Task 3: 10만 건 목록 성능과 100장 등록 부하 검증

**Files:**
- Create: `backend/tests/performance/test_image_listing.py`
- Create: `frontend/tests/e2e/upload-concurrency.spec.ts`
- Create: `scripts/Measure-ImageLibrary.ps1`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: opt-in pytest marker `performance`, repeatable local measurement script

- [ ] **Step 1: 기준을 코드로 작성**

성능 테스트는 bulk insert로 10만 metadata를 만들고 status·filename·product filter 각각의 첫 50건 API 요청 elapsed가 2초 미만인지 측정한다. Playwright는 100개의 작은 fixture를 선택하고 서버 route 계수로 동시 multipart 요청 최대가 2이며 완료 후 JS heap 또는 queue 보유 항목이 파일 수에 따라 계속 증가하지 않는지 확인한다.

- [ ] **Step 2: 기준선 실행**

Run: `uv run pytest -m performance backend/tests/performance/test_image_listing.py -q; npm --prefix frontend run test:e2e -- upload-concurrency.spec.ts`

Expected: tests either fail at the explicit threshold or pass; elapsed time and max concurrency are printed for the review record.

- [ ] **Step 3: 측정에서 확인된 query와 queue 병목만 수정**

SQLite `EXPLAIN QUERY PLAN`이 image 목록 복합 인덱스를 사용하는지 assertion으로 남긴다. full table scan이면 migration에 필요한 covering index를 추가하고, 원본 bytes eager load가 있으면 metadata projection으로 제한한다. 업로더는 완료된 File reference를 결과 요약에 필요한 이름·상태만 남기고 해제한다.

- [ ] **Step 4: 성능 기준 통과 확인**

Run: `pwsh -NoProfile -File scripts/Measure-ImageLibrary.ps1`

Expected: 100,000 rows, each measured first page below 2,000ms, max upload concurrency 2.

- [ ] **Step 5: 용량 검증 커밋**

```powershell
git add backend/tests/performance frontend/tests/e2e scripts pyproject.toml uv.lock
git commit -m "test: verify target image library capacity"
```

### Task 4: 접근성·반응형·시각 상태 검증

**Files:**
- Create: `frontend/tests/e2e/accessibility.spec.ts`
- Create: `frontend/tests/e2e/responsive-visual.spec.ts`
- Create: `frontend/tests/e2e/fixtures/long-content.ts`
- Modify: `frontend/playwright.config.ts`
- Modify: `frontend/package.json`

**Interfaces:**
- Produces: axe checks and screenshot artifacts for 1440×900, 1280×720, 1024×768

- [ ] **Step 1: 접근성과 layout 실패 테스트 작성**

axe-core로 이름 없는 버튼, label 연결, 주요 ARIA, 심각한 명암 오류가 0인지 검사한다. keyboard-only로 브랜드 선택, 상품 등록, 업로드, N·Delete·Esc·Enter를 실행한다. 각 viewport에서 빈 목록, loading, 오류, 100개 목록, 긴 한글명·파일명, 세 저장 상태, 밝고 어두운 사진의 세 박스 상태를 screenshot으로 남기고 겹침·잘림 assertion을 둔다.

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test:e2e -- accessibility.spec.ts responsive-visual.spec.ts`

Expected: tests fail at any unmet accessible name, focus, overflow, or state requirement.

- [ ] **Step 3: 발견된 결함을 해당 원본 컴포넌트에서 수정**

공통 버튼·dialog·sheet 결함은 `components/ui`, 기능 상태 결함은 해당 feature에서 수정한다. 200% zoom에서 대표 행동과 저장 상태를 DOM viewport assertion으로 확인하고 `prefers-reduced-motion`에서 비필수 transition duration이 0인지 검사한다.

- [ ] **Step 4: 접근성과 시각 검증 통과 확인**

Run: `npm --prefix frontend run test:e2e -- accessibility.spec.ts responsive-visual.spec.ts`

Expected: all checks pass and screenshots are attached to the Playwright report.

- [ ] **Step 5: 품질 검증 커밋**

```powershell
git add frontend
git commit -m "test: verify accessibility and responsive states"
```

### Task 5: Windows·사내망 수동 승인 체크리스트

**Files:**
- Create: `docs/operations/windows-internal-release-checklist.md`
- Create: `docs/operations/data-directory.md`
- Modify: `README.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Produces: 운영자가 실제 PC에서 서명 가능한 첫 출시 체크리스트

- [ ] **Step 1: 체크리스트 필수 항목 검사 작성**

PowerShell 검사에서 문서가 localhost 접속, 사내망 다른 PC 접속, 도메인·개인 방화벽 profile, 공용 profile 금지, 외부 port forwarding 금지, 재시작 유지, 데이터 경로, 디스크 여유, 자동 백업 없음과 복구 불가 위험을 모두 포함하는지 확인한다.

- [ ] **Step 2: 실패 확인**

Run: `pwsh -NoProfile -Command "$c=Get-Content -Raw -Encoding utf8 docs/operations/windows-internal-release-checklist.md; if(-not $c.Contains('자동 백업')){exit 1}"`

Expected: FAIL because checklist is absent.

- [ ] **Step 3: 운영 문서와 프로젝트 입구 갱신**

체크리스트에는 실행 날짜, PC 이름, 실행자, 앱 commit, 1TB 이상 데이터 디스크 확인, 실제 Chrome과 Edge 확인, 각 결과와 메모 칸을 둔다. `data-directory.md`는 `database`, `originals`, `thumbnails`, `imports`, `trash`, `logs`의 역할과 앱 종료 후 수동 복사 시 SQLite DB·WAL·SHM과 파일 전체를 같은 시점으로 다뤄야 함을 설명하되 이를 내장 백업 기능처럼 표현하지 않는다. README와 AGENTS의 현재 단계·실행 명령·위험을 실제 구현과 일치시킨다.

- [ ] **Step 4: 문서 계약과 링크 확인**

Run:

```powershell
$files = @('README.md','AGENTS.md','docs/operations/windows-internal-release-checklist.md','docs/operations/data-directory.md')
foreach ($file in $files) { if (-not (Test-Path $file)) { throw "Missing $file" } }
git diff --check
```

Expected: no missing files and no whitespace errors.

- [ ] **Step 5: 운영 문서 커밋**

```powershell
git add README.md AGENTS.md docs/operations
git commit -m "docs: add internal Windows operations guide"
```

### Task 6: 첫 내부 출시 최종 게이트

**Files:**
- Modify: `docs/operations/windows-internal-release-checklist.md`

**Interfaces:**
- Consumes: all automated suites and actual Windows internal-network verification
- Produces: checked release evidence tied to one commit

- [ ] **Step 1: 깨끗한 환경에서 자동 게이트 실행**

```powershell
uv sync --frozen --all-groups
npm --prefix frontend ci
uv run pytest
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
pwsh -NoProfile -File scripts/Measure-ImageLibrary.ps1
pwsh -NoProfile -File scripts/Test-StartScript.ps1
git diff --check
```

Expected: every command exits 0 with no skipped release-critical suite.

- [ ] **Step 2: 실제 Windows PC에서 실행 흐름 확인**

`./start.ps1`로 시작해 `http://localhost:8000`에서 전체 대표 흐름을 수행하고 서버를 재시작한 뒤 브랜드, 상품, 이미지, 박스, 완료 상태가 유지되는지 체크리스트에 기록한다.

- [ ] **Step 3: 사내망 다른 PC 접속 확인**

도메인 또는 개인 네트워크 profile에서만 Windows 방화벽 inbound rule을 운영자가 직접 설정한 뒤 `http://<서버-PC-IP>:8000` 접속과 대표 조회를 확인한다. 공용 profile과 외부 port forwarding이 비활성임을 기록한다.

- [ ] **Step 4: 데이터 위험 확인과 최종 상태 기록**

기본 또는 설정된 `BAKERY_DATA_DIR`와 10GB 여유 공간 검사를 확인하고, 자동 백업이 없어 PC·디스크 장애 시 복구할 수 없다는 운영 수용 여부를 체크한다. 한 항목이라도 실패하면 출시 상태를 승인으로 표시하지 않는다.

- [ ] **Step 5: 검증 기록 커밋**

```powershell
git add docs/operations/windows-internal-release-checklist.md
git commit -m "docs: record internal release verification"
```
