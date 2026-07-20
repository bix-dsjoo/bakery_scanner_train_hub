from __future__ import annotations

import os
import tempfile
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageOps, UnidentifiedImageError


FORMAT_DETAILS = {
    "JPEG": ("image/jpeg", "jpg", {".jpg", ".jpeg"}),
    "MPO": ("image/jpeg", "jpg", {".jpg", ".jpeg"}),
    "PNG": ("image/png", "png", {".png"}),
    "WEBP": ("image/webp", "webp", {".webp"}),
}


class InvalidImageError(ValueError):
    pass


class UnsupportedImageError(ValueError):
    pass


@dataclass(frozen=True)
class InspectedImage:
    mime_type: str
    extension: str
    width: int
    height: int


@dataclass(frozen=True)
class Thumbnail:
    path: Path
    width: int
    height: int


class ImageProcessor:
    def inspect(self, path: Path, original_filename: str) -> InspectedImage:
        try:
            with reject_decompression_bombs():
                with Image.open(path) as image:
                    image_format = image.format
                    image.verify()
                with Image.open(path) as image:
                    image.seek(0)
                    image.load()
                    width, height = image.size
        except (
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ) as error:
            raise InvalidImageError("image exceeds the safe pixel limit") from error
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
            raise InvalidImageError("file is not a decodable image") from error

        if image_format not in FORMAT_DETAILS:
            raise UnsupportedImageError(
                "image format must be JPEG, PNG, WebP, or JPEG-compatible MPO"
            )
        mime_type, extension, accepted_suffixes = FORMAT_DETAILS[image_format]
        if Path(original_filename).suffix.lower() not in accepted_suffixes:
            raise UnsupportedImageError("filename extension does not match image content")
        return InspectedImage(
            mime_type=mime_type,
            extension=extension,
            width=width,
            height=height,
        )

    def create_thumbnail(
        self, source: Path, destination: Path, *, max_edge: int = 512
    ) -> Thumbnail:
        if max_edge <= 0:
            raise ValueError("max_edge must be positive")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        try:
            try:
                with reject_decompression_bombs():
                    with Image.open(source) as image:
                        if image.format not in FORMAT_DETAILS:
                            raise UnsupportedImageError(
                                "image format must be JPEG, PNG, WebP, or JPEG-compatible MPO"
                            )
                        image.seek(0)
                        image.load()
                        thumbnail = ImageOps.exif_transpose(image)
                        thumbnail.thumbnail(
                            (max_edge, max_edge), Image.Resampling.LANCZOS
                        )
                        if thumbnail.mode not in {"RGB", "RGBA"}:
                            mode = "RGBA" if "A" in thumbnail.getbands() else "RGB"
                            thumbnail = thumbnail.convert(mode)
                        thumbnail.save(temporary_path, format="WEBP")
                        width, height = thumbnail.size
                    self._verify_thumbnail(temporary_path)
            except UnsupportedImageError:
                raise
            except (
                Image.DecompressionBombWarning,
                Image.DecompressionBombError,
            ) as error:
                raise InvalidImageError(
                    "image exceeds the safe pixel limit"
                ) from error
            except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
                raise InvalidImageError("file is not a decodable image") from error

            self._publish_without_overwrite(temporary_path, destination)
        finally:
            temporary_path.unlink(missing_ok=True)
        return Thumbnail(path=destination, width=width, height=height)

    @staticmethod
    def _verify_thumbnail(path: Path) -> None:
        with Image.open(path) as image:
            if image.format != "WEBP":
                raise InvalidImageError("thumbnail is not WebP")
            image.verify()
        with Image.open(path) as image:
            image.load()

    @staticmethod
    def _publish_without_overwrite(source: Path, destination: Path) -> None:
        os.link(source, destination)
        source.unlink()


@contextmanager
def reject_decompression_bombs() -> Iterator[None]:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        yield
