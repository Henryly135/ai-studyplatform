from io import BytesIO
from types import SimpleNamespace
import shlex
import sys

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.core.config import settings
from app.services.course_management_service import CourseManagementService
from app.services.module_material_service import ModuleMaterialService
from app.services import upload_scan_service as upload_scan_module
from app.services.upload_scan_service import EICAR_TEST_SIGNATURE, UploadScanFailure, UploadScanService


def _service() -> ModuleMaterialService:
    return ModuleMaterialService(session=object())


def _upload(
    *,
    filename: str,
    content_type: str | None,
    size: int | None = None,
    content: bytes = b"x",
) -> UploadFile:
    headers = Headers({"content-type": content_type}) if content_type else Headers({})
    resolved_size = len(content) if size is None else size
    return UploadFile(file=BytesIO(content), size=resolved_size, filename=filename, headers=headers)


def test_standard_upload_rejects_unsupported_material_content_type():
    service = _service()
    upload = _upload(filename="payload.exe", content_type="application/x-msdownload")

    with pytest.raises(HTTPException) as exc_info:
        service._validate_upload_file(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INVALID_REQUEST"
    assert exc_info.value.detail["message"] == "Unsupported material file type"


def test_standard_upload_rejects_files_over_configured_size_limit():
    service = _service()
    upload = _upload(
        filename="large.pdf",
        content_type="application/pdf",
        size=settings.max_material_upload_bytes + 1,
    )

    with pytest.raises(HTTPException) as exc_info:
        service._validate_upload_file(upload)

    assert exc_info.value.status_code == 400
    assert "File is too large for standard upload" in exc_info.value.detail["message"]


def test_multipart_upload_rejects_unsupported_content_type():
    service = _service()

    with pytest.raises(HTTPException) as exc_info:
        service._validate_multipart_upload_request(
            filename="payload.exe",
            content_type="application/x-msdownload",
            size_bytes=1,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["message"] == "Unsupported material file type"


def test_multipart_upload_rejects_files_over_configured_size_limit():
    service = _service()

    with pytest.raises(HTTPException) as exc_info:
        service._validate_multipart_upload_request(
            filename="lecture.mp4",
            content_type="video/mp4",
            size_bytes=settings.max_multipart_material_upload_bytes + 1,
        )

    assert exc_info.value.status_code == 400
    assert "Maximum multipart material upload size" in exc_info.value.detail["message"]


def test_material_upload_accepts_known_document_and_media_types():
    service = _service()

    service._validate_upload_file(_upload(filename="notes.pdf", content_type="application/pdf"))
    service._validate_upload_file(_upload(filename="clip.mp4", content_type="video/mp4"))
    service._validate_upload_file(_upload(filename="outline.md", content_type=None))
    service._validate_upload_file(_upload(filename="outline.yaml", content_type="application/yaml"))


def test_builtin_upload_scan_rejects_eicar_signature():
    upload = _upload(
        filename="notes.txt",
        content_type="text/plain",
        content=b"clean prefix " + EICAR_TEST_SIGNATURE + b" clean suffix",
    )

    with pytest.raises(UploadScanFailure, match="malware test signature"):
        UploadScanService().scan_upload(upload, label="notes.txt")


def test_material_upload_scan_failure_maps_to_invalid_request():
    service = _service()
    upload = _upload(
        filename="notes.txt",
        content_type="text/plain",
        content=EICAR_TEST_SIGNATURE,
    )

    with pytest.raises(HTTPException) as exc_info:
        service._scan_upload_file(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INVALID_REQUEST"
    assert "security scan" in exc_info.value.detail["message"]


def test_clean_upload_scan_restores_stream_position():
    upload = _upload(filename="notes.txt", content_type="text/plain", content=b"hello")
    upload.file.seek(2)

    result = UploadScanService().scan_upload(upload, label="notes.txt")

    assert result.status == "clean"
    assert upload.file.tell() == 2


def _patch_scan_settings(monkeypatch: pytest.MonkeyPatch, *, command: str) -> None:
    monkeypatch.setattr(
        upload_scan_module,
        "settings",
        SimpleNamespace(
            material_scan_enabled=True,
            material_scan_command=command,
            material_scan_timeout_seconds=1,
            material_scan_chunk_bytes=4096,
            material_scan_max_bytes=1024 * 1024,
        ),
    )


def test_external_upload_scan_rejects_nonzero_scanner_result(monkeypatch: pytest.MonkeyPatch):
    command = (
        f"{shlex.quote(sys.executable)} -c "
        "\"import sys; print('blocked by scanner', file=sys.stderr); sys.exit(7)\" {path}"
    )
    _patch_scan_settings(monkeypatch, command=command)
    upload = _upload(filename="notes.txt", content_type="text/plain", content=b"clean text")

    with pytest.raises(UploadScanFailure, match="blocked by scanner"):
        UploadScanService().scan_upload(upload, label="notes.txt")


def test_external_upload_scan_unavailable_fails_closed(monkeypatch: pytest.MonkeyPatch):
    _patch_scan_settings(monkeypatch, command="definitely-missing-material-scanner-binary {path}")
    upload = _upload(filename="notes.txt", content_type="text/plain", content=b"clean text")

    with pytest.raises(UploadScanFailure, match="scanner is unavailable"):
        UploadScanService().scan_upload(upload, label="notes.txt")


def test_material_service_maps_external_scanner_rejection_to_invalid_request(monkeypatch: pytest.MonkeyPatch):
    command = (
        f"{shlex.quote(sys.executable)} -c "
        "\"import sys; print('blocked by scanner', file=sys.stderr); sys.exit(7)\" {path}"
    )
    _patch_scan_settings(monkeypatch, command=command)
    service = _service()
    upload = _upload(filename="notes.txt", content_type="text/plain", content=b"clean text")

    with pytest.raises(HTTPException) as exc_info:
        service._scan_upload_file(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INVALID_REQUEST"
    assert "blocked by scanner" in exc_info.value.detail["message"]


def test_external_scan_path_uses_stored_file_path(monkeypatch: pytest.MonkeyPatch, tmp_path):
    stored_file = tmp_path / "stored.txt"
    stored_file.write_text("clean text", encoding="utf-8")
    command = (
        f"{shlex.quote(sys.executable)} -c "
        "\"import pathlib, sys; p=pathlib.Path(sys.argv[1]); "
        "sys.exit(0 if p.name == 'stored.txt' and p.read_text() == 'clean text' else 8)\" {path}"
    )
    _patch_scan_settings(monkeypatch, command=command)

    result = UploadScanService().scan_path(stored_file, label="stored.txt")

    assert result.status == "clean"
    assert result.scanner == "builtin+external"


def test_course_cover_rejects_unsupported_svg_content():
    service = CourseManagementService(session=object())
    upload = _upload(filename="cover.svg", content_type="image/svg+xml")

    with pytest.raises(HTTPException) as exc_info:
        service._validate_course_cover_upload(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["message"] == "Course cover must be a JPEG, PNG, WebP, or GIF image"


def test_course_cover_scan_rejects_malware_signature():
    service = CourseManagementService(session=object())
    upload = _upload(
        filename="cover.png",
        content_type="image/png",
        content=EICAR_TEST_SIGNATURE,
    )

    with pytest.raises(HTTPException) as exc_info:
        service._validate_course_cover_upload(upload)

    assert exc_info.value.status_code == 400
    assert "security scan" in exc_info.value.detail["message"]
