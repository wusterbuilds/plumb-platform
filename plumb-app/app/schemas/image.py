from datetime import datetime

from pydantic import BaseModel


class ImageResponse(BaseModel):
    id: str
    deal_id: str
    image_type: str
    filename: str
    caption: str | None
    sort_order: int
    associated_entity: str | None
    uploaded_at: datetime | None
    download_url: str | None = None

    model_config = {"from_attributes": True}


class ImageListResponse(BaseModel):
    images: list[ImageResponse]


class ImageUpdate(BaseModel):
    caption: str | None = None
    sort_order: int | None = None
