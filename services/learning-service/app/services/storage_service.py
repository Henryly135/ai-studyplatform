from __future__ import annotations

import hashlib
import hmac
import mimetypes
import posixpath
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlencode, urlparse, urlunparse

from fastapi import UploadFile
from minio.error import S3Error
from app.core.config import settings
from app.services.upload_scan_service import UploadScanResult, UploadScanService
from platform_common.ids.secret import get_public_id_secret
from platform_common.storage import (
    abort_multipart_upload,
    build_minio_client,
    build_multipart_part_upload_url,
    complete_multipart_upload,
    create_multipart_upload,
    ensure_bucket_exists,
)


def normalize_local_material_object_key(object_key: str) -> str:
    candidate = unquote(object_key or "").replace("\\", "/").strip()
    if not candidate or candidate.startswith("/") or "\x00" in candidate:
        raise ValueError("Material path is invalid")

    normalized = posixpath.normpath(candidate)
    if normalized in {".", ".."} or normalized.startswith("../"):
        raise ValueError("Material path must stay within the configured material root")
    return normalized


def sign_local_material_access_url(object_key: str, expires_at: int) -> str:
    normalized_key = normalize_local_material_object_key(object_key)
    secret = get_public_id_secret(settings.public_id_secret)
    payload = f"{normalized_key}:{expires_at}"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_local_material_access_url(object_key: str, expires: int, signature: str) -> str:
    if expires < int(time.time()):
        raise ValueError("Material access URL has expired")

    normalized_key = normalize_local_material_object_key(object_key)
    expected_signature = sign_local_material_access_url(normalized_key, expires)
    if not hmac.compare_digest(signature or "", expected_signature):
        raise ValueError("Material access URL signature is invalid")
    return normalized_key


@dataclass(frozen=True)
class StoredFile:
    provider: str
    bucket: str | None
    object_key: str
    public_url: str
    content_type: str | None
    size_bytes: int
    original_filename: str
    absolute_path: Path | None = None


@dataclass(frozen=True)
class MultipartUploadTarget:
    provider: str
    bucket: str | None
    object_key: str
    upload_id: str


@dataclass(frozen=True)
class MaterialAccessGrant:
    """A short-lived, user-bound grant used by the material delivery proxy."""

    material_uuid: str
    user_id: int
    identity: str
    expires_at: int
    download: bool


@dataclass(frozen=True)
class MaterialContentSource:
    """A managed object resolved only after the caller has passed authorization."""

    provider: str
    bucket: str | None
    object_key: str
    filename: str
    content_type: str | None
    size_bytes: int
    absolute_path: Path | None = None


def _material_proxy_signature_payload(
    *,
    material_uuid: str,
    user_id: int,
    identity: str,
    expires_at: int,
    download: bool,
) -> str:
    normalized_material_uuid = material_uuid.strip()
    normalized_identity = identity.strip()
    if not normalized_material_uuid or not normalized_identity or ":" in normalized_identity:
        raise ValueError("Material access grant is invalid")
    if user_id <= 0:
        raise ValueError("Material access grant is invalid")
    return f"{normalized_material_uuid}:{user_id}:{normalized_identity}:{expires_at}:{int(download)}"


def sign_material_proxy_access_url(
    *,
    material_uuid: str,
    user_id: int,
    identity: str,
    expires_at: int,
    download: bool,
) -> str:
    payload = _material_proxy_signature_payload(
        material_uuid=material_uuid,
        user_id=user_id,
        identity=identity,
        expires_at=expires_at,
        download=download,
    )
    secret = get_public_id_secret(settings.public_id_secret)
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_material_proxy_access_url(
    *,
    material_uuid: str,
    user_id: int,
    identity: str,
    expires: int,
    signature: str,
    download: bool,
) -> MaterialAccessGrant:
    if expires < int(time.time()):
        raise ValueError("Material access URL has expired")

    expected_signature = sign_material_proxy_access_url(
        material_uuid=material_uuid,
        user_id=user_id,
        identity=identity,
        expires_at=expires,
        download=download,
    )
    if not hmac.compare_digest(signature or "", expected_signature):
        raise ValueError("Material access URL signature is invalid")

    return MaterialAccessGrant(
        material_uuid=material_uuid.strip(),
        user_id=user_id,
        identity=identity.strip(),
        expires_at=expires,
        download=download,
    )


class StorageService:
    def __init__(self) -> None:
        self.provider = settings.object_storage_provider.strip().lower()
        if self.provider not in {"local", "minio"}:
            raise ValueError("OBJECT_STORAGE_PROVIDER must be one of local, minio")

    def store_course_cover(self, *, course_uuid: str, upload: UploadFile) -> StoredFile:
        safe_name = self._sanitize_filename(upload.filename, upload.content_type, fallback_stem="cover")
        object_key = f"{course_uuid}/{safe_name}"
        return self._store_upload(upload=upload, object_key=object_key)

    def store_module_material(self, *, course_uuid: str, module_uuid: str, upload: UploadFile) -> StoredFile:
        safe_name = self._sanitize_filename(upload.filename, upload.content_type, fallback_stem="material")
        object_key = f"{course_uuid}/{module_uuid}/{safe_name}"
        return self._store_upload(upload=upload, object_key=object_key)

    def initiate_module_material_multipart_upload(
        self,
        *,
        course_uuid: str,
        module_uuid: str,
        filename: str,
        content_type: str | None,
    ) -> MultipartUploadTarget:
        if self.provider != "minio":
            raise ValueError("Multipart direct uploads require OBJECT_STORAGE_PROVIDER=minio")

        safe_name = self._sanitize_filename(filename, content_type, fallback_stem="material")
        object_key = f"{course_uuid}/{module_uuid}/{safe_name}"
        client = self._build_minio_client()
        ensure_bucket_exists(client, settings.minio_bucket)
        upload_id = create_multipart_upload(
            client,
            bucket_name=settings.minio_bucket,
            object_name=object_key,
            content_type=content_type,
        )
        return MultipartUploadTarget(
            provider="minio",
            bucket=settings.minio_bucket,
            object_key=object_key,
            upload_id=upload_id,
        )

    def get_multipart_part_upload_url(
        self,
        *,
        bucket: str | None,
        object_key: str,
        upload_id: str,
        part_number: int,
    ) -> str:
        if self.provider != "minio":
            raise ValueError("Multipart direct uploads require OBJECT_STORAGE_PROVIDER=minio")

        normalized_bucket = bucket or settings.minio_bucket
        client = self._build_minio_client()
        expires = timedelta(seconds=settings.minio_multipart_part_url_expires_seconds)
        presigned_url = build_multipart_part_upload_url(
            client,
            bucket_name=normalized_bucket,
            object_name=object_key,
            upload_id=upload_id,
            part_number=part_number,
            expires=expires,
        )
        return self._rewrite_minio_presigned_url(presigned_url=presigned_url, bucket=normalized_bucket)

    def complete_multipart_material_upload(
        self,
        *,
        bucket: str | None,
        object_key: str,
        upload_id: str,
        parts: list[tuple[int, str]],
        content_type: str | None,
        size_bytes: int | None,
    ) -> StoredFile:
        if self.provider != "minio":
            raise ValueError("Multipart direct uploads require OBJECT_STORAGE_PROVIDER=minio")

        normalized_bucket = bucket or settings.minio_bucket
        client = self._build_minio_client()
        complete_multipart_upload(
            client,
            bucket_name=normalized_bucket,
            object_name=object_key,
            upload_id=upload_id,
            parts=parts,
        )
        # Read the object metadata after completion instead of trusting the
        # client-declared size.  This keeps media limits and AI indexing costs
        # tied to bytes actually stored in MinIO.
        object_stat = client.stat_object(normalized_bucket, object_key)
        actual_size_bytes = int(getattr(object_stat, "size", size_bytes or 0) or 0)
        return StoredFile(
            provider="minio",
            bucket=normalized_bucket,
            object_key=object_key,
            public_url=self._build_minio_public_url(object_key),
            content_type=content_type,
            size_bytes=actual_size_bytes,
            original_filename=Path(object_key).name,
            absolute_path=None,
        )

    def abort_multipart_material_upload(
        self,
        *,
        bucket: str | None,
        object_key: str,
        upload_id: str,
    ) -> None:
        if self.provider != "minio":
            return

        client = self._build_minio_client()
        abort_multipart_upload(
            client,
            bucket_name=bucket or settings.minio_bucket,
            object_name=object_key,
            upload_id=upload_id,
        )

    def get_material_access_url(self, *, metadata: dict | None, fallback_url: str | None) -> str:
        if self.provider != "minio":
            object_key = self._resolve_local_material_object_key(metadata=metadata, fallback_url=fallback_url)
            return self._build_local_material_access_url(object_key) if object_key else ""

        metadata = metadata or {}
        object_key = metadata.get("objectKey") or metadata.get("storedRelativePath")
        bucket = metadata.get("bucket") or settings.minio_bucket
        if not object_key or not bucket:
            return fallback_url or ""

        return self._build_minio_material_url(bucket=bucket, object_key=object_key)

    def get_material_download_url(self, *, metadata: dict | None, fallback_url: str | None) -> str:
        metadata = metadata or {}
        if self.provider != "minio":
            object_key = self._resolve_local_material_object_key(metadata=metadata, fallback_url=fallback_url)
            if not object_key:
                return ""
            base_url = self._build_local_material_access_url(object_key)
            separator = "&" if "?" in base_url else "?"
            return f"{base_url}{separator}download=1"

        object_key = metadata.get("objectKey") or metadata.get("storedRelativePath")
        bucket = metadata.get("bucket") or settings.minio_bucket
        if not object_key or not bucket:
            return fallback_url or ""
        filename = str(metadata.get("originalFilename") or Path(str(object_key)).name)
        client = self._build_minio_client()
        expires = timedelta(seconds=settings.minio_signed_url_expires_seconds)
        presigned_url = client.presigned_get_object(
            bucket,
            str(object_key),
            expires=expires,
            response_headers={
                "response-content-disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            },
        )
        return self._rewrite_minio_presigned_url(presigned_url=presigned_url, bucket=str(bucket))

    def has_managed_material(self, *, metadata: dict | None) -> bool:
        """Return whether a material has an object owned by this platform.

        External links deliberately stay external; only uploaded/local/MinIO
        objects are eligible for the authenticated delivery proxy.
        """

        metadata = metadata or {}
        object_key = metadata.get("objectKey") or metadata.get("storedRelativePath")
        return isinstance(object_key, str) and bool(object_key.strip())

    def get_material_proxy_access_url(
        self,
        *,
        material_uuid: str,
        user_id: int,
        identity: str,
        download: bool = False,
    ) -> str:
        """Build a short-lived opaque URL for the learning-service proxy.

        The URL contains no object path or storage credentials.  Its grant is
        re-authorized against the database when the content is requested.
        """

        expires_at = int(time.time()) + max(1, settings.material_access_url_expires_seconds)
        signature = sign_material_proxy_access_url(
            material_uuid=material_uuid,
            user_id=user_id,
            identity=identity,
            expires_at=expires_at,
            download=download,
        )
        query = {
            "userId": str(user_id),
            "identity": identity.strip(),
            "expires": str(expires_at),
            "signature": signature,
        }
        if download:
            query["download"] = "1"

        base = settings.learning_material_public_base_url.rstrip("/")
        return f"{base}/access/{quote(material_uuid.strip(), safe='')}?{urlencode(query)}"

    def resolve_managed_material_content(self, *, metadata: dict | None) -> MaterialContentSource:
        """Resolve a managed object for proxy delivery without exposing its URL."""

        metadata = metadata or {}
        raw_object_key = metadata.get("objectKey") or metadata.get("storedRelativePath")
        if not isinstance(raw_object_key, str) or not raw_object_key.strip():
            raise ValueError("Material does not have a managed storage object")

        object_key = normalize_local_material_object_key(raw_object_key)
        provider = str(metadata.get("storageProvider") or self.provider).strip().lower()
        filename = str(metadata.get("originalFilename") or Path(object_key).name).strip() or Path(object_key).name
        configured_content_type = metadata.get("contentType")
        content_type = configured_content_type if isinstance(configured_content_type, str) else None

        if provider == "local":
            material_root = settings.material_root_path.resolve()
            material_path = (material_root / object_key).resolve()
            try:
                material_path.relative_to(material_root)
            except ValueError as exc:
                raise ValueError("Material path is invalid") from exc
            if not material_path.is_file():
                raise FileNotFoundError("Material not found")
            return MaterialContentSource(
                provider="local",
                bucket=None,
                object_key=object_key,
                filename=filename,
                content_type=content_type or mimetypes.guess_type(filename)[0],
                size_bytes=material_path.stat().st_size,
                absolute_path=material_path,
            )

        if provider == "minio":
            bucket = str(metadata.get("bucket") or settings.minio_bucket).strip()
            if not bucket:
                raise ValueError("Material storage bucket is invalid")
            object_stat = self._build_minio_client().stat_object(bucket, object_key)
            stat_content_type = getattr(object_stat, "content_type", None)
            return MaterialContentSource(
                provider="minio",
                bucket=bucket,
                object_key=object_key,
                filename=filename,
                content_type=content_type or stat_content_type or mimetypes.guess_type(filename)[0],
                size_bytes=int(getattr(object_stat, "size", 0) or 0),
                absolute_path=None,
            )

        raise ValueError("Unsupported material storage provider")

    def open_managed_material_stream(
        self,
        *,
        source: MaterialContentSource,
        offset: int = 0,
        length: int | None = None,
    ):
        if source.provider != "minio" or not source.bucket:
            raise ValueError("Material source is not streamable from MinIO")

        options: dict[str, int] = {"offset": max(0, offset)}
        if length is not None:
            options["length"] = max(0, length)
        return self._build_minio_client().get_object(source.bucket, source.object_key, **options)

    def _build_minio_material_url(self, *, bucket: str, object_key: str) -> str:
        client = self._build_minio_client()
        expires = timedelta(seconds=settings.minio_signed_url_expires_seconds)
        presigned_url = client.presigned_get_object(bucket, object_key, expires=expires)
        return self._rewrite_minio_presigned_url(presigned_url=presigned_url, bucket=bucket)

    def delete_course_cover(
        self,
        *,
        course_uuid: str,
        cover_image_url: str | None,
    ) -> None:
        object_key = self._extract_course_cover_object_key(course_uuid=course_uuid, cover_image_url=cover_image_url)
        if object_key is None:
            return

        if self.provider == "minio":
            client = self._build_minio_client()
            try:
                client.remove_object(settings.minio_bucket, object_key)
            except S3Error as exc:
                if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchVersion"}:
                    return
                raise
            return

        target_path = (settings.material_root_path / object_key).resolve()
        try:
            target_path.relative_to(settings.material_root_path.resolve())
        except ValueError as exc:
            raise ValueError("Course cover path must remain within the configured material root") from exc
        target_path.unlink(missing_ok=True)

    def delete_module_material(
        self,
        *,
        storage_provider: str | None,
        bucket: str | None,
        object_key: str | None,
    ) -> None:
        normalized_provider = (storage_provider or self.provider).strip().lower()
        normalized_object_key = (object_key or "").strip()
        if not normalized_object_key:
            # Some material records may not have a managed backing object.
            return

        if normalized_provider == "minio":
            client = self._build_minio_client()
            try:
                client.remove_object(bucket or settings.minio_bucket, normalized_object_key)
            except S3Error as exc:
                if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchVersion"}:
                    return
                raise
            return

        target_path = (settings.material_root_path / normalized_object_key).resolve()
        try:
            target_path.relative_to(settings.material_root_path.resolve())
        except ValueError as exc:
            raise ValueError("Material storage path must remain within the configured material root") from exc
        target_path.unlink(missing_ok=True)

    def scan_stored_file(self, *, stored_file: StoredFile, scanner: UploadScanService) -> UploadScanResult:
        normalized_provider = stored_file.provider.strip().lower()
        if normalized_provider == "local":
            target_path = stored_file.absolute_path or (settings.material_root_path / stored_file.object_key).resolve()
            try:
                target_path.relative_to(settings.material_root_path.resolve())
            except ValueError as exc:
                raise ValueError("Material storage path must remain within the configured material root") from exc
            return scanner.scan_path(target_path, label=stored_file.original_filename)

        if normalized_provider == "minio":
            client = self._build_minio_client()
            response = client.get_object(stored_file.bucket or settings.minio_bucket, stored_file.object_key)
            try:
                return scanner.scan_chunks(
                    response.stream(max(4096, settings.material_scan_chunk_bytes)),
                    label=stored_file.original_filename,
                )
            finally:
                response.close()
                response.release_conn()

        raise ValueError("Unsupported storage provider for material security scan")

    @contextmanager
    def material_file_for_inspection(self, *, stored_file: StoredFile):
        """Yield a local path for media metadata validation without exposing storage credentials."""
        normalized_provider = stored_file.provider.strip().lower()
        if normalized_provider == "local":
            target_path = stored_file.absolute_path or (settings.material_root_path / stored_file.object_key).resolve()
            yield target_path
            return
        if normalized_provider != "minio":
            raise ValueError("Unsupported storage provider for material inspection")

        temporary_file = tempfile.NamedTemporaryFile(prefix="material-inspection-", delete=False)
        temporary_path = Path(temporary_file.name)
        temporary_file.close()
        response = None
        try:
            client = self._build_minio_client()
            response = client.get_object(stored_file.bucket or settings.minio_bucket, stored_file.object_key)
            with temporary_path.open("wb") as output_stream:
                for chunk in response.stream(1024 * 1024):
                    output_stream.write(chunk)
            yield temporary_path
        finally:
            if response is not None:
                response.close()
                response.release_conn()
            temporary_path.unlink(missing_ok=True)

    def _store_upload(self, *, upload: UploadFile, object_key: str) -> StoredFile:
        if self.provider == "minio":
            return self._store_minio(upload=upload, object_key=object_key)
        return self._store_local(upload=upload, object_key=object_key)

    def _store_local(self, *, upload: UploadFile, object_key: str) -> StoredFile:
        target_path = settings.material_root_path / object_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path = self._allocate_target_path(target_path)

        size_bytes = 0
        try:
            with target_path.open("wb") as output_stream:
                upload.file.seek(0)
                while True:
                    chunk = upload.file.read(1024 * 1024)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > settings.max_material_upload_bytes:
                        raise ValueError(
                            f"File is too large for standard upload. Maximum is {settings.max_material_upload_bytes} bytes."
                        )
                    output_stream.write(chunk)
        except Exception:
            self._delete_file_if_exists(target_path)
            raise
        finally:
            upload.file.close()

        relative_key = target_path.relative_to(settings.material_root_path).as_posix()
        return StoredFile(
            provider="local",
            bucket=None,
            object_key=relative_key,
            public_url=self._build_local_public_url(relative_key),
            content_type=upload.content_type,
            size_bytes=size_bytes,
            original_filename=Path(target_path.name).name,
            absolute_path=target_path,
        )

    def _store_minio(self, *, upload: UploadFile, object_key: str) -> StoredFile:
        client = self._build_minio_client()
        ensure_bucket_exists(client, settings.minio_bucket)
        normalized_key = object_key
        size_bytes = self._get_upload_size(upload)
        if size_bytes > settings.max_material_upload_bytes:
            raise ValueError(
                f"File is too large for standard upload. Maximum is {settings.max_material_upload_bytes} bytes."
            )

        try:
            upload.file.seek(0)
            client.put_object(
                settings.minio_bucket,
                normalized_key,
                data=upload.file,
                length=size_bytes,
                content_type=upload.content_type or "application/octet-stream",
            )
        finally:
            upload.file.close()
        return StoredFile(
            provider="minio",
            bucket=settings.minio_bucket,
            object_key=normalized_key,
            public_url=self._build_minio_public_url(normalized_key),
            content_type=upload.content_type,
            size_bytes=size_bytes,
            original_filename=Path(normalized_key).name,
            absolute_path=None,
        )

    def _build_local_public_url(self, object_key: str) -> str:
        base = settings.learning_material_public_base_url.rstrip("/")
        encoded_segments = "/".join(quote(part) for part in object_key.split("/"))
        return f"{base}/{encoded_segments}"

    def _build_local_material_access_url(self, object_key: str) -> str:
        normalized_key = normalize_local_material_object_key(object_key)
        expires_at = int(time.time()) + max(1, settings.material_access_url_expires_seconds)
        signature = sign_local_material_access_url(normalized_key, expires_at)
        base = settings.learning_material_public_base_url.rstrip("/")
        encoded_segments = "/".join(quote(part, safe="") for part in normalized_key.split("/"))
        query = urlencode({"expires": str(expires_at), "signature": signature})
        return f"{base}/{encoded_segments}?{query}"

    def _resolve_local_material_object_key(self, *, metadata: dict | None, fallback_url: str | None) -> str | None:
        metadata = metadata or {}
        object_key = metadata.get("objectKey") or metadata.get("storedRelativePath")
        if isinstance(object_key, str) and object_key.strip():
            return normalize_local_material_object_key(object_key)

        if not fallback_url:
            return None

        parsed = urlparse(fallback_url.strip())
        parsed_path = parsed.path or fallback_url.strip()
        material_base_path = urlparse(settings.learning_material_public_base_url).path.rstrip("/")
        if material_base_path and parsed_path.startswith(f"{material_base_path}/"):
            suffix = parsed_path.removeprefix(material_base_path).lstrip("/")
            return normalize_local_material_object_key(suffix)

        if fallback_url.strip().startswith(("http://", "https://", "/")):
            return None
        return normalize_local_material_object_key(fallback_url)

    def _build_minio_public_url(self, object_key: str) -> str:
        if settings.minio_public_base_url.strip():
            base = settings.minio_public_base_url.rstrip("/")
            encoded_segments = "/".join(quote(part) for part in object_key.split("/"))
            return f"{base}/{encoded_segments}"

        client = self._build_minio_client()
        expires = timedelta(seconds=settings.minio_signed_url_expires_seconds)
        presigned_url = client.presigned_get_object(settings.minio_bucket, object_key, expires=expires)
        return self._rewrite_minio_presigned_url(presigned_url=presigned_url, bucket=settings.minio_bucket)

    def _rewrite_minio_presigned_url(self, *, presigned_url: str, bucket: str) -> str:
        public_base_url = settings.minio_public_base_url.strip()
        if not public_base_url:
            return presigned_url

        parsed_presigned = urlparse(presigned_url)
        parsed_base = urlparse(public_base_url)
        bucket_prefix = f"/{bucket.strip('/')}/"
        if parsed_presigned.path.startswith(bucket_prefix):
            object_path = parsed_presigned.path.removeprefix(bucket_prefix).lstrip("/")
        else:
            object_path = parsed_presigned.path.lstrip("/")

        base_path = parsed_base.path.rstrip("/")
        rewritten_path = f"{base_path}/{object_path}" if base_path else f"/{object_path}"
        rewritten_path = "/" + "/".join(quote(unquote(part), safe="") for part in rewritten_path.split("/") if part)

        if parsed_base.scheme and parsed_base.netloc:
            return urlunparse(
                (
                    parsed_base.scheme,
                    parsed_base.netloc,
                    rewritten_path,
                    "",
                    parsed_presigned.query,
                    parsed_presigned.fragment,
                )
            )

        return urlunparse(("", "", rewritten_path, "", parsed_presigned.query, parsed_presigned.fragment))

    def _build_minio_client(self):
        return build_minio_client(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
        )

    def _sanitize_filename(self, filename: str | None, content_type: str | None, *, fallback_stem: str) -> str:
        candidate = Path(filename or fallback_stem).name.strip()
        stem = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in candidate)
        normalized = stem.strip("._") or fallback_stem
        if Path(normalized).suffix:
            return normalized
        guessed_extension = mimetypes.guess_extension((content_type or "").strip().lower()) or ""
        return normalized + guessed_extension

    def _allocate_target_path(self, target_path: Path) -> Path:
        if not target_path.exists():
            return target_path

        stem = target_path.stem or "file"
        suffix = target_path.suffix
        counter = 1
        while True:
            candidate = target_path.with_name(f"{stem}-{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _get_upload_size(self, upload: UploadFile) -> int:
        try:
            current_position = upload.file.tell()
            upload.file.seek(0, 2)
            size_bytes = upload.file.tell()
            upload.file.seek(current_position)
            return size_bytes
        except (AttributeError, OSError) as exc:
            declared_size = getattr(upload, "size", None)
            if isinstance(declared_size, int) and declared_size >= 0:
                return declared_size
            raise ValueError("Unable to determine upload size") from exc

    def _delete_file_if_exists(self, target_path: Path) -> None:
        try:
            target_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _extract_course_cover_object_key(self, *, course_uuid: str, cover_image_url: str | None) -> str | None:
        normalized_url = (cover_image_url or "").strip()
        if not normalized_url:
            return None

        parsed = urlparse(normalized_url)
        decoded_path = unquote(parsed.path or "")
        course_marker = f"/{course_uuid}/"
        if course_marker in decoded_path:
            _, suffix = decoded_path.split(course_marker, 1)
            suffix = suffix.lstrip("/")
            if suffix:
                return f"{course_uuid}/{suffix}"

        filename = Path(decoded_path).name.strip()
        if filename:
            return f"{course_uuid}/{filename}"
        return None
