# 이미지 업로드와 작업함 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상품 사진과 트레이 사진을 파일별로 안전하게 등록하고 브랜드별 작업함에서 검색·필터·페이지 조회·삭제할 수 있게 한다.

**Architecture:** 업로드 application service가 스트리밍, 내용 검증, 해시, 썸네일, 파일 이동과 DB 등록을 하나의 보상 가능한 흐름으로 조정한다. 브라우저는 파일 하나당 한 요청을 보내되 동시 요청을 2개로 제한하고, 성공한 파일은 유지하면서 파일별 결과를 표시한다.

**Tech Stack:** FastAPI UploadFile, Pillow, SQLAlchemy 2.0, pytest, React, TanStack Query, shadcn/ui, Vitest, MSW

## Global Constraints

- 이 계획은 [애플리케이션 기반과 카탈로그](2026-07-15-image-management-foundation-catalog.md)가 병합된 상태에서 시작한다.
- 지원 형식은 JPEG, PNG, WebP이며 실제 파일 내용을 디코딩해 확인한다.
- 파일당 기본 최대 용량은 25MB이고 처리 후 디스크 여유 공간을 최소 10GB 남긴다.
- 원본은 재인코딩하지 않고, 썸네일은 긴 변 최대 512px의 WebP다.
- 저장 키는 서버가 생성하며 사용자 파일명을 경로에 사용하지 않는다.
- 같은 브랜드의 같은 SHA-256 이미지는 중복 등록하지 않는다.
- 브라우저 업로드 동시 요청은 최대 2개다.
- 목록 기본 페이지 크기는 50, 최대 100이며 `created_at DESC, id DESC` cursor를 사용한다.

---

### Task 1: 이미지 스키마와 조회 인덱스

**Files:**
- Modify: `backend/app/infrastructure/models.py`
- Create: `backend/migrations/versions/0002_images.py`
- Create: `backend/app/domain/images.py`
- Create: `backend/tests/infrastructure/test_image_schema.py`

**Interfaces:**
- Produces: `ImageModel`, immutable `ImageRecord`, enums `ImageKind(PRODUCT, TRAY)`, `LabelingStatus(UNLABELED, COMPLETED)`

- [ ] **Step 1: 제약과 인덱스 실패 테스트 작성**

상품 사진의 `product_id` 필수, 트레이 사진의 `product_id` 비어 있음, `(brand_id, sha256)` unique, 이미지 목록 복합 인덱스 존재를 검사한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/infrastructure/test_image_schema.py -q`

Expected: FAIL because `images` table is absent.

- [ ] **Step 3: 모델과 마이그레이션 구현**

`images`에 제품 설계의 모든 필드를 추가하고 `revision` 기본값은 0으로 둔다. kind와 product 연결은 DB check constraint와 application 검증을 모두 사용한다. 상품 삭제는 `RESTRICT`, 브랜드 삭제도 `RESTRICT`다.

- [ ] **Step 4: 마이그레이션과 테스트 통과 확인**

Run: `uv run alembic upgrade head; uv run pytest backend/tests/infrastructure/test_image_schema.py -q`

Expected: all tests pass.

- [ ] **Step 5: 스키마 커밋**

```powershell
git add backend/app/infrastructure/models.py backend/app/domain/images.py backend/migrations backend/tests/infrastructure
git commit -m "feat: add image metadata schema"
```

### Task 2: 스트리밍 파일 저장소와 이미지 검사

**Files:**
- Create: `backend/app/infrastructure/file_storage.py`
- Create: `backend/app/infrastructure/image_processor.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `backend/tests/infrastructure/test_file_storage.py`
- Create: `backend/tests/infrastructure/test_image_processor.py`
- Create: `backend/tests/fixtures/valid.jpg`
- Create: `backend/tests/fixtures/valid.png`
- Create: `backend/tests/fixtures/valid.webp`
- Create: `backend/tests/fixtures/corrupt.jpg`

**Interfaces:**
- Produces: `LocalFileStorage.stream_import`, `promote`, `move_to_trash`, `restore_from_trash`, `delete_trash`; `ImageProcessor.inspect`, `create_thumbnail`

- [ ] **Step 1: 저장과 검사 실패 테스트 작성**

스트리밍 중 25MB 초과 즉시 중단, SHA-256 정확성, 사용자 파일명 미사용, hash prefix 경로, 긴 변 512px WebP, 손상 파일·확장자 위장 거부를 테스트한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/infrastructure/test_file_storage.py backend/tests/infrastructure/test_image_processor.py -q`

Expected: FAIL because storage and processor are absent.

- [ ] **Step 3: 순수 파일 구현 작성**

Pillow와 multipart parsing 의존성을 `pyproject.toml`에 추가하고 잠금 파일을 갱신한다. 64KiB chunk로 `imports`에 기록하며 크기와 SHA-256을 동시에 계산한다. `Image.verify()` 후 실제 format을 MIME으로 매핑하고, thumbnail 생성 시 EXIF orientation을 적용한다. 최종 키는 `<brand>/<hash[0:2]>/<hash[2:4]>/<uuid>.<ext>`다.

- [ ] **Step 4: 저장소 테스트 통과 확인**

Run: `uv run pytest backend/tests/infrastructure/test_file_storage.py backend/tests/infrastructure/test_image_processor.py -q`

Expected: all tests pass and no test file remains outside `tmp_path`.

- [ ] **Step 5: 파일 기반 커밋**

```powershell
git add backend/app/infrastructure backend/tests/infrastructure backend/tests/fixtures
git commit -m "feat: validate and store image files"
```

### Task 3: 보상 가능한 이미지 등록 사용 사례

**Files:**
- Create: `backend/app/application/image_upload.py`
- Create: `backend/app/infrastructure/image_repository.py`
- Create: `backend/tests/application/test_image_upload.py`

**Interfaces:**
- Produces: `ImageUploadService.upload(brand_id: str, kind: ImageKind, product_id: str | None, filename: str, stream: BinaryIO) -> ImageRecord`
- Consumes: catalog repository, image repository, file storage, image processor, `DiskSpaceProbe.can_accept(byte_limit: int, reserve_bytes: int) -> bool`

- [ ] **Step 1: 업로드 상태와 보상 실패 테스트 작성**

상품 사진은 활성·같은 브랜드 상품일 때 `COMPLETED`, 트레이 사진은 product 없이 `UNLABELED`인지 테스트한다. 중복, 다른 브랜드 상품, 비활성 상품, 디스크 부족, DB commit 실패 후 원본·썸네일 정리도 각각 검증한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/application/test_image_upload.py -q`

Expected: FAIL because upload service is absent.

- [ ] **Step 3: 등록 orchestration 구현**

처리 순서는 여유 공간 → stream/hash → 실제 이미지 검사 → 브랜드 중복 → thumbnail → 두 파일 promote → DB commit이다. 실패하면 현재 요청이 만든 임시·최종 파일만 역순으로 정리한다. 오류 코드는 `IMAGE_TOO_LARGE`, `IMAGE_UNSUPPORTED`, `IMAGE_CORRUPT`, `IMAGE_DUPLICATE`, `DISK_SPACE_LOW`, `PRODUCT_INACTIVE`, `PRODUCT_BRAND_MISMATCH`로 고정한다.

- [ ] **Step 4: 사용 사례 테스트 통과 확인**

Run: `uv run pytest backend/tests/application/test_image_upload.py -q`

Expected: all tests pass.

- [ ] **Step 5: 업로드 서비스 커밋**

```powershell
git add backend/app/application/image_upload.py backend/app/infrastructure/image_repository.py backend/tests/application
git commit -m "feat: add compensated image upload flow"
```

### Task 4: 이미지 업로드·조회·삭제 API

**Files:**
- Create: `backend/app/application/image_library.py`
- Create: `backend/app/api/images.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/api/test_images_api.py`

**Interfaces:**
- Produces: `POST /api/v1/brands/{brand_id}/images`, `GET /api/v1/brands/{brand_id}/images`, `GET /api/v1/images/{id}`, `PATCH /api/v1/images/{id}/product`, `GET /api/v1/images/{id}/original`, `GET /api/v1/images/{id}/thumbnail`, `DELETE /api/v1/images/{id}`

- [ ] **Step 1: HTTP 계약 실패 테스트 작성**

multipart 단일 파일 등록, kind별 product 요구, MIME·Content-Disposition, status·product·filename 검색, cursor 다음 페이지, 최대 limit 100, 다른 브랜드 격리를 테스트한다. 상품 사진 재지정은 같은 브랜드의 활성 상품만 허용하고 연결 제거와 트레이 사진 재지정은 거부한다. 삭제는 상세 응답의 `box_count`를 제공하고, 원본·썸네일이 trash로 이동된 뒤 DB row가 제거되는지와 DB 실패 시 복원되는지 확인한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest backend/tests/api/test_images_api.py -q`

Expected: 404 for image routes.

- [ ] **Step 3: API와 cursor 조회 구현**

cursor는 마지막 `created_at`과 `id`를 URL-safe base64 JSON으로 인코딩한다. 목록 응답은 `items`와 `next_cursor`만 제공하고 원본 bytes는 포함하지 않는다. 상세 응답은 삭제 확인에 사용할 `box_count`를 포함한다. 파일 조회는 ID로 저장 키를 찾은 뒤 서버가 실제 경로를 구성한다. 삭제 성공 후 trash 제거 실패는 요청을 실패시키지 않고 로그에 기록한다.

- [ ] **Step 4: API 통합 테스트 통과 확인**

Run: `uv run pytest backend/tests -q`

Expected: all backend tests pass.

- [ ] **Step 5: 이미지 API 커밋**

```powershell
git add backend/app/application backend/app/api backend/app/main.py backend/tests/api
git commit -m "feat: expose image library API"
```

### Task 5: 동시 요청 2개 업로더

**Files:**
- Create: `frontend/src/features/uploads/types.ts`
- Create: `frontend/src/features/uploads/upload-queue.ts`
- Create: `frontend/src/features/uploads/upload-dialog.tsx`
- Create: `frontend/src/features/uploads/upload-queue.test.ts`
- Create: `frontend/src/features/uploads/upload-dialog.test.tsx`

**Interfaces:**
- Produces: `uploadFiles({files, brandId, kind, productId, concurrency: 2})`, `UploadDialog`

- [ ] **Step 1: queue와 부분 성공 실패 테스트 작성**

100개 Promise를 넣어 동시에 실행 중인 요청의 최댓값이 2인지 검증한다. 성공·중복·손상·용량 초과 결과가 원래 파일 순서로 남고, 한 실패가 나머지를 취소하지 않는지 테스트한다.

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test -- --run src/features/uploads`

Expected: FAIL because upload queue is absent.

- [ ] **Step 3: queue와 dialog 구현**

dialog는 JPEG·PNG·WebP accept, 파일별 대기·업로드 중·성공·실패 상태, 전체 progress, 실패 원인과 `action`을 표시한다. 상품 상세는 `PRODUCT`와 현재 product를, 트레이 화면은 `TRAY`를 props로 고정해 사용자에게 다시 묻지 않는다. 결과는 `aria-live="polite"`로 알린다.

- [ ] **Step 4: 업로드 UI 테스트 통과 확인**

Run: `npm --prefix frontend run test -- --run src/features/uploads`

Expected: all upload tests pass.

- [ ] **Step 5: 업로더 커밋**

```powershell
git add frontend/src/features/uploads
git commit -m "feat: add bounded image upload queue"
```

### Task 6: 상품 사진과 트레이 사진 작업함

**Files:**
- Create: `frontend/src/features/images/api.ts`
- Create: `frontend/src/features/images/image-list.tsx`
- Create: `frontend/src/features/images/image-filters.tsx`
- Create: `frontend/src/pages/product-detail-page.tsx`
- Create: `frontend/src/pages/tray-images-page.tsx`
- Create: `frontend/src/pages/product-detail-page.test.tsx`
- Create: `frontend/src/pages/tray-images-page.test.tsx`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Produces: product photo list and tray inbox with cursor pagination
- Consumes: image API, `UploadDialog`, current brand

- [ ] **Step 1: 페이지 상태 실패 테스트 작성**

상품 상세의 사진 추가가 현재 product를 사용하고, 상품 사진을 같은 브랜드의 다른 활성 상품으로 옮길 수 있는지 테스트한다. 트레이 사진은 `라벨 필요`·`완료` tabs, 파일명 검색, 상품 필터, 48~64px thumbnail, 다음 페이지 loading을 제공하는지 테스트한다. 빈 목록·검색 결과 없음·100개 목록·긴 파일명도 포함한다.

- [ ] **Step 2: 실패 확인**

Run: `npm --prefix frontend run test -- --run src/pages/product-detail-page.test.tsx src/pages/tray-images-page.test.tsx`

Expected: FAIL because pages are absent.

- [ ] **Step 3: 작업함 구현**

트레이 업로드 성공 후 대표 행동은 `첫 사진 라벨링하기`다. 다만 이 업로드 단계에는 라벨링 route가 없으므로 버튼은 비활성 상태와 안내 문구로 표시하고, 다음 라벨링 편집기 단계에서 실제 route를 구현할 때 활성화한다. 삭제는 이미지 수와 향후 삭제될 박스 수를 표시하는 AlertDialog를 사용한다. 목록은 thumbnail endpoint만 요청하며 원본 endpoint를 사용하지 않는다. 200ms보다 짧은 조회는 skeleton을 표시하지 않는다.

- [ ] **Step 4: 프런트엔드와 전체 단계 검증**

Run:

```powershell
npm --prefix frontend run test -- --run
npm --prefix frontend run build
uv run pytest
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 5: 작업함 커밋**

```powershell
git add frontend/src
git commit -m "feat: add product and tray image libraries"
```
