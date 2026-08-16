from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException

from app.api import material_access as material_access_module
from app.services import material_access_session as material_session_module
from app.services import storage_service as storage_module
from app.services.storage_service import MaterialContentSource, StorageService, validate_material_proxy_access_url


def _patch_local_material_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_settings = SimpleNamespace(
        object_storage_provider="local",
        learning_material_public_base_url="/materials",
        material_access_url_expires_seconds=300,
        public_id_secret="test-public-id-secret-for-material-access",
        material_root_path=tmp_path,
    )
    monkeypatch.setattr(storage_module, "settings", fake_settings)
    monkeypatch.setattr(material_access_module, "settings", fake_settings)
    monkeypatch.setattr(material_session_module, "settings", fake_settings)


def test_local_material_access_url_is_signed_and_previewed_inline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_local_material_settings(monkeypatch, tmp_path)
    object_key = "course-one/module-one/notes.txt"
    material_path = tmp_path / object_key
    material_path.parent.mkdir(parents=True)
    material_path.write_text("signed material body", encoding="utf-8")

    url = StorageService().get_material_access_url(metadata={"objectKey": object_key}, fallback_url=None)

    assert url.startswith("/materials/course-one/module-one/notes.txt?")
    assert "expires=" in url
    assert "signature=" in url
    route_path = url.split("?", 1)[0].removeprefix("/materials/")
    query = dict(part.split("=", 1) for part in url.split("?", 1)[1].split("&"))
    response = material_access_module.download_local_material(
        object_path=route_path,
        expires=int(query["expires"]),
        signature=query["signature"],
    )
    assert Path(response.path) == material_path.resolve()
    assert response.headers["content-disposition"].startswith("inline;")


def test_local_material_access_can_request_an_attachment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_local_material_settings(monkeypatch, tmp_path)
    object_key = "course-one/module-one/notes.txt"
    material_path = tmp_path / object_key
    material_path.parent.mkdir(parents=True)
    material_path.write_text("signed material body", encoding="utf-8")

    url = StorageService().get_material_access_url(metadata={"objectKey": object_key}, fallback_url=None)
    route_path = url.split("?", 1)[0].removeprefix("/materials/")
    query = dict(part.split("=", 1) for part in url.split("?", 1)[1].split("&"))

    response = material_access_module.download_local_material(
        object_path=route_path,
        expires=int(query["expires"]),
        signature=query["signature"],
        download=True,
    )

    assert response.headers["content-disposition"].startswith("attachment;")


def test_local_material_access_keeps_unsafe_inline_types_as_attachments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_local_material_settings(monkeypatch, tmp_path)
    object_key = "course-one/module-one/diagram.svg"
    material_path = tmp_path / object_key
    material_path.parent.mkdir(parents=True)
    material_path.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")

    url = StorageService().get_material_access_url(metadata={"objectKey": object_key}, fallback_url=None)
    route_path = url.split("?", 1)[0].removeprefix("/materials/")
    query = dict(part.split("=", 1) for part in url.split("?", 1)[1].split("&"))

    response = material_access_module.download_local_material(
        object_path=route_path,
        expires=int(query["expires"]),
        signature=query["signature"],
    )

    assert response.headers["content-disposition"].startswith("attachment;")


def test_local_material_access_rejects_expired_or_tampered_urls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_local_material_settings(monkeypatch, tmp_path)
    object_key = "course-one/module-one/notes.txt"
    material_path = tmp_path / object_key
    material_path.parent.mkdir(parents=True)
    material_path.write_text("signed material body", encoding="utf-8")

    with pytest.raises(HTTPException) as expired_info:
        material_access_module.download_local_material(
            object_path=object_key,
            expires=1,
            signature="bad",
        )
    assert expired_info.value.status_code == 403

    expires = int(time.time()) + 300
    with pytest.raises(HTTPException) as tampered_info:
        material_access_module.download_local_material(
            object_path=object_key,
            expires=expires,
            signature="bad",
        )
    assert tampered_info.value.status_code == 403


def test_local_material_access_url_rejects_path_traversal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_local_material_settings(monkeypatch, tmp_path)

    with pytest.raises(ValueError):
        StorageService().get_material_access_url(metadata={"objectKey": "../secret.txt"}, fallback_url=None)


def test_material_proxy_url_hides_storage_key_and_binds_the_authenticated_subject(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_local_material_settings(monkeypatch, tmp_path)

    url = StorageService().get_material_proxy_access_url(
        material_uuid="material-public-id",
        user_id=7,
        identity="Learner",
    )

    assert url.startswith("/materials/access/material-public-id?")
    assert "course-one" not in url
    assert "notes.txt" not in url
    query = parse_qs(urlparse(url).query)
    grant = validate_material_proxy_access_url(
        material_uuid="material-public-id",
        user_id=int(query["userId"][0]),
        identity=query["identity"][0],
        expires=int(query["expires"][0]),
        signature=query["signature"][0],
        download=False,
    )

    assert grant.user_id == 7
    assert grant.identity == "Learner"

    with pytest.raises(ValueError):
        validate_material_proxy_access_url(
            material_uuid="different-material",
            user_id=7,
            identity="Learner",
            expires=int(query["expires"][0]),
            signature=query["signature"][0],
            download=False,
        )


def test_material_proxy_rechecks_catalog_authorization_before_file_delivery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_local_material_settings(monkeypatch, tmp_path)
    material_path = tmp_path / "course-one" / "module-one" / "notes.txt"
    material_path.parent.mkdir(parents=True)
    material_path.write_text("protected material", encoding="utf-8")

    checked_subjects: list[dict] = []

    class FakeCatalog:
        def __init__(self, _session) -> None:
            pass

        def get_accessible_material_by_uuid(self, *, material_uuid: str, current_user: dict):
            checked_subjects.append({"material_uuid": material_uuid, **current_user})
            return SimpleNamespace(metadata_json={"objectKey": "course-one/module-one/notes.txt"})

    source = SimpleNamespace(
        provider="local",
        absolute_path=material_path,
        filename="notes.txt",
        content_type="text/plain",
        size_bytes=material_path.stat().st_size,
    )
    fake_storage = SimpleNamespace(resolve_managed_material_content=lambda **_kwargs: source)
    monkeypatch.setattr(material_access_module, "CourseCatalogService", FakeCatalog)
    monkeypatch.setattr(material_access_module, "StorageService", lambda: fake_storage)
    monkeypatch.setattr(
        material_access_module,
        "IdentityUserClient",
        lambda: SimpleNamespace(
            lookup_users_by_ids=lambda **_kwargs: {
                7: {"accountStatus": "active", "roleCodes": ["learner"]}
            }
        ),
    )

    expires = int(time.time()) + 300
    signature = storage_module.sign_material_proxy_access_url(
        material_uuid="material-public-id",
        user_id=7,
        identity="Learner",
        expires_at=expires,
        download=False,
    )
    material_access_session = material_session_module.create_material_access_session(
        user_id=7,
        identity="Learner",
        expires_at=expires,
    )
    response = material_access_module.proxy_material_access(
        material_uuid="material-public-id",
        request=SimpleNamespace(headers={}),
        user_id=7,
        identity="Learner",
        expires=expires,
        signature=signature,
        download=False,
        material_access_session=material_access_session,
        session=SimpleNamespace(),
    )

    assert checked_subjects == [{"material_uuid": "material-public-id", "id": 7, "identity": "Learner"}]
    assert Path(response.path) == material_path.resolve()
    assert response.headers["cache-control"] == "private, no-store"


def test_material_proxy_rejects_a_session_after_the_identity_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_local_material_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(
        material_access_module,
        "IdentityUserClient",
        lambda: SimpleNamespace(
            lookup_users_by_ids=lambda **_kwargs: {
                7: {"accountStatus": "disabled", "roleCodes": ["learner"]}
            }
        ),
    )
    expires = int(time.time()) + 300
    signature = storage_module.sign_material_proxy_access_url(
        material_uuid="material-public-id",
        user_id=7,
        identity="Learner",
        expires_at=expires,
        download=False,
    )
    material_access_session = material_session_module.create_material_access_session(
        user_id=7,
        identity="Learner",
        expires_at=expires,
    )

    with pytest.raises(HTTPException) as exc_info:
        material_access_module.proxy_material_access(
            material_uuid="material-public-id",
            request=SimpleNamespace(headers={}),
            user_id=7,
            identity="Learner",
            expires=expires,
            signature=signature,
            download=False,
            material_access_session=material_access_session,
            session=SimpleNamespace(),
        )

    assert exc_info.value.status_code == 403


def test_minio_proxy_streams_single_byte_range_without_exposing_a_signed_object_url() -> None:
    class FakeUpstreamResponse:
        def __init__(self) -> None:
            self.closed = False
            self.released = False

        def stream(self, _chunk_size: int):
            yield b"bcd"

        def close(self) -> None:
            self.closed = True

        def release_conn(self) -> None:
            self.released = True

    upstream = FakeUpstreamResponse()
    open_calls: list[dict] = []
    fake_storage = SimpleNamespace(
        open_managed_material_stream=lambda **kwargs: open_calls.append(kwargs) or upstream,
    )
    source = MaterialContentSource(
        provider="minio",
        bucket="learning-materials",
        object_key="course-one/module-one/notes.txt",
        filename="notes.txt",
        content_type="text/plain",
        size_bytes=10,
    )

    response = material_access_module._deliver_managed_material(
        storage=fake_storage,
        source=source,
        download=False,
        range_header="bytes=1-3",
    )

    async def collect_body() -> bytes:
        return b"".join([chunk async for chunk in response.body_iterator])

    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 1-3/10"
    assert response.headers["content-length"] == "3"
    assert asyncio.run(collect_body()) == b"bcd"
    assert open_calls == [{"source": source, "offset": 1, "length": 3}]
    assert upstream.closed is True
    assert upstream.released is True


class _FakeMinioClient:
    def presigned_get_object(self, bucket: str, object_key: str, *, expires):
        return (
            f"http://minio:9000/{bucket}/{object_key}"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=abc123"
        )

    def get_presigned_url(
        self,
        method: str,
        bucket: str,
        object_key: str,
        *,
        expires,
        extra_query_params: dict[str, str],
    ):
        return (
            f"http://minio:9000/{bucket}/{object_key}"
            f"?uploadId={extra_query_params['uploadId']}"
            f"&partNumber={extra_query_params['partNumber']}"
            f"&X-Amz-Signature=put123"
        )


def _patch_minio_material_settings(monkeypatch: pytest.MonkeyPatch, *, public_base_url: str) -> None:
    fake_settings = SimpleNamespace(
        object_storage_provider="minio",
        minio_bucket="learning-materials",
        minio_public_base_url=public_base_url,
        minio_signed_url_expires_seconds=300,
        minio_multipart_part_url_expires_seconds=300,
    )
    monkeypatch.setattr(storage_module, "settings", fake_settings)
    monkeypatch.setattr(StorageService, "_build_minio_client", lambda self: _FakeMinioClient())


def test_minio_material_access_url_rewrites_internal_host_to_public_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_minio_material_settings(monkeypatch, public_base_url="/learning-materials")

    url = StorageService().get_material_access_url(
        metadata={"bucket": "learning-materials", "objectKey": "course-one/module-one/notes.pdf"},
        fallback_url=None,
    )

    assert url.startswith("/learning-materials/course-one/module-one/notes.pdf?")
    assert "X-Amz-Signature=abc123" in url
    assert "minio:9000" not in url


def test_minio_material_access_url_preserves_internal_url_when_public_base_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_minio_material_settings(monkeypatch, public_base_url="")

    url = StorageService().get_material_access_url(
        metadata={"bucket": "learning-materials", "objectKey": "course-one/module-one/notes.pdf"},
        fallback_url=None,
    )

    assert url.startswith("http://minio:9000/learning-materials/course-one/module-one/notes.pdf?")
    assert "X-Amz-Signature=abc123" in url


def test_minio_multipart_part_upload_url_rewrites_internal_host_to_public_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_minio_material_settings(monkeypatch, public_base_url="/learning-materials")

    url = StorageService().get_multipart_part_upload_url(
        bucket="learning-materials",
        object_key="course-one/module-one/big notes.pdf",
        upload_id="upload-123",
        part_number=3,
    )

    assert url.startswith("/learning-materials/course-one/module-one/big%20notes.pdf?")
    assert "uploadId=upload-123" in url
    assert "partNumber=3" in url
    assert "X-Amz-Signature=put123" in url
    assert "minio:9000" not in url
