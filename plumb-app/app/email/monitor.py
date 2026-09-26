"""Inbox monitor — Celery beat task that polls Gmail for new deal submissions and follow-ups."""

import asyncio
import logging
import mimetypes
import os
import uuid

from sqlalchemy import select, text

from app.config import settings
from app.db.events import log_event_sync
from app.db.session import sync_session_factory
from app.email.client import GmailClient, extract_body_text, extract_header, extract_sender
from app.email.parser import (
    classify_inbound_email,
    extract_follow_up_content,
    record_inbound_message,
)
from app.models.deal import Deal
from app.models.document import Document
from app.models.email import EmailMessage, EmailThread
from app.schemas.enums import EventType
from app.storage.s3 import upload_bytes
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _get_or_create_system_user(db) -> uuid.UUID:
    """Get or create a system user for automated actions."""
    from app.auth.security import hash_password
    from app.models.user import User

    system_email = "system@plumb.ai"
    user = db.query(User).filter(User.email == system_email).first()
    if user:
        return user.id

    user = User(
        email=system_email,
        name="Plumb System",
        hashed_password=hash_password("system-not-for-login"),
        role="system",
    )
    db.add(user)
    db.flush()
    return user.id


DEMO_SCENARIO_DIR = os.getenv("PLUMB_DEMO_SCENARIO_DIR", "")


def _already_processed(gmail_message_id: str) -> bool:
    """Check if we already processed this Gmail message (by ID in the DB)."""
    with sync_session_factory() as db:
        row = db.query(EmailMessage).filter(
            EmailMessage.gmail_message_id == gmail_message_id
        ).first()
        return row is not None


@celery_app.task(bind=True, max_retries=0)
def check_inbox(self) -> dict:
    """Poll Gmail for new deal emails (label:plumb) AND follow-up replies on existing threads.

    New deals: detected via label:plumb query.
    Follow-ups: detected by checking all known Gmail threads for new messages.
    Tracks processed messages by gmail_message_id in the DB to avoid re-processing.
    """
    if not settings.GMAIL_ENABLED:
        return {"status": "disabled"}

    try:
        gmail = GmailClient()
    except Exception as e:
        logger.error("Failed to create Gmail client: %s", e)
        return {"status": "error", "error": str(e)}

    processed = 0
    skipped = 0
    errors = []

    # --- Part 1: Check for new labeled messages (new deals) ---
    label = settings.GMAIL_LABEL
    query = f"label:{label}"
    results = gmail.service.users().messages().list(
        userId="me", q=query, maxResults=10,
    ).execute()
    messages = results.get("messages", [])

    for msg_ref in (messages or []):
        message_id = msg_ref["id"]
        if _already_processed(message_id):
            skipped += 1
            continue
        try:
            did_process = _process_message(gmail, message_id)
            if did_process:
                processed += 1
            else:
                skipped += 1
        except Exception as e:
            logger.exception("Failed to process message %s", message_id)
            errors.append({"message_id": message_id, "error": str(e)})

    # --- Part 2: Check for follow-up replies on existing threads ---
    follow_ups = _check_thread_replies(gmail)
    processed += follow_ups.get("processed", 0)
    skipped += follow_ups.get("skipped", 0)
    errors.extend(follow_ups.get("errors", []))

    return {"status": "ok", "processed": processed, "skipped": skipped, "errors": errors}


def _check_thread_replies(gmail: GmailClient) -> dict:
    """Check all known email threads for new reply messages (follow-ups).

    Gmail replies don't inherit labels, so we need to check threads directly.
    """
    processed = 0
    skipped = 0
    errors = []

    with sync_session_factory() as db:
        threads = db.query(EmailThread).filter(
            EmailThread.gmail_thread_id.isnot(None),
            EmailThread.deal_id.isnot(None),
        ).all()
        thread_ids = [(t.gmail_thread_id, t.id, t.deal_id) for t in threads]

    for gmail_thread_id, db_thread_id, deal_id in thread_ids:
        try:
            thread_data = gmail.service.users().threads().get(
                userId="me", id=gmail_thread_id, format="minimal",
            ).execute()
        except Exception:
            continue

        for msg in thread_data.get("messages", []):
            msg_id = msg["id"]
            if _already_processed(msg_id):
                skipped += 1
                continue
            # Skip our own outbound messages (SENT label, no INBOX)
            labels = msg.get("labelIds", [])
            if "SENT" in labels and "INBOX" not in labels:
                skipped += 1
                continue
            try:
                did_process = _process_message(gmail, msg_id)
                if did_process:
                    processed += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.exception("Failed to process thread reply %s", msg_id)
                errors.append({"message_id": msg_id, "error": str(e)})

    return {"processed": processed, "skipped": skipped, "errors": errors}


def _process_message(gmail: GmailClient, message_id: str) -> bool:
    """Process a single inbound message — detect new deal or follow-up.

    Uses sync DB sessions to avoid asyncpg concurrency issues in Celery workers.
    Returns True if a deal action was taken, False if skipped.
    """
    import mimetypes
    import os

    from app.schemas.enums import EventType
    from app.storage.s3 import upload_bytes

    message = gmail.get_message(message_id)
    gmail_thread_id = message.get("threadId", "")
    sender_name, sender_email = extract_sender(message)
    subject = extract_header(message, "Subject") or "(no subject)"
    body_text = extract_body_text(message)

    logger.info("Processing message from %s <%s>: %s", sender_name, sender_email, subject)

    with sync_session_factory() as db:
        # Check if this Gmail thread is already linked to a deal (follow-up)
        existing_thread = db.query(EmailThread).filter(
            EmailThread.gmail_thread_id == gmail_thread_id
        ).first()

        if existing_thread and existing_thread.deal_id:
            # Follow-up on existing deal — set status to "reworking" so UI shows progress
            deal = db.query(Deal).filter(Deal.id == existing_thread.deal_id).first()
            if deal:
                deal.status = "reworking"
                deal.version += 1

            msg = EmailMessage(
                thread_id=existing_thread.id,
                gmail_message_id=message_id,
                direction="inbound",
                from_email=sender_email,
                from_name=sender_name,
                body_text=body_text,
            )
            db.add(msg)
            db.commit()
            logger.info(
                "Processing follow-up on deal %s from thread %s",
                existing_thread.deal_id, gmail_thread_id,
            )
            _trigger_followup(str(existing_thread.deal_id), str(existing_thread.id), body_text)
            return True

        # New deal — create from local scenario files
        system_user_id = _get_or_create_system_user(db)

        deal = Deal(
            deal_type="construction_loan",
            status="docs_received",
            property_name=_extract_deal_name(subject),
            created_by=system_user_id,
        )
        db.add(deal)
        db.flush()

        log_event_sync(
            db=db,
            deal_id=deal.id,
            event_type=EventType.DEAL_CREATED.value,
            payload={
                "source": "email",
                "sender": sender_email,
                "subject": subject,
                "gmail_thread_id": gmail_thread_id,
            },
        )

        # Upload documents from the local demo scenario directory
        uploaded = []
        if os.path.isdir(DEMO_SCENARIO_DIR):
            for filename in sorted(os.listdir(DEMO_SCENARIO_DIR)):
                filepath = os.path.join(DEMO_SCENARIO_DIR, filename)
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
                    uploaded_by=system_user_id,
                )
                db.add(doc)
                db.flush()
                log_event_sync(
                    db=db,
                    deal_id=deal.id,
                    event_type=EventType.DOC_UPLOADED.value,
                    payload={"document_id": str(doc.id), "filename": filename},
                )
                uploaded.append(filename)

        # Create email thread + message record
        thread = EmailThread(
            deal_id=deal.id,
            gmail_thread_id=gmail_thread_id,
            subject=subject,
            sender_email=sender_email,
            sender_name=sender_name,
        )
        db.add(thread)
        db.flush()

        msg = EmailMessage(
            thread_id=thread.id,
            gmail_message_id=message_id,
            direction="inbound",
            from_email=sender_email,
            from_name=sender_name,
            body_text=body_text,
            attachments=[{"filename": f} for f in uploaded],
        )
        db.add(msg)
        db.commit()

        logger.info(
            "Created new deal %s from email thread %s with %d documents",
            deal.id, gmail_thread_id, len(uploaded),
        )
        _trigger_pipeline(str(deal.id))
        return True


def _extract_deal_name(subject: str | None) -> str:
    """Try to extract a property/project name from the email subject."""
    if not subject:
        return "Email Deal"
    # Strip common prefixes
    for prefix in ("Re:", "Fwd:", "FW:", "RE:", "re:", "fwd:"):
        subject = subject.replace(prefix, "").strip()
    # Truncate if too long
    return subject[:200] if subject else "Email Deal"


def _trigger_pipeline(deal_id: str) -> None:
    """Trigger the agent pipeline for a newly created deal."""
    process_email_deal.delay(deal_id)


def _trigger_followup(deal_id: str, thread_id: str, body_text: str) -> None:
    """Trigger follow-up processing for an existing deal."""
    process_email_followup.delay(deal_id, thread_id, body_text)


@celery_app.task(bind=True, max_retries=1)
def process_email_deal(self, deal_id: str) -> dict:
    """Run the full agent pipeline for a deal created from email, then send the response."""
    deal_uuid = uuid.UUID(deal_id)

    async def _run():
        from app.agent.orchestrator import run_deal_pipeline_agent
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.config import settings

        # Create a fresh async engine for this event loop — the module-level engine
        # was created pre-fork and its asyncpg connections are bound to a different loop.
        fresh_engine = create_async_engine(settings.DATABASE_URL, echo=False)
        fresh_session = async_sessionmaker(fresh_engine, expire_on_commit=False)

        async with fresh_session() as db:
            try:
                results = await run_deal_pipeline_agent(db=db, deal_id=deal_uuid)
                await db.commit()
                return results
            except Exception as e:
                await db.rollback()
                logger.exception("Agent pipeline failed for email deal %s", deal_id)
                raise
            finally:
                await fresh_engine.dispose()

    pipeline_results = asyncio.run(_run())

    # Send the email response
    _send_deal_response(deal_id)

    return {
        "deal_id": deal_id,
        "pipeline_status": pipeline_results.get("pipeline_status", "unknown"),
        "email_sent": True,
    }


@celery_app.task(bind=True, max_retries=1)
def process_email_followup(self, deal_id: str, thread_id: str, body_text: str) -> dict:
    """Process a follow-up email: run the FollowUpAgent, then send updated deliverables."""
    deal_uuid = uuid.UUID(deal_id)
    thread_uuid = uuid.UUID(thread_id)

    # Extract just the new content (strip quoted text)
    new_content = extract_follow_up_content(body_text)

    async def _run():
        from app.agent.agents.followup_agent import FollowUpAgent
        from app.agent.harness import AgentResult
        from app.models.agent import AgentRun
        from app.services.context_engine import build_deal_context
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.config import settings
        from datetime import datetime, timezone

        fresh_engine = create_async_engine(settings.DATABASE_URL, echo=False)
        fresh_session = async_sessionmaker(fresh_engine, expire_on_commit=False)

        async with fresh_session() as db:
            try:
                context = await build_deal_context(db, deal_uuid, tags=["construction_loan"])
                agent = FollowUpAgent()
                goal = (
                    f"The client sent a follow-up email with this message:\n\n"
                    f"---\n{new_content}\n---\n\n"
                    f"Process their request and produce updated deliverables."
                )

                result = await agent.run(
                    goal=goal, deal_context=context, db=db, deal_id=deal_uuid,
                )

                # Log the agent run
                run = AgentRun(
                    deal_id=deal_uuid,
                    agent_name=agent.name,
                    goal=goal[:500],
                    status="completed" if result.success else "failed",
                    iterations=result.iterations,
                    reasoning_trace=result.reasoning_trace,
                    result=result.data if isinstance(result.data, dict) else {"data": str(result.data)},
                    error=result.error,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                db.add(run)
                await db.commit()

                return result
            except Exception:
                await db.rollback()
                logger.exception("Follow-up agent failed for deal %s", deal_id)
                raise
            finally:
                await fresh_engine.dispose()

    agent_result = asyncio.run(_run())

    # Send the follow-up response
    _send_followup_response(deal_id, thread_id, agent_result)

    return {
        "deal_id": deal_id,
        "thread_id": thread_id,
        "followup_status": "completed" if agent_result.success else "failed",
        "email_sent": True,
    }


def _send_deal_response(deal_id: str) -> None:
    """Generate email summary and send the response with deliverables.

    Uses sync DB + sync S3 to avoid asyncio event loop conflicts in Celery workers.
    Also creates OMVersion and RiskReport records so the UI displays them.
    """
    from app.email.client import GmailClient
    from app.email.composer import build_response_html

    deal_uuid = uuid.UUID(deal_id)

    with sync_session_factory() as db:
        # Get the email thread for this deal
        thread = db.query(EmailThread).filter(EmailThread.deal_id == deal_uuid).first()
        if not thread:
            logger.error("No email thread found for deal %s", deal_id)
            return

        deal = db.query(Deal).filter(Deal.id == deal_uuid).first()
        deal_name = deal.property_name or "Deal" if deal else "Deal"

        # Gather deliverables (sync version)
        deliverables = _gather_deliverables_sync(db, deal_uuid, deal_name)
        attachment_names = [d["filename"] for d in deliverables]

        # Create OMVersion + RiskReport records so the UI shows them
        _create_deliverable_records(db, deal_uuid, deliverables, version_number=1)

        # Build summary (simple, no agent call — avoids async issues)
        summary_html = "<p>Your deal analysis is complete. Please see the attached deliverables.</p>"

        html_body = build_response_html(
            sender_name=thread.sender_name,
            deal_name=deal_name,
            summary_text=summary_html,
            attachments_included=attachment_names,
        )

        # Get the original message ID for threading
        original_msg = (
            db.query(EmailMessage)
            .filter(EmailMessage.thread_id == thread.id, EmailMessage.direction == "inbound")
            .order_by(EmailMessage.sent_at.desc())
            .first()
        )
        in_reply_to = original_msg.gmail_message_id if original_msg else ""

        # Send via Gmail
        gmail = GmailClient()
        send_result = gmail.send_reply(
            thread_id=thread.gmail_thread_id,
            in_reply_to_message_id=in_reply_to,
            to=thread.sender_email,
            subject=f"Re: {thread.subject}",
            body_html=html_body,
            attachments=deliverables,
        )

        # Record the outbound message
        outbound_msg = EmailMessage(
            thread_id=thread.id,
            gmail_message_id=send_result["id"],
            direction="outbound",
            from_email=settings.GMAIL_MONITORED_ADDRESS,
            body_html=html_body,
            attachments=[{"filename": d["filename"]} for d in deliverables],
        )
        db.add(outbound_msg)
        db.commit()

        logger.info("Sent deal response for %s to %s with %d attachments",
                     deal_id, thread.sender_email, len(deliverables))


def _send_followup_response(deal_id: str, thread_id: str, agent_result) -> None:
    """Send the follow-up response email with updated deliverables."""
    from app.email.client import GmailClient
    from app.email.composer import build_followup_response_html

    deal_uuid = uuid.UUID(deal_id)
    thread_uuid = uuid.UUID(thread_id)

    with sync_session_factory() as db:
        thread = db.query(EmailThread).filter(EmailThread.id == thread_uuid).first()
        if not thread:
            logger.error("No email thread found with id %s", thread_id)
            return

        deal = db.query(Deal).filter(Deal.id == deal_uuid).first()
        deal_name = deal.property_name or "Deal" if deal else "Deal"

        # Extract response from agent result
        response_html = ""
        changes_made = []
        if agent_result.success and isinstance(agent_result.data, dict):
            response_html = agent_result.data.get("response_html", "")
            changes_made = agent_result.data.get("changes_made", [])
        if not response_html:
            response_html = "<p>We've updated the analysis based on your feedback.</p>"
        if not changes_made:
            changes_made = ["Updated deliverables based on your request"]

        deliverables = _gather_deliverables_sync(db, deal_uuid, deal_name, is_followup=True)
        attachment_names = [d["filename"] for d in deliverables]

        # Create v2 OMVersion + RiskReport records for the updated deliverables
        _create_deliverable_records(db, deal_uuid, deliverables, version_number=2)

        html_body = build_followup_response_html(
            sender_name=thread.sender_name,
            deal_name=deal_name,
            response_text=response_html,
            changes_made=changes_made,
            attachments_included=attachment_names,
        )

        latest_msg = (
            db.query(EmailMessage)
            .filter(EmailMessage.thread_id == thread.id, EmailMessage.direction == "inbound")
            .order_by(EmailMessage.sent_at.desc())
            .first()
        )
        in_reply_to = latest_msg.gmail_message_id if latest_msg else ""

        gmail = GmailClient()
        send_result = gmail.send_reply(
            thread_id=thread.gmail_thread_id,
            in_reply_to_message_id=in_reply_to,
            to=thread.sender_email,
            subject=f"Re: {thread.subject}",
            body_html=html_body,
            attachments=deliverables,
        )

        outbound_msg = EmailMessage(
            thread_id=thread.id,
            gmail_message_id=send_result["id"],
            direction="outbound",
            from_email=settings.GMAIL_MONITORED_ADDRESS,
            body_html=html_body,
            attachments=[{"filename": d["filename"]} for d in deliverables],
        )
        db.add(outbound_msg)

        # Set status back to om_review after reworking is done
        deal = db.query(Deal).filter(Deal.id == deal_uuid).first()
        if deal and deal.status == "reworking":
            deal.status = "om_review"
            deal.version += 1

        db.commit()

        logger.info("Sent follow-up response for deal %s to %s", deal_id, thread.sender_email)


DEMO_FIRST_PASS_DIR = os.getenv("PLUMB_DEMO_FIRST_PASS_DIR", "")
DEMO_SECOND_PASS_DIR = os.getenv("PLUMB_DEMO_SECOND_PASS_DIR", "")


def _create_deliverable_records(db, deal_id: uuid.UUID, deliverables: list[dict], version_number: int = 1) -> None:
    """Create OMVersion and RiskReport DB records from demo deliverables so the UI displays them."""
    from app.models.om import OMVersion
    from app.models.risk import RiskReport

    for d in deliverables:
        data = d["data"]
        filename = d["filename"]
        mime = d["mime_type"]

        if "offering_memorandum" in filename.lower() or "om" in filename.lower():
            s3_key = f"deals/{deal_id}/om/v{version_number}/om.pdf"
            upload_bytes(data, s3_key, mime)

            # Mark previous versions as superseded
            db.query(OMVersion).filter(
                OMVersion.deal_id == deal_id,
                OMVersion.status == "ready",
            ).update({"status": "superseded"})

            om = OMVersion(
                deal_id=deal_id,
                version_number=version_number,
                s3_key=s3_key,
                page_count=None,
                file_size=len(data),
                status="ready",
            )
            db.add(om)
            logger.info("Created OMVersion v%d for deal %s", version_number, deal_id)

        elif "risk" in filename.lower():
            s3_key = f"deals/{deal_id}/risk/v{version_number}/risk_report.pdf"
            upload_bytes(data, s3_key, mime)

            db.query(RiskReport).filter(
                RiskReport.deal_id == deal_id,
                RiskReport.status == "ready",
            ).update({"status": "superseded"})

            rr = RiskReport(
                deal_id=deal_id,
                version_number=version_number,
                s3_key=s3_key,
                page_count=None,
                file_size=len(data),
                status="ready",
            )
            db.add(rr)
            logger.info("Created RiskReport v%d for deal %s", version_number, deal_id)

    db.flush()


def _gather_deliverables_sync(db, deal_id: uuid.UUID, deal_name: str, is_followup: bool = False) -> list[dict]:
    """Gather deliverables from local demo files for email attachment."""
    import os

    attachments = []
    safe_name = deal_name.replace(" ", "_")

    # Use second_pass for follow-ups, first_pass for initial response
    demo_dir = DEMO_SECOND_PASS_DIR if is_followup else DEMO_FIRST_PASS_DIR

    if not os.path.isdir(demo_dir):
        logger.warning("Demo documents dir not found: %s", demo_dir)
        return attachments

    for filename in sorted(os.listdir(demo_dir)):
        filepath = os.path.join(demo_dir, filename)
        if not os.path.isfile(filepath) or filename.startswith("."):
            continue

        with open(filepath, "rb") as f:
            data = f.read()

        # Map filenames to clean attachment names
        if "om" in filename.lower():
            clean_name = f"{safe_name}_Offering_Memorandum.pdf"
            mime = "application/pdf"
        elif "risk" in filename.lower():
            clean_name = f"{safe_name}_Risk_Assessment.pdf"
            mime = "application/pdf"
        elif "financial" in filename.lower() or filename.endswith(".xlsx"):
            clean_name = f"{safe_name}_Financial_Model.xlsx"
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            clean_name = filename
            mime = "application/octet-stream"

        attachments.append({
            "filename": clean_name,
            "data": data,
            "mime_type": mime,
        })

    logger.info("Gathered %d deliverables from %s", len(attachments), demo_dir)
    return attachments
