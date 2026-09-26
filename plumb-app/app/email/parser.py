"""Inbound email parser — detects new deals vs follow-ups, extracts attachments."""

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.email.client import (
    GmailClient,
    extract_body_text,
    extract_header,
    extract_sender,
)
from app.models.email import EmailMessage, EmailThread

logger = logging.getLogger(__name__)

# Document MIME types we accept as deal package attachments
DEAL_ATTACHMENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

# Also match by extension for MIME types that Gmail sometimes reports generically
DEAL_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".docx", ".doc"}


def _is_deal_attachment(filename: str, mime_type: str) -> bool:
    """Check if a file is a plausible deal document attachment."""
    if mime_type in DEAL_ATTACHMENT_TYPES:
        return True
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in DEAL_EXTENSIONS


async def classify_inbound_email(
    db: AsyncSession,
    gmail_thread_id: str,
) -> str:
    """Determine if a message belongs to an existing deal thread or is new.

    Returns:
        "new_deal" — first time we've seen this thread, has attachments
        "follow_up" — thread already linked to a deal
        "no_attachments" — new thread but no deal documents attached
    """
    result = await db.execute(
        select(EmailThread).where(EmailThread.gmail_thread_id == gmail_thread_id)
    )
    existing = result.scalar_one_or_none()

    if existing and existing.deal_id:
        return "follow_up"

    return "new_deal"


async def record_inbound_message(
    db: AsyncSession,
    gmail_client: GmailClient,
    message_id: str,
    message: dict,
) -> tuple[EmailThread, EmailMessage, list[dict]]:
    """Parse and store an inbound email message. Returns (thread, message, attachments).

    attachments: list of {filename, mime_type, data (bytes), size}
    """
    gmail_thread_id = message.get("threadId", "")
    sender_name, sender_email = extract_sender(message)
    subject = extract_header(message, "Subject") or "(no subject)"
    body_text = extract_body_text(message)

    # Get or create thread
    result = await db.execute(
        select(EmailThread).where(EmailThread.gmail_thread_id == gmail_thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        thread = EmailThread(
            gmail_thread_id=gmail_thread_id,
            subject=subject,
            sender_email=sender_email,
            sender_name=sender_name,
        )
        db.add(thread)
        await db.flush()

    # Download attachments
    raw_attachments = gmail_client.get_attachments(message_id, message)
    deal_attachments = [a for a in raw_attachments if _is_deal_attachment(a["filename"], a["mime_type"])]

    # Record attachment metadata (without the raw bytes) for the DB
    attachment_meta = [
        {"filename": a["filename"], "mime_type": a["mime_type"], "size": a["size"]}
        for a in deal_attachments
    ]

    # Store message
    email_msg = EmailMessage(
        thread_id=thread.id,
        gmail_message_id=message_id,
        direction="inbound",
        from_email=sender_email,
        from_name=sender_name,
        body_text=body_text,
        attachments=attachment_meta,
    )
    db.add(email_msg)
    await db.flush()

    return thread, email_msg, deal_attachments


def extract_follow_up_content(body_text: str) -> str:
    """Strip quoted reply text from an email body to get just the new content.

    Gmail typically uses "On ... wrote:" or "> " prefix for quoted text.
    """
    lines = body_text.split("\n")
    new_lines = []
    for line in lines:
        # Stop at quoted text markers
        if re.match(r"^On .+ wrote:$", line.strip()):
            break
        if line.strip().startswith(">"):
            break
        # Stop at common signature markers
        if line.strip() in ("--", "---", "Sent from my iPhone", "Sent from my iPad"):
            break
        new_lines.append(line)

    return "\n".join(new_lines).strip()
