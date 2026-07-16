from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


FORMAT_DETAILS = {
    "JPEG": ("image/jpeg", "jpg", {".jpg", ".jpeg"}),
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
            with Image.open(path) as image:
                image_format = image.format
                image.verify()
            with Image.open(path) as image:
                image.load()
                width, height = image.size
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
            raise InvalidImageError("file is not a decodable image") from error

        if image_format not in FORMAT_DETAILS:
            raise UnsupportedImageError("image format must be JPEG, PNG, or WebP")
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
        try:
            with Image.open(source) as image:
                if image.format not in FORMAT_DETAILS:
                    raise UnsupportedImageError(
                        "image format must be JPEG, PNG, or WebP"
                    )
                image.load()
                thumbnail = ImageOps.exif_transpose(image)
                thumbnail.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                if thumbnail.mode not in {"RGB", "RGBA"}:
                    thumbnail = thumbnail.convert("RGBA" if "A" in thumbnail.getbands() else "RGB")
                thumbnail.save(destination, format="WEBP")
                width, height = thumbnail.size
        except UnsupportedImageError:
            destination.unlink(missing_ok=True)
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
            destination.unlink(missing_ok=True)
            raise InvalidImageError("file is not a decodable image") from error
        return Thumbnail(path=destination, width=width, height=height)
