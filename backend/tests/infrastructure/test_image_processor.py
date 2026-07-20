from pathlib import Path

import pytest
from PIL import Image

from backend.app.infrastructure.image_processor import (
    ImageProcessor,
    InvalidImageError,
    UnsupportedImageError,
)


FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.mark.parametrize(
    ("filename", "mime_type", "extension"),
    [
        ("valid.jpg", "image/jpeg", "jpg"),
        ("valid.png", "image/png", "png"),
        ("valid.webp", "image/webp", "webp"),
    ],
)
def test_inspect_decodes_supported_image_content(
    filename: str, mime_type: str, extension: str
) -> None:
    result = ImageProcessor().inspect(FIXTURES / filename, filename)

    assert result.mime_type == mime_type
    assert result.extension == extension
    assert result.width == 640
    assert result.height == 320


def test_inspect_rejects_corrupt_image() -> None:
    with pytest.raises(InvalidImageError):
        ImageProcessor().inspect(FIXTURES / "corrupt.jpg", "corrupt.jpg")


def test_inspect_rejects_extension_disguised_as_supported_image() -> None:
    with pytest.raises(UnsupportedImageError):
        ImageProcessor().inspect(FIXTURES / "valid.png", "disguised.jpg")


def test_inspect_rejects_unsupported_extension_even_for_valid_content() -> None:
    with pytest.raises(UnsupportedImageError):
        ImageProcessor().inspect(FIXTURES / "valid.jpg", "valid.gif")


def test_create_thumbnail_writes_webp_with_long_edge_at_most_512(
    tmp_path: Path,
) -> None:
    output = tmp_path / "thumbnail.tmp"

    result = ImageProcessor().create_thumbnail(FIXTURES / "valid.jpg", output)

    inspected = ImageProcessor().inspect(output, "thumbnail.webp")
    assert inspected.mime_type == "image/webp"
    assert (inspected.width, inspected.height) == (512, 256)
    assert result.path == output
    assert result.width == 512
    assert result.height == 256


def test_create_thumbnail_applies_exif_orientation(tmp_path: Path) -> None:
    from PIL import Image

    source = tmp_path / "rotated.jpg"
    output = tmp_path / "rotated-thumbnail"
    image = Image.new("RGB", (40, 20), "orange")
    exif = image.getexif()
    exif[274] = 6
    image.save(source, exif=exif)

    ImageProcessor().create_thumbnail(source, output)

    inspected = ImageProcessor().inspect(output, "thumbnail.webp")
    assert (inspected.width, inspected.height) == (20, 40)


def test_create_thumbnail_removes_partial_output_on_failure(tmp_path: Path) -> None:
    output = tmp_path / "thumbnail"

    with pytest.raises(InvalidImageError):
        ImageProcessor().create_thumbnail(FIXTURES / "corrupt.jpg", output)

    assert not output.exists()


@pytest.mark.parametrize("max_pixels", [150_000, 100_000])
def test_inspect_rejects_decompression_bombs(
    monkeypatch: pytest.MonkeyPatch, max_pixels: int
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", max_pixels)

    with pytest.raises(InvalidImageError, match="safe pixel limit"):
        ImageProcessor().inspect(FIXTURES / "valid.jpg", "valid.jpg")


@pytest.mark.parametrize("max_pixels", [150_000, 100_000])
def test_create_thumbnail_rejects_decompression_bombs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, max_pixels: int
) -> None:
    output = tmp_path / "thumbnail"
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", max_pixels)

    with pytest.raises(InvalidImageError, match="safe pixel limit"):
        ImageProcessor().create_thumbnail(FIXTURES / "valid.jpg", output)

    assert not output.exists()


def test_create_thumbnail_preserves_existing_destination(tmp_path: Path) -> None:
    output = tmp_path / "thumbnail"
    output.write_bytes(b"existing thumbnail")

    with pytest.raises(FileExistsError):
        ImageProcessor().create_thumbnail(FIXTURES / "valid.jpg", output)

    assert output.read_bytes() == b"existing thumbnail"
    assert list(tmp_path.glob(".thumbnail.*.tmp")) == []


def test_create_thumbnail_cleans_request_temp_after_unexpected_save_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class UnexpectedSaveFailure(BaseException):
        pass

    output = tmp_path / "thumbnail"
    output.write_bytes(b"existing thumbnail")

    def fail_after_partial_write(_image, destination, **_kwargs) -> None:
        Path(destination).write_bytes(b"partial thumbnail")
        raise UnexpectedSaveFailure

    monkeypatch.setattr(Image.Image, "save", fail_after_partial_write)

    with pytest.raises(UnexpectedSaveFailure):
        ImageProcessor().create_thumbnail(FIXTURES / "valid.jpg", output)

    assert output.read_bytes() == b"existing thumbnail"
    assert list(tmp_path.glob(".thumbnail.*.tmp")) == []
