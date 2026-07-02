import mimetypes

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.services.storage_service import validate_local_material_access_url


router = APIRouter(tags=["material-access"])


@router.get("/materials/{object_path:path}", include_in_schema=False)
def download_local_material(
    object_path: str,
    expires: int = Query(...),
    signature: str = Query(...),
) -> FileResponse:
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
    return FileResponse(material_path, media_type=media_type, filename=material_path.name)
