"""Deal image management API routes."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.deal import Deal
from app.models.image import DealImage
from app.models.user import User
from app.schemas.image import ImageListResponse, ImageResponse, ImageUpdate
from app.storage.s3 import delete_document, get_presigned_url

router = APIRouter()

ALLOWED_IMAGE_TYPES = {
    "hero_rendering",
    "exterior_rendering",
    "interior_rendering",
    "aerial_rendering",
    "site_plan",
    "floor_plan",
    "lot_map",
    "market_map",
    "sponsor_logo",
    "sponsor_photo",
    "other",
}


def _image_to_response(img: DealImage, include_url: bool = True) -> ImageResponse:
    download_url = None
    if include_url:
        try:
            download_url = get_presigned_url(img.s3_key)
        except Exception:
            pass

    return ImageResponse(
        id=str(img.id),
        deal_id=str(img.deal_id),
        image_type=img.image_type,
        filename=img.filename,
        caption=img.caption,
        sort_order=img.sort_order,
        associated_entity=img.associated_entity,
        uploaded_at=img.uploaded_at,
        download_url=download_url,
    )


async def _get_deal(deal_id: uuid.UUID, db: AsyncSession) -> Deal:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.post("", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    deal_id: uuid.UUID,
    image_type: str = Form(...),
    caption: str = Form(None),
    associated_entity: str = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload an image for a deal."""
    await _get_deal(deal_id, db)

    if image_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image_type '{image_type}'. Allowed: {sorted(ALLOWED_IMAGE_TYPES)}",
        )

    # Read file content
    content = await file.read()
    file_size = len(content)
    filename = file.filename or "unnamed"

    # Upload to S3
    from app.storage.s3 import _get_client
    from app.config import settings

    s3_key = f"deals/{deal_id}/images/{filename}"
    client = _get_client()
    client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=content,
        ContentType=file.content_type or "image/jpeg",
    )

    # Determine sort order (append after existing images of same type)
    result = await db.execute(
        select(DealImage)
        .where(DealImage.deal_id == deal_id, DealImage.image_type == image_type)
        .order_by(DealImage.sort_order.desc())
        .limit(1)
    )
    last_img = result.scalar_one_or_none()
    sort_order = (last_img.sort_order + 1) if last_img else 0

    img = DealImage(
        deal_id=deal_id,
        image_type=image_type,
        filename=filename,
        s3_key=s3_key,
        file_size=file_size,
        caption=caption,
        sort_order=sort_order,
        associated_entity=associated_entity,
        uploaded_by=current_user.id,
    )
    db.add(img)
    await db.flush()
    await db.refresh(img)

    return _image_to_response(img)


@router.get("", response_model=ImageListResponse)
async def list_images(
    deal_id: uuid.UUID,
    image_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List images for a deal, optionally filtered by type."""
    await _get_deal(deal_id, db)

    query = select(DealImage).where(DealImage.deal_id == deal_id)
    if image_type:
        query = query.where(DealImage.image_type == image_type)
    query = query.order_by(DealImage.image_type, DealImage.sort_order)

    result = await db.execute(query)
    images = result.scalars().all()

    return ImageListResponse(
        images=[_image_to_response(img) for img in images],
    )


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(
    deal_id: uuid.UUID,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an image."""
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(DealImage).where(
            DealImage.id == image_id,
            DealImage.deal_id == deal_id,
        )
    )
    img = result.scalar_one_or_none()
    if img is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    # Delete from S3
    try:
        delete_document(img.s3_key)
    except Exception:
        pass  # Best effort — don't fail the API call if S3 cleanup fails

    await db.delete(img)
    await db.flush()


@router.patch("/{image_id}", response_model=ImageResponse)
async def update_image(
    deal_id: uuid.UUID,
    image_id: uuid.UUID,
    update: ImageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update image caption or sort order."""
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(DealImage).where(
            DealImage.id == image_id,
            DealImage.deal_id == deal_id,
        )
    )
    img = result.scalar_one_or_none()
    if img is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(img, field, value)

    await db.flush()
    await db.refresh(img)

    return _image_to_response(img)
