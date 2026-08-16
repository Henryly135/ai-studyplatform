import mimetypes
from collections.abc import Iterator
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from minio.error import S3Error
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import require_identity_user
from app.db.session import get_db_session
from app.schemas.course import MaterialAccessTicketResponse
from app.services.course_catalog_service import CourseCatalogService
from app.services.identity_user_client import IdentityUserClient
from app.services.material_access_session import (
    MATERIAL_ACCESS_SESSION_COOKIE,
    require_matching_material_access_session,
)
from app.services.storage_service import (
    MaterialContentSource,
    StorageService,
    validate_local_material_access_url,
    validate_material_proxy_access_url,
)


router = APIRouter(tags=["material-access"])


def _can_preview_inline(media_type: str) -> bool:
    safe_inline_media_types = {
        "application/json",
        "application/pdf",
        "text/csv",
        "text/markdown",
        "text/plain",
    }
    return (
        media_type in safe_inline_media_types
        or media_type.startswith("audio/")
        or media_type.startswith("video/")
        or (media_type.startswith("image/") and media_type != "image/svg+xml")
    )


def _content_disposition_headers(*, filename: str, media_type: str, download: bool) -> dict[str, str]:
    disposition_type = "inline" if _can_preview_inline(media_type) and not download else "attachment"
    return {
        "Content-Disposition": f"{disposition_type}; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }


def _parse_single_byte_range(range_header: str | None, *, total_size: int) -> tuple[int, int] | None:
    if not range_header:
        return None
    if total_size <= 0:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested range is not satisfiable",
            headers={"Content-Range": f"bytes */{total_size}"},
        )

    normalized = range_header.strip()
    if not normalized.startswith("bytes=") or "," in normalized:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested range is not satisfiable",
            headers={"Content-Range": f"bytes */{total_size}"},
        )

    start_text, separator, end_text = normalized.removeprefix("bytes=").partition("-")
    if not separator or (not start_text and not end_text):
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested range is not satisfiable",
            headers={"Content-Range": f"bytes */{total_size}"},
        )

    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else total_size - 1
        else:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise ValueError
            start = max(0, total_size - suffix_length)
            end = total_size - 1
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested range is not satisfiable",
            headers={"Content-Range": f"bytes */{total_size}"},
        ) from exc

    if start < 0 or start >= total_size or end < start:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested range is not satisfiable",
            headers={"Content-Range": f"bytes */{total_size}"},
        )
    return start, min(end, total_size - 1)


def _stream_minio_response(response) -> Iterator[bytes]:
    try:
        yield from response.stream(1024 * 1024)
    finally:
        response.close()
        response.release_conn()


def _deliver_managed_material(
    *,
    storage: StorageService,
    source: MaterialContentSource,
    download: bool,
    range_header: str | None,
):
    media_type = source.content_type or mimetypes.guess_type(source.filename)[0] or "application/octet-stream"
    response_headers = _content_disposition_headers(
        filename=source.filename,
        media_type=media_type,
        download=download,
    )

    if source.provider == "local":
        if source.absolute_path is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
        return FileResponse(
            source.absolute_path,
            media_type=media_type,
            filename=source.filename,
            content_disposition_type="inline" if _can_preview_inline(media_type) and not download else "attachment",
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    if source.provider != "minio":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    byte_range = _parse_single_byte_range(range_header, total_size=source.size_bytes)
    offset = byte_range[0] if byte_range else 0
    length = byte_range[1] - byte_range[0] + 1 if byte_range else None
    try:
        upstream_response = storage.open_managed_material_stream(
            source=source,
            offset=offset,
            length=length,
        )
    except S3Error as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found") from exc

    if byte_range:
        response_headers.update(
            {
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {byte_range[0]}-{byte_range[1]}/{source.size_bytes}",
                "Content-Length": str(length),
            }
        )
        response_status = status.HTTP_206_PARTIAL_CONTENT
    else:
        response_headers.update(
            {
                "Accept-Ranges": "bytes",
                "Content-Length": str(source.size_bytes),
            }
        )
        response_status = status.HTTP_200_OK

    return StreamingResponse(
        _stream_minio_response(upstream_response),
        status_code=response_status,
        media_type=media_type,
        headers=response_headers,
    )


@router.get(
    "/materials/{material_uuid}/ticket",
    summary="Refresh Material Access Ticket [Authenticated]",
    response_model=MaterialAccessTicketResponse,
    response_model_exclude_none=True,
)
def issue_material_access_ticket(
    material_uuid: str,
    current_user: dict = Depends(require_identity_user),
    session: Session = Depends(get_db_session),
) -> MaterialAccessTicketResponse:
    catalog = CourseCatalogService(session)
    material = catalog.get_accessible_material_by_uuid(
        material_uuid=material_uuid,
        current_user=current_user,
    )
    resource_url, download_url = catalog.get_material_delivery_urls(
        material=material,
        current_user=current_user,
    )
    return MaterialAccessTicketResponse(resourceUrl=resource_url, downloadUrl=download_url)


@router.get("/materials/access/{material_uuid}", include_in_schema=False)
def proxy_material_access(
    material_uuid: str,
    request: Request,
    user_id: int = Query(..., alias="userId", ge=1),
    identity: str = Query(..., min_length=1, max_length=32),
    expires: int = Query(...),
    signature: str = Query(...),
    download: bool = False,
    material_access_session: str | None = Cookie(
        default=None,
        alias=MATERIAL_ACCESS_SESSION_COOKIE,
    ),
    session: Session = Depends(get_db_session),
):
    """Deliver an uploaded material through a short-lived, re-authorized proxy."""

    try:
        grant = validate_material_proxy_access_url(
            material_uuid=material_uuid,
            user_id=user_id,
            identity=identity,
            expires=expires,
            signature=signature,
            download=download,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    try:
        require_matching_material_access_session(
            token=material_access_session,
            user_id=grant.user_id,
            identity=grant.identity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    current_identity = IdentityUserClient().lookup_users_by_ids(user_ids=[grant.user_id]).get(grant.user_id)
    role_codes = current_identity.get("roleCodes", []) if current_identity else []
    normalized_roles = {
        str(role_code).strip().lower()
        for role_code in role_codes
        if isinstance(role_code, str)
    }
    if (
        current_identity is None
        or str(current_identity.get("accountStatus", "")).strip().lower() != "active"
        or grant.identity.strip().lower() not in normalized_roles
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Material access identity is no longer active",
        )

    catalog = CourseCatalogService(session)
    material = catalog.get_accessible_material_by_uuid(
        material_uuid=grant.material_uuid,
        current_user={"id": grant.user_id, "identity": grant.identity},
    )
    storage = StorageService()
    try:
        source = storage.resolve_managed_material_content(metadata=material.metadata_json)
    except (FileNotFoundError, S3Error, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found") from exc

    return _deliver_managed_material(
        storage=storage,
        source=source,
        download=grant.download,
        range_header=request.headers.get("range"),
    )


@router.get("/materials/{object_path:path}", include_in_schema=False)
def download_local_material(
    object_path: str,
    expires: int = Query(...),
    signature: str = Query(...),
    download: bool = False,
) -> FileResponse:
    """Compatibility route for already-issued local signed URLs.

    New catalog responses use ``/materials/access/{material_uuid}`` above and
    never expose a storage object path.  This route can be removed after the
    maximum legacy URL lifetime has elapsed following deployment.
    """

    if settings.object_storage_provider.strip().lower() != "local":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    try:
        normalized_key = validate_local_material_access_url(
            object_key=object_path,
            expires=expires,
            signature=signature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    material_root = settings.material_root_path.resolve()
    material_path = (material_root / normalized_key).resolve()
    try:
        material_path.relative_to(material_root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Material path is invalid") from exc

    if not material_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    media_type = mimetypes.guess_type(material_path.name)[0] or "application/octet-stream"
    content_disposition_type = "inline" if _can_preview_inline(media_type) and not download else "attachment"
    return FileResponse(
        material_path,
        media_type=media_type,
        filename=material_path.name,
        content_disposition_type=content_disposition_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
