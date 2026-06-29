from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

from minio import Minio
from minio.datatypes import Part
from minio.error import S3Error


def normalize_minio_endpoint(endpoint: str) -> tuple[str, bool]:
    normalized = endpoint.strip()
    if not normalized:
        raise ValueError("MinIO endpoint is required")

    if "://" in normalized:
        parsed = urlparse(normalized)
        return parsed.netloc, parsed.scheme == "https"
    return normalized, False


def build_minio_client(*, endpoint: str, access_key: str, secret_key: str) -> Minio:
    normalized_endpoint, secure = normalize_minio_endpoint(endpoint)
    return Minio(
        normalized_endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )


def ensure_bucket_exists(client: Minio, bucket_name: str) -> None:
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
    except S3Error:
        raise


def create_multipart_upload(
    client: Minio,
    *,
    bucket_name: str,
    object_name: str,
    content_type: str | None = None,
) -> str:
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    return client._create_multipart_upload(bucket_name, object_name, headers)


def build_multipart_part_upload_url(
    client: Minio,
    *,
    bucket_name: str,
    object_name: str,
    upload_id: str,
    part_number: int,
    expires: timedelta,
) -> str:
    return client.get_presigned_url(
        "PUT",
        bucket_name,
        object_name,
        expires=expires,
        extra_query_params={
            "uploadId": upload_id,
            "partNumber": str(part_number),
        },
    )


def complete_multipart_upload(
    client: Minio,
    *,
    bucket_name: str,
    object_name: str,
    upload_id: str,
    parts: list[tuple[int, str]],
) -> None:
    normalized_parts = [Part(part_number, etag) for part_number, etag in sorted(parts, key=lambda item: item[0])]
    client._complete_multipart_upload(bucket_name, object_name, upload_id, normalized_parts)


def abort_multipart_upload(
    client: Minio,
    *,
    bucket_name: str,
    object_name: str,
    upload_id: str,
) -> None:
    client._abort_multipart_upload(bucket_name, object_name, upload_id)
