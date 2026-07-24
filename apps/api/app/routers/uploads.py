import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_parent
from ..config import get_settings
from ..db import get_session
from ..models import Child, Upload
from ..schemas import PresignOut, PresignRequest

router = APIRouter(prefix="/uploads", tags=["uploads"])

_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}


@router.post("/presign", response_model=PresignOut)
async def presign_upload(
    body: PresignRequest,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_parent),
) -> PresignOut:
    """Create an uploads row and a presigned PUT URL. The browser uploads
    straight to S3 — the photo never passes through this API."""
    settings = get_settings()
    if not settings.s3_upload_bucket:
        raise HTTPException(status_code=503, detail="S3_UPLOAD_BUCKET is not configured")

    child = await session.get(Child, body.child_id)
    if child is None or child.parent_clerk_id != user_id:
        raise HTTPException(status_code=404, detail="Child not found")

    key = f"uploads/{child.id}/{uuid.uuid4().hex}.{_EXTENSIONS[body.content_type]}"
    upload = Upload(child_id=child.id, s3_key=key)
    session.add(upload)
    await session.commit()
    await session.refresh(upload)

    import boto3  # lazy: keeps boot RSS down, and unit tests never touch it

    client = boto3.client("s3", region_name=settings.aws_region)
    # Presigning is local computation (no network call), so inline is fine.
    url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_upload_bucket,
            "Key": key,
            "ContentType": body.content_type,
        },
        ExpiresIn=settings.upload_url_ttl_seconds,
    )
    return PresignOut(
        upload_id=upload.id,
        s3_key=key,
        url=url,
        headers={"Content-Type": body.content_type},
        expires_in=settings.upload_url_ttl_seconds,
    )
