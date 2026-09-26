"""Gmail API client wrapper for reading, sending, and replying to emails."""

import base64
import logging
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _get_credentials() -> Credentials:
    """Load or refresh Gmail OAuth2 credentials."""
    creds = None
    token_path = settings.GMAIL_TOKEN_JSON

    if token_path and os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    elif not creds or not creds.valid:
        creds_path = settings.GMAIL_CREDENTIALS_JSON
        if not creds_path or not os.path.exists(creds_path):
            raise RuntimeError(
                f"Gmail credentials file not found at '{creds_path}'. "
                "Run `python -m app.email.auth_setup` to set up Gmail OAuth."
            )
        flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
        creds = flow.run_local_server(port=0)
        if token_path:
            with open(token_path, "w") as f:
                f.write(creds.to_json())

    return creds


def get_gmail_service():
    """Build and return a Gmail API service client."""
    creds = _get_credentials()
    return build("gmail", "v1", credentials=creds)


class GmailClient:
    """High-level wrapper around the Gmail API for Plumb's email integration."""

    def __init__(self):
        self._service = None

    @property
    def service(self):
        if self._service is None:
            self._service = get_gmail_service()
        return self._service

    def list_unread_messages(self, max_results: int = 20) -> list[dict]:
        """List unread messages in inbox, newest first."""
        results = self.service.users().messages().list(
            userId="me",
            q="is:unread in:inbox",
            maxResults=max_results,
        ).execute()
        return results.get("messages", [])

    def get_message(self, message_id: str) -> dict:
        """Get full message details including payload."""
        return self.service.users().messages().get(
            userId="me",
            id=message_id,
            format="full",
        ).execute()

    def get_thread(self, thread_id: str) -> dict:
        """Get full thread with all messages."""
        return self.service.users().threads().get(
            userId="me",
            id=thread_id,
            format="full",
        ).execute()

    def mark_as_read(self, message_id: str) -> None:
        """Remove UNREAD label from a message."""
        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

    def get_attachments(self, message_id: str, message: dict | None = None) -> list[dict]:
        """Extract attachment metadata and data from a message.

        Returns list of {filename, mime_type, data (bytes), size}.
        """
        if message is None:
            message = self.get_message(message_id)

        attachments = []
        parts = message.get("payload", {}).get("parts", [])

        for part in parts:
            filename = part.get("filename")
            if not filename:
                continue

            mime_type = part.get("mimeType", "application/octet-stream")
            body = part.get("body", {})
            attachment_id = body.get("attachmentId")

            if attachment_id:
                att_data = self.service.users().messages().attachments().get(
                    userId="me",
                    messageId=message_id,
                    id=attachment_id,
                ).execute()
                data = base64.urlsafe_b64decode(att_data["data"])
            elif body.get("data"):
                data = base64.urlsafe_b64decode(body["data"])
            else:
                continue

            attachments.append({
                "filename": filename,
                "mime_type": mime_type,
                "data": data,
                "size": len(data),
            })

        return attachments

    def send_reply(
        self,
        thread_id: str,
        in_reply_to_message_id: str,
        to: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        """Send a reply in an existing thread with optional file attachments.

        attachments: list of {filename, data (bytes), mime_type}
        """
        msg = MIMEMultipart("mixed")
        msg["To"] = to
        msg["Subject"] = subject
        msg["In-Reply-To"] = in_reply_to_message_id
        msg["References"] = in_reply_to_message_id

        # Body — HTML preferred, plain text fallback
        body_part = MIMEMultipart("alternative")
        if body_text:
            body_part.attach(MIMEText(body_text, "plain"))
        body_part.attach(MIMEText(body_html, "html"))
        msg.attach(body_part)

        # Attachments
        for att in (attachments or []):
            part = MIMEApplication(att["data"], Name=att["filename"])
            part["Content-Disposition"] = f'attachment; filename="{att["filename"]}"'
            msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        result = self.service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id},
        ).execute()

        logger.info("Sent reply message %s in thread %s", result["id"], thread_id)
        return result

    def send_new(
        self,
        to: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        """Send a new email (not a reply)."""
        msg = MIMEMultipart("mixed")
        msg["To"] = to
        msg["Subject"] = subject

        body_part = MIMEMultipart("alternative")
        if body_text:
            body_part.attach(MIMEText(body_text, "plain"))
        body_part.attach(MIMEText(body_html, "html"))
        msg.attach(body_part)

        for att in (attachments or []):
            part = MIMEApplication(att["data"], Name=att["filename"])
            part["Content-Disposition"] = f'attachment; filename="{att["filename"]}"'
            msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        result = self.service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()

        logger.info("Sent new message %s", result["id"])
        return result


def extract_header(message: dict, header_name: str) -> str | None:
    """Extract a specific header from a Gmail message payload."""
    headers = message.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"].lower() == header_name.lower():
            return h["value"]
    return None


def extract_body_text(message: dict) -> str:
    """Extract plain text body from a Gmail message."""
    payload = message.get("payload", {})

    # Simple message (no parts)
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    # Multipart message — walk parts looking for text/plain
    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        # Nested multipart/alternative
        for sub in part.get("parts", []):
            if sub.get("mimeType") == "text/plain" and sub.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(sub["body"]["data"]).decode("utf-8", errors="replace")

    return ""


def extract_sender(message: dict) -> tuple[str, str]:
    """Extract sender name and email from a message. Returns (name, email)."""
    from_header = extract_header(message, "From") or ""
    # Format: "Name <email@example.com>" or just "email@example.com"
    if "<" in from_header:
        name = from_header.split("<")[0].strip().strip('"')
        email = from_header.split("<")[1].rstrip(">").strip()
    else:
        name = ""
        email = from_header.strip()
    return name, email
