# JPEG 기반 MPO 업로드 호환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `.jpg` 또는 `.jpeg`로 제공된 JPEG 기반 MPO를 원본 그대로 저장하고 첫 번째 프레임을 기존 JPEG 업로드 흐름에서 사용한다.

**Architecture:** `ImageProcessor`가 Pillow 포맷 `MPO`를 JPEG 메타데이터로 정규화하고 검사와 썸네일 생성에서 첫 번째 프레임을 명시적으로 선택한다. 업로드 서비스와 API 계약은 변경하지 않으며, 합성 MPO를 사용하는 인프라·사용 사례 테스트로 원본 보존과 상태 전이를 검증한다.

**Tech Stack:** Python 3.13, Pillow, FastAPI application service, pytest

## Global Constraints

- `.jpg` 또는 `.jpeg`로 제공된 MPO만 JPEG 호환 파일로 허용한다.
- 원본 바이트와 원본 기준 SHA-256을 변경하지 않는다.
- 저장 메타데이터는 `mime_type=image/jpeg`, 저장 확장자 `jpg`를 사용한다.
- 이미지 크기와 썸네일은 첫 번째 프레임을 기준으로 한다.
- `.mpo` 확장자는 지원하지 않는다.
- JPEG, PNG, WebP의 기존 검증과 확장자 위장 차단을 유지한다.
- 새 런타임 의존성을 추가하지 않는다.

---

### Task 1: MPO를 JPEG 호환 업로드로 처리

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/infrastructure/test_image_processor.py`
- Modify: `backend/tests/application/test_image_upload.py`
- Modify: `backend/app/infrastructure/image_processor.py`

**Interfaces:**
- Consumes: `ImageProcessor.inspect(path: Path, original_filename: str) -> InspectedImage`, `ImageProcessor.create_thumbnail(source: Path, destination: Path, *, max_edge: int = 512) -> Thumbnail`
- Produces: `MPO` 입력을 `InspectedImage(mime_type="image/jpeg", extension="jpg", width=<첫 프레임 너비>, height=<첫 프레임 높이>)`로 정규화하는 기존 인터페이스

- [ ] **Step 1: 테스트 전용 합성 MPO fixture 작성**

`backend/tests/conftest.py`에 다음 import와 fixture를 추가한다.

```python
from io import BytesIO

from PIL import Image


@pytest.fixture
def mpo_bytes() -> bytes:
    output = BytesIO()
    primary = Image.new("RGB", (40, 20), "red")
    exif = primary.getexif()
    exif[274] = 6
    auxiliary = Image.new("L", (10, 10), 128)
    primary.save(
        output,
        format="MPO",
        save_all=True,
        append_images=[auxiliary],
        exif=exif,
    )
    return output.getvalue()
```

- [ ] **Step 2: 이미지 검사와 썸네일의 실패 테스트 작성**

`backend/tests/infrastructure/test_image_processor.py`에 다음 테스트를 추가한다.

```python
def test_inspect_accepts_jpeg_named_mpo_as_jpeg(
    tmp_path: Path, mpo_bytes: bytes
) -> None:
    source = tmp_path / "iphone.jpg"
    source.write_bytes(mpo_bytes)

    result = ImageProcessor().inspect(source, source.name)

    assert result.mime_type == "image/jpeg"
    assert result.extension == "jpg"
    assert (result.width, result.height) == (40, 20)


def test_inspect_rejects_mpo_filename_extension(
    tmp_path: Path, mpo_bytes: bytes
) -> None:
    source = tmp_path / "iphone.mpo"
    source.write_bytes(mpo_bytes)

    with pytest.raises(UnsupportedImageError):
        ImageProcessor().inspect(source, source.name)


def test_inspect_rejects_corrupt_mpo(tmp_path: Path, mpo_bytes: bytes) -> None:
    source = tmp_path / "corrupt-mpo.jpg"
    source.write_bytes(mpo_bytes[:64])

    with pytest.raises(InvalidImageError):
        ImageProcessor().inspect(source, source.name)


def test_create_thumbnail_uses_oriented_first_mpo_frame(
    tmp_path: Path, mpo_bytes: bytes
) -> None:
    source = tmp_path / "iphone.jpg"
    output = tmp_path / "thumbnail"
    source.write_bytes(mpo_bytes)

    result = ImageProcessor().create_thumbnail(source, output)

    assert (result.width, result.height) == (20, 40)
    inspected = ImageProcessor().inspect(output, "thumbnail.webp")
    assert (inspected.width, inspected.height) == (20, 40)
```

- [ ] **Step 3: 업로드 원본 보존과 종류별 상태의 실패 테스트 작성**

`backend/tests/application/test_image_upload.py`에 다음 테스트를 추가한다.

```python
@pytest.mark.parametrize(
    ("kind", "expected_status"),
    [
        (ImageKind.PRODUCT, LabelingStatus.COMPLETED),
        (ImageKind.TRAY, LabelingStatus.UNLABELED),
    ],
)
def test_mpo_jpeg_upload_preserves_original_and_existing_status_rules(
    session: Session,
    settings: Settings,
    catalog: CatalogService,
    mpo_bytes: bytes,
    kind: ImageKind,
    expected_status: LabelingStatus,
) -> None:
    brand = catalog.create_brand(f"MPO {kind.value} Bakery")
    product_id = None
    if kind == ImageKind.PRODUCT:
        product = catalog.create_product(brand.id, "MPO-001", "MPO 빵")
        product_id = product.id
    session.commit()

    record = make_service(session, settings).upload(
        brand.id,
        kind,
        product_id,
        "iphone.jpg",
        io.BytesIO(mpo_bytes),
    )

    original = LocalFileStorage(settings).resolve("originals", record.storage_key)
    assert original.read_bytes() == mpo_bytes
    assert record.mime_type == "image/jpeg"
    assert (record.width, record.height) == (40, 20)
    assert record.labeling_status == expected_status
```

- [ ] **Step 4: 실패가 MPO 미지원 때문인지 확인**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/infrastructure/test_image_processor.py backend/tests/application/test_image_upload.py -k mpo -q
```

Expected: `.jpg` MPO 검사와 업로드가 `UnsupportedImageError` 또는 `IMAGE_UNSUPPORTED`로 실패하고, `.mpo` 확장자 거부 및 손상 MPO 테스트는 통과한다.

- [ ] **Step 5: 최소 MPO 정규화 구현**

`backend/app/infrastructure/image_processor.py`의 `FORMAT_DETAILS`에 MPO를 JPEG 호환 포맷으로 추가한다.

```python
FORMAT_DETAILS = {
    "JPEG": ("image/jpeg", "jpg", {".jpg", ".jpeg"}),
    "MPO": ("image/jpeg", "jpg", {".jpg", ".jpeg"}),
    "PNG": ("image/png", "png", {".png"}),
    "WEBP": ("image/webp", "webp", {".webp"}),
}
```

`inspect()`의 두 번째 열기에서 첫 번째 프레임을 명시적으로 선택한다.

```python
with Image.open(path) as image:
    image.seek(0)
    image.load()
    width, height = image.size
```

`create_thumbnail()`에서도 포맷 검사 뒤 첫 번째 프레임을 명시적으로 선택한다.

```python
if image.format not in FORMAT_DETAILS:
    raise UnsupportedImageError(
        "image format must be JPEG, PNG, WebP, or JPEG-compatible MPO"
    )
image.seek(0)
image.load()
thumbnail = ImageOps.exif_transpose(image)
```

검사 오류의 사용자용 계약은 `IMAGE_UNSUPPORTED` 그대로이므로 application service와 프런트엔드는 변경하지 않는다.

- [ ] **Step 6: MPO 집중 테스트 통과 확인**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/infrastructure/test_image_processor.py backend/tests/application/test_image_upload.py -k mpo -q
```

Expected: 6 tests pass.

- [ ] **Step 7: 이미지 업로드 백엔드 회귀 테스트 실행**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/infrastructure/test_image_processor.py backend/tests/application/test_image_upload.py backend/tests/api/test_images_api.py -q
```

Expected: all selected tests pass without warnings introduced by this change.

- [ ] **Step 8: 전체 품질 게이트 실행**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 9: 구현 커밋**

```powershell
git add backend/tests/conftest.py backend/tests/infrastructure/test_image_processor.py backend/tests/application/test_image_upload.py backend/app/infrastructure/image_processor.py docs/superpowers/plans/2026-07-20-mpo-jpeg-upload.md
git commit -m "fix: accept JPEG-compatible MPO uploads"
```

## Completion

- [x] Task 1 completed on 2026-07-20.
