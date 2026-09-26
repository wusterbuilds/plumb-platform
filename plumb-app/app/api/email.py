"""API routes for email integration — thread management, manual triggers, and status."""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.email import EmailMessage, EmailThread
from app.models.user import User

router = APIRouter(prefix="/email", tags=["email"])


# ── Email Threads ──


@router.get("/threads")
async def list_threads(
    deal_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List email threads, optionally filtered by deal."""
    query = select(EmailThread).order_by(EmailThread.updated_at.desc()).limit(50)
    if deal_id:
        query = query.where(EmailThread.deal_id == deal_id)

    result = await db.execute(query)
    threads = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "deal_id": str(t.deal_id) if t.deal_id else None,
            "gmail_thread_id": t.gmail_thread_id,
            "subject": t.subject,
            "sender_email": t.sender_email,
            "sender_name": t.sender_name,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in threads
    ]


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a single thread with all messages."""
    result = await db.execute(
        select(EmailThread).where(EmailThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    msg_result = await db.execute(
        select(EmailMessage)
        .where(EmailMessage.thread_id == thread_id)
        .order_by(EmailMessage.sent_at.asc())
    )
    messages = msg_result.scalars().all()

    return {
        "id": str(thread.id),
        "deal_id": str(thread.deal_id) if thread.deal_id else None,
        "gmail_thread_id": thread.gmail_thread_id,
        "subject": thread.subject,
        "sender_email": thread.sender_email,
        "sender_name": thread.sender_name,
        "status": thread.status,
        "created_at": thread.created_at.isoformat() if thread.created_at else None,
        "messages": [
            {
                "id": str(m.id),
                "gmail_message_id": m.gmail_message_id,
                "direction": m.direction,
                "from_email": m.from_email,
                "from_name": m.from_name,
                "body_text": m.body_text,
                "attachments": m.attachments,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            }
            for m in messages
        ],
    }


# ── Deal-scoped email endpoints ──


@router.get("/deals/{deal_id}/thread")
async def get_deal_thread(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get the email thread for a specific deal (if it was created from email)."""
    result = await db.execute(
        select(EmailThread).where(EmailThread.deal_id == deal_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        return {"thread": None}

    msg_result = await db.execute(
        select(EmailMessage)
        .where(EmailMessage.thread_id == thread.id)
        .order_by(EmailMessage.sent_at.asc())
    )
    messages = msg_result.scalars().all()

    return {
        "thread": {
            "id": str(thread.id),
            "gmail_thread_id": thread.gmail_thread_id,
            "subject": thread.subject,
            "sender_email": thread.sender_email,
            "sender_name": thread.sender_name,
            "status": thread.status,
            "message_count": len(messages),
            "messages": [
                {
                    "id": str(m.id),
                    "direction": m.direction,
                    "from_email": m.from_email,
                    "from_name": m.from_name,
                    "body_text": m.body_text[:500] if m.body_text else None,
                    "attachment_count": len(m.attachments) if m.attachments else 0,
                    "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                }
                for m in messages
            ],
        }
    }


# ── Manual triggers ──


class ManualInboxCheckRequest(BaseModel):
    pass


@router.post("/check-inbox")
async def manual_check_inbox(
    _user: User = Depends(get_current_user),
):
    """Manually trigger an inbox check (instead of waiting for the beat schedule)."""
    from app.email.monitor import check_inbox

    result = check_inbox.delay()
    return {"task_id": result.id, "status": "triggered"}


class ManualSendResponseRequest(BaseModel):
    deal_id: str


@router.post("/send-response")
async def manual_send_response(
    body: ManualSendResponseRequest,
    _user: User = Depends(get_current_user),
):
    """Manually trigger sending an email response for a deal (useful for demo/testing)."""
    from app.email.monitor import _send_deal_response

    _send_deal_response(body.deal_id)
    return {"status": "sent", "deal_id": body.deal_id}


class SimulateEmailRequest(BaseModel):
    """For demo: simulate an inbound email with deal documents already uploaded."""
    deal_id: str
    sender_email: str
    sender_name: str = ""
    subject: str = "Deal Package"
    body_text: str = "Please analyze the attached deal package."


@router.post("/simulate-inbound")
async def simulate_inbound_email(
    body: SimulateEmailRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Simulate an inbound email for a deal that already has documents uploaded.

    This creates an email thread linked to the deal and triggers the pipeline +
    email response, without needing actual Gmail integration. Useful for demo.
    """
    deal_uuid = uuid.UUID(body.deal_id)

    # Create a fake thread
    thread = EmailThread(
        deal_id=deal_uuid,
        gmail_thread_id=f"sim-{uuid.uuid4().hex[:12]}",
        subject=body.subject,
        sender_email=body.sender_email,
        sender_name=body.sender_name,
    )
    db.add(thread)
    await db.flush()

    # Create a fake inbound message
    msg = EmailMessage(
        thread_id=thread.id,
        gmail_message_id=f"sim-msg-{uuid.uuid4().hex[:12]}",
        direction="inbound",
        from_email=body.sender_email,
        from_name=body.sender_name,
        body_text=body.body_text,
    )
    db.add(msg)
    await db.flush()
    await db.commit()

    # Trigger the agent pipeline + email response
    from app.email.monitor import process_email_deal
    process_email_deal.delay(body.deal_id)

    return {
        "status": "triggered",
        "thread_id": str(thread.id),
        "deal_id": body.deal_id,
        "message": "Agent pipeline started. Email response will be sent when complete.",
    }


class DemoTriggerRequest(BaseModel):
    """Trigger the pipeline from a maintainer-supplied synthetic fixture directory."""
    property_name: str = "Harbor Point"
    sender_email: str = "jordan.lee@example.com"
    sender_name: str = "Jordan Lee"
    subject: str = "Harbor Point - Construction Loan Package"


@router.post("/demo-trigger")
async def demo_trigger(
    body: DemoTriggerRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Create a demo deal from a configured fixture directory and start the pipeline.

    Set ``PLUMB_DEMO_SCENARIO_DIR`` to a directory containing synthetic files.
    Customer files must never be placed in the repository.
    """
    import mimetypes
    import os

    from app.db.events import log_event
    from app.email.monitor import process_email_deal
    from app.models.deal import Deal
    from app.models.document import Document
    from app.schemas.enums import EventType
    from app.storage.s3 import upload_bytes

    scenario_dir = os.getenv("PLUMB_DEMO_SCENARIO_DIR", "")
    if not os.path.isdir(scenario_dir):
        raise HTTPException(
            status_code=400,
            detail="PLUMB_DEMO_SCENARIO_DIR must point to a local synthetic fixture directory",
        )

    # Create the deal
    deal = Deal(
        deal_type="construction_loan",
        status="docs_received",
        property_name=body.property_name,
        created_by=_user.id,
    )
    db.add(deal)
    await db.flush()
    await db.refresh(deal)

    await log_event(
        db=db,
        deal_id=deal.id,
        event_type=EventType.DEAL_CREATED.value,
        actor_id=_user.id,
        payload={
            "source": "email_demo",
            "sender": body.sender_email,
            "subject": body.subject,
        },
    )

    # Upload each file from the test scenario directory
    uploaded = []
    for filename in sorted(os.listdir(scenario_dir)):
        filepath = os.path.join(scenario_dir, filename)
        if not os.path.isfile(filepath) or filename.startswith("."):
            continue

        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or "application/octet-stream"

        with open(filepath, "rb") as f:
            data = f.read()

        s3_key = f"deals/{deal.id}/documents/{filename}"
        upload_bytes(data, s3_key, mime_type)

        doc = Document(
            deal_id=deal.id,
            filename=filename,
            mime_type=mime_type,
            s3_key=s3_key,
            file_size=len(data),
            uploaded_by=_user.id,
        )
        db.add(doc)
        await db.flush()

        await log_event(
            db=db,
            deal_id=deal.id,
            event_type=EventType.DOC_UPLOADED.value,
            actor_id=_user.id,
            payload={"document_id": str(doc.id), "filename": filename},
        )
        uploaded.append(filename)

    # Create an email thread so it looks like it came from email
    thread = EmailThread(
        deal_id=deal.id,
        gmail_thread_id=f"demo-{uuid.uuid4().hex[:12]}",
        subject=body.subject,
        sender_email=body.sender_email,
        sender_name=body.sender_name,
    )
    db.add(thread)
    await db.flush()

    msg = EmailMessage(
        thread_id=thread.id,
        gmail_message_id=f"demo-msg-{uuid.uuid4().hex[:12]}",
        direction="inbound",
        from_email=body.sender_email,
        from_name=body.sender_name,
        body_text=f"Please find attached the deal package for {body.property_name}.",
        attachments=[{"filename": f} for f in uploaded],
    )
    db.add(msg)
    await db.commit()

    # Kick off the agent pipeline via Celery
    process_email_deal.delay(str(deal.id))

    return {
        "status": "triggered",
        "deal_id": str(deal.id),
        "thread_id": str(thread.id),
        "documents_uploaded": uploaded,
        "message": f"Deal '{body.property_name}' created with {len(uploaded)} documents. Pipeline started.",
    }


class SimulateFollowUpRequest(BaseModel):
    deal_id: str
    body_text: str  # The follow-up question/request


@router.post("/simulate-followup")
async def simulate_followup_email(
    body: SimulateFollowUpRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Simulate a follow-up email on an existing deal.

    Creates a fake inbound message on the existing thread and triggers the
    follow-up agent. Useful for demo.
    """
    deal_uuid = uuid.UUID(body.deal_id)

    # Find the existing thread
    result = await db.execute(
        select(EmailThread).where(EmailThread.deal_id == deal_uuid)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No email thread found for this deal. Use simulate-inbound first.",
        )

    # Create a fake follow-up message
    msg = EmailMessage(
        thread_id=thread.id,
        gmail_message_id=f"sim-fu-{uuid.uuid4().hex[:12]}",
        direction="inbound",
        from_email=thread.sender_email,
        from_name=thread.sender_name,
        body_text=body.body_text,
    )
    db.add(msg)
    await db.flush()
    await db.commit()

    # Trigger the follow-up agent
    from app.email.monitor import process_email_followup
    process_email_followup.delay(body.deal_id, str(thread.id), body.body_text)

    return {
        "status": "triggered",
        "thread_id": str(thread.id),
        "deal_id": body.deal_id,
        "message": "Follow-up agent started. Updated deliverables will be sent when complete.",
    }
