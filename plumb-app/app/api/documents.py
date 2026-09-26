import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.events import log_event
from app.db.session import get_db
from app.models.deal import Deal
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.schemas.enums import EventType
from app.storage.s3 import get_presigned_url, upload_document

router = APIRouter(prefix="/deals/{deal_id}/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_doc(
    deal_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify deal exists
    deal_result = await db.execute(select(Deal).where(Deal.id == deal_id))
    if deal_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    s3_key, file_size = upload_document(deal_id, file)

    doc = Document(
        deal_id=deal_id,
        filename=file.filename or "unnamed",
        mime_type=file.content_type or "application/octet-stream",
        s3_key=s3_key,
        file_size=file_size,
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    await log_event(
        db=db,
        deal_id=deal_id,
        event_type=EventType.DOC_UPLOADED.value,
        actor_id=current_user.id,
        payload={"document_id": str(doc.id), "filename": doc.filename, "file_size": file_size},
    )

    return doc


@router.get("", response_model=DocumentListResponse)
async def list_docs(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.deal_id == deal_id).order_by(Document.uploaded_at.desc())
    )
    docs = result.scalars().all()
    return DocumentListResponse(documents=docs, total=len(docs))


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_doc(
    deal_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.deal_id == deal_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.get("/{doc_id}/download")
async def download_doc(
    deal_id: uuid.UUID,
    doc_id: uuid.UUID,
    inline: bool = Query(False, description="Return URL for inline viewing instead of download"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.deal_id == deal_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    url = get_presigned_url(doc.s3_key, inline=inline)
    return {"download_url": url, "filename": doc.filename, "mime_type": doc.mime_type}
