from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageOps


def ensure_parent_dir(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def resize_image_bytes(
    image_bytes: bytes,
    width: int,
    height: int,
    *,
    image_format: str = "JPEG",
    quality: int = 90,
) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as image:
        normalized = ImageOps.exif_transpose(image).convert("RGB")
        resized = ImageOps.fit(
            normalized,
            (int(width), int(height)),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        output = io.BytesIO()
        resized.save(output, format=image_format, quality=quality)
        return output.getvalue()


def save_resized_image(
    image_bytes: bytes,
    output_path: str | Path,
    width: int,
    height: int,
    *,
    image_format: str = "JPEG",
    quality: int = 90,
) -> Path:
    target = ensure_parent_dir(output_path)
    target.write_bytes(
        resize_image_bytes(
            image_bytes,
            width,
            height,
            image_format=image_format,
            quality=quality,
        )
    )
    return target


def image_file_to_resized_bytes(
    image_path: str | Path,
    width: int,
    height: int,
    *,
    image_format: str = "JPEG",
    quality: int = 90,
) -> bytes:
    return resize_image_bytes(
        Path(image_path).read_bytes(),
        width,
        height,
        image_format=image_format,
        quality=quality,
    )


def decode_base64_image(data: str) -> bytes:
    payload = data.split(",", 1)[-1].strip()
    if not payload:
        raise ValueError("Empty base64 image payload")
    return base64.b64decode(payload)
