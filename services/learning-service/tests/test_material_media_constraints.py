from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import pytest
from PIL import Image

from app.core.config import settings
from app.services import material_media_constraints as constraints_module
from app.services.material_media_constraints import MaterialMediaConstraintService


def test_image_upload_checks_actual_bytes_and_dimensions() -> None:
    service = MaterialMediaConstraintService()
    payload = BytesIO()
    Image.new("RGB", (32, 24), color="white").save(payload, format="PNG")
    payload.seek(0)

    result = service.validate_upload(
        file_object=payload,
        filename="lesson.png",
        content_type="image/png",
        # Deliberately under-report the client-declared size.
        size_bytes=1,
    )

    assert result.kind == "image"
    assert result.width == 32
    assert result.height == 24


def test_image_upload_rejects_pixel_limit(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = MaterialMediaConstraintService()
    path = tmp_path / "large.png"
    Image.new("RGB", (100, 100), color="white").save(path, format="PNG")
    monkeypatch.setattr(
        constraints_module,
        "settings",
        replace(settings, material_image_max_pixels=1000),
    )

    with pytest.raises(ValueError, match="像素"):
        service.validate_path(
            path=path,
            filename=path.name,
            content_type="image/png",
            size_bytes=path.stat().st_size,
        )


def test_video_upload_rejects_duration_limit(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = MaterialMediaConstraintService()
    path = tmp_path / "lecture.mp4"
    path.write_bytes(b"media")

    class Completed:
        returncode = 0
        stdout = str(settings.material_video_max_duration_seconds + 1)

    monkeypatch.setattr("app.services.material_media_constraints.subprocess.run", lambda *args, **kwargs: Completed())

    with pytest.raises(ValueError, match="视频时长不能超过"):
        service.validate_path(
            path=path,
            filename=path.name,
            content_type="video/mp4",
            size_bytes=path.stat().st_size,
        )


def test_svg_upload_is_validated_without_rasterizing(tmp_path) -> None:
    service = MaterialMediaConstraintService()
    path = tmp_path / "diagram.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480"><text>AI</text></svg>', encoding="utf-8")

    result = service.validate_path(
        path=path,
        filename=path.name,
        content_type="image/svg+xml",
        size_bytes=path.stat().st_size,
    )

    assert result.as_metadata() == {"kind": "image", "width": 640, "height": 480}
