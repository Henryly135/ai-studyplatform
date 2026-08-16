from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from xml.etree import ElementTree

from PIL import Image, UnidentifiedImageError

from app.core.config import settings


_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mpeg", ".mpg"}
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac", ".opus", ".wma"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}
_ARCHIVE_EXTENSIONS = {".zip"}
_OFFICE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".odt",
    ".odp",
    ".ods",
}


@dataclass(frozen=True)
class MaterialMediaValidation:
    kind: str
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None

    def as_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {"kind": self.kind}
        if self.duration_seconds is not None:
            metadata["durationSeconds"] = round(self.duration_seconds, 3)
        if self.width is not None:
            metadata["width"] = self.width
        if self.height is not None:
            metadata["height"] = self.height
        return metadata


class MaterialMediaConstraintService:
    """Validate resource cost before a material is made visible to learners."""

    def classify(self, *, filename: str, content_type: str | None) -> str:
        normalized_content_type = (content_type or "").strip().lower()
        extension = Path(filename or "").suffix.lower()
        if normalized_content_type.startswith("video/") or extension in _VIDEO_EXTENSIONS:
            return "video"
        if normalized_content_type.startswith("audio/") or extension in _AUDIO_EXTENSIONS:
            return "audio"
        if normalized_content_type.startswith("image/") or extension in _IMAGE_EXTENSIONS:
            return "image"
        if normalized_content_type in {"application/zip", "application/x-zip-compressed"} or extension in _ARCHIVE_EXTENSIONS:
            return "archive"
        if (
            extension in _OFFICE_EXTENSIONS
            or "word" in normalized_content_type
            or "spreadsheet" in normalized_content_type
            or "presentation" in normalized_content_type
        ):
            return "office"
        return "document"

    def validate_upload(
        self,
        *,
        file_object: BinaryIO,
        filename: str,
        content_type: str | None,
        size_bytes: int | None,
    ) -> MaterialMediaValidation:
        kind = self.classify(filename=filename, content_type=content_type)
        self._validate_size(kind=kind, size_bytes=size_bytes)
        if kind not in {"video", "audio", "image"}:
            return MaterialMediaValidation(kind=kind)

        temporary_path = self._copy_to_temporary_file(file_object=file_object, filename=filename)
        try:
            # UploadFile.size can reflect a client-provided header.  Validate
            # the bytes that were actually received so a forged size cannot
            # bypass media cost limits.
            actual_size_bytes = temporary_path.stat().st_size
            return self.validate_path(
                path=temporary_path,
                filename=filename,
                content_type=content_type,
                size_bytes=actual_size_bytes,
            )
        finally:
            temporary_path.unlink(missing_ok=True)

    def validate_declared_size(
        self,
        *,
        filename: str,
        content_type: str | None,
        size_bytes: int,
    ) -> MaterialMediaValidation:
        kind = self.classify(filename=filename, content_type=content_type)
        self._validate_size(kind=kind, size_bytes=size_bytes)
        return MaterialMediaValidation(kind=kind)

    def validate_path(
        self,
        *,
        path: Path,
        filename: str,
        content_type: str | None,
        size_bytes: int | None,
    ) -> MaterialMediaValidation:
        kind = self.classify(filename=filename, content_type=content_type)
        self._validate_size(kind=kind, size_bytes=size_bytes)
        if kind in {"video", "audio"}:
            duration_seconds = self._read_duration_seconds(path=path, filename=filename)
            max_duration = (
                settings.material_video_max_duration_seconds
                if kind == "video"
                else settings.material_audio_max_duration_seconds
            )
            if duration_seconds > max_duration + 0.5:
                unit = "视频" if kind == "video" else "音频"
                raise ValueError(f"{unit}时长不能超过 {max_duration // 60} 分钟。")
            return MaterialMediaValidation(kind=kind, duration_seconds=duration_seconds)
        if kind == "image":
            if Path(filename).suffix.lower() == ".svg" or (content_type or "").strip().lower() == "image/svg+xml":
                return self._validate_svg(path=path, filename=filename)
            return self._validate_image(path=path, filename=filename)
        return MaterialMediaValidation(kind=kind)

    def _validate_size(self, *, kind: str, size_bytes: int | None) -> None:
        if size_bytes is None:
            return
        max_size = {
            "video": settings.material_video_max_bytes,
            "audio": settings.material_audio_max_bytes,
            "image": settings.material_image_max_bytes,
            "office": settings.material_office_max_bytes,
            "archive": settings.material_archive_max_bytes,
        }.get(kind)
        if max_size is not None and size_bytes > max_size:
            label = {
                "video": "视频",
                "audio": "音频",
                "image": "图片",
                "office": "Office 文件",
                "archive": "压缩包",
            }[kind]
            raise ValueError(f"{label}大小不能超过 {max_size // (1024 * 1024)} MB。")

    def _validate_image(self, *, path: Path, filename: str) -> MaterialMediaValidation:
        try:
            with Image.open(path) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > settings.material_image_max_pixels:
                    raise ValueError(
                        f"图片像素不能超过 {settings.material_image_max_pixels:,}。"
                    )
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"无法读取图片文件 {Path(filename).name}。") from exc
        return MaterialMediaValidation(kind="image", width=width, height=height)

    def _validate_svg(self, *, path: Path, filename: str) -> MaterialMediaValidation:
        try:
            root = ElementTree.parse(path).getroot()
            if root.tag.rsplit("}", 1)[-1].lower() != "svg":
                raise ValueError("not an SVG document")
            view_box = (root.attrib.get("viewBox") or root.attrib.get("viewbox") or "").replace(",", " ").split()
            if len(view_box) == 4:
                width, height = float(view_box[2]), float(view_box[3])
            else:
                width = self._svg_dimension(root.attrib.get("width"))
                height = self._svg_dimension(root.attrib.get("height"))
            width = max(1, int(round(width or 1)))
            height = max(1, int(round(height or 1)))
            if width * height > settings.material_image_max_pixels:
                raise ValueError(f"图片像素不能超过 {settings.material_image_max_pixels:,}。")
            return MaterialMediaValidation(kind="image", width=width, height=height)
        except ValueError:
            raise
        except (ElementTree.ParseError, OSError) as exc:
            raise ValueError(f"无法读取图片文件 {Path(filename).name}。") from exc

    @staticmethod
    def _svg_dimension(value: str | None) -> float | None:
        if not value:
            return None
        numeric = "".join(character for character in value.strip() if character.isdigit() or character in ".-")
        try:
            return float(numeric) if numeric else None
        except ValueError:
            return None

    def _read_duration_seconds(self, *, path: Path, filename: str) -> float:
        try:
            completed = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("媒体时长校验服务不可用，请联系管理员。") from exc
        if completed.returncode != 0:
            raise ValueError(f"无法读取媒体文件 {Path(filename).name} 的时长。")
        try:
            duration_seconds = float(completed.stdout.strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"无法读取媒体文件 {Path(filename).name} 的时长。") from exc
        if duration_seconds < 0:
            raise ValueError(f"媒体文件 {Path(filename).name} 的时长无效。")
        return duration_seconds

    def _copy_to_temporary_file(self, *, file_object: BinaryIO, filename: str) -> Path:
        suffix = Path(filename or "material").suffix[:16]
        temporary_file = tempfile.NamedTemporaryFile(prefix="material-validate-", suffix=suffix, delete=False)
        temporary_path = Path(temporary_file.name)
        try:
            current_position = file_object.tell()
            file_object.seek(0)
            shutil.copyfileobj(file_object, temporary_file, length=1024 * 1024)
            file_object.seek(current_position)
            temporary_file.flush()
            return temporary_path
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        finally:
            temporary_file.close()
