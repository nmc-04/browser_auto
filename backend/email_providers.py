"""Email provider adapters used by the workflow execution engine.

The application keeps provider-specific code behind this small interface.  The
Gmail adapter uses OAuth 2.0 and the Gmail API.  The local adapter is only for
controlled demos and automated tests; it labels every result as simulated and
never represents a message as delivered to a recipient.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from email.message import EmailMessage
from email.utils import parseaddr
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from utils.helpers import current_iso_time, generate_id
from utils.logger import add_log_entry, logger

load_dotenv(override=True)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class EmailProviderError(RuntimeError):
    """A provider operation could not be completed."""


class EmailNotConfiguredError(EmailProviderError):
    """The provider has not been configured or authorized."""


class EmailPendingVerification(EmailProviderError):
    """Submission started but provider evidence is not yet conclusive."""


def _repo_path(value: str) -> str:
    """Resolve a configured relative path from the project directory."""
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str(Path(__file__).resolve().parent.parent / path)


def _safe_headers(payload: Dict[str, Any]) -> Dict[str, str]:
    headers = {}
    for header in payload.get("headers", []) or []:
        name = str(header.get("name", "")).lower()
        if name in {"from", "to", "cc", "bcc", "subject", "date", "message-id"}:
            headers[name] = str(header.get("value", ""))
    return headers


class BaseEmailProvider:
    name = "email"
    mode = "unknown"

    def connection_status(self) -> Dict[str, Any]:
        return {"provider": self.name, "mode": self.mode, "connected": False}

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def read(self, email_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def send(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def verify(self, provider_message_id: str, expected: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError


class DemoEmailProvider(BaseEmailProvider):
    """Local fixture provider for demos and tests.

    It reads the checked-in inbox fixture and writes sent records to the same
    local fixture store used by the original project.  Results are explicitly
    marked ``SIMULATED`` so the UI cannot confuse them with a Gmail submission.
    """

    name = "Local fixture"
    mode = "demo"

    def __init__(self, inbox_file: Optional[str] = None, sent_file: Optional[str] = None):
        self.inbox_file = _repo_path(inbox_file or os.getenv("EMAIL_INBOX_FILE", "demo_data/emails.json"))
        self.sent_file = _repo_path(sent_file or os.getenv("EMAIL_SENT_FILE", "demo_data/sent_emails.json"))

    def _load(self, path: str) -> List[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, list) else []
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Unable to read local email fixture %s: %s", path, exc)
            return []

    def _save(self, path: str, value: List[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)

    def connection_status(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "mode": self.mode,
            "connected": True,
            "external_send": False,
            "message": "Local fixture mode. No external email is sent.",
        }

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        messages = self._load(self.inbox_file)
        text = (query or "").strip().lower()
        if not text:
            return messages[:limit]

        # Support both simple natural-language search and common Gmail-style
        # operators so the same workflow works when switched to Gmail.
        operators = re.findall(r"(from|to|subject|after|before|is|newer_than):([^\s]+)", text)
        terms = re.sub(r"(?:from|to|subject|after|before|is|newer_than):[^\s]+", "", text).strip()
        tokens = [token for token in re.findall(r"[\w@.-]+", terms) if token]

        def matches(message: Dict[str, Any]) -> bool:
            sender = str(message.get("from", "")).lower()
            recipient = str(message.get("to", "")).lower()
            subject = str(message.get("subject", "")).lower()
            body = str(message.get("body", "")).lower()
            haystack = " ".join([sender, recipient, subject, body])
            for field, value in operators:
                value = value.lower()
                if field == "from" and value not in sender:
                    return False
                if field == "to" and value not in recipient:
                    return False
                if field == "subject" and value not in subject:
                    return False
                if field == "is" and value == "unread" and message.get("read") is True:
                    return False
                if field == "newer_than" and value.endswith("d") and "today" not in str(message.get("date", "")).lower():
                    return False
            return all(token in haystack for token in tokens) or (not tokens and not operators)

        return [message for message in messages if matches(message)][:limit]

    def read(self, email_id: str) -> Optional[Dict[str, Any]]:
        return next((item for item in self._load(self.inbox_file) if item.get("id") == email_id), None)

    def send(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        sent = self._load(self.sent_file)
        recipient = draft.get("to", "").strip().lower()
        subject = draft.get("subject", "").strip()
        key = draft.get("idempotency_key")
        for item in reversed(sent):
            same_key = key and item.get("idempotency_key") == key
            same_message = (
                item.get("to", "").strip().lower() == recipient
                and item.get("subject", "") == subject
                and set(os.path.basename(path) for path in item.get("attachments", []))
                == set(os.path.basename(path) for path in draft.get("attachments", []))
            )
            if same_key or same_message:
                return {
                    **item,
                    "status": "SKIPPED",
                    "simulated": True,
                    "verification_status": "DUPLICATE_PREVENTED",
                    "verification_evidence": {"local_record_id": item.get("email_id")},
                }

        record = {
            "email_id": generate_id("demo_msg"),
            "draft_id": draft.get("draft_id"),
            "idempotency_key": key,
            "to": draft.get("to"),
            "client_name": draft.get("client_name"),
            "subject": subject,
            "body": draft.get("body", ""),
            "attachments": draft.get("attachments", []),
            "invoice_number": draft.get("invoice_number"),
            "sent_at": current_iso_time(),
            "status": "SIMULATED",
            "simulated": True,
            "verified": True,
            "verification_status": "SIMULATED_LOCAL_RECORD",
            "verification_evidence": {"local_record_id": None},
        }
        record["verification_evidence"]["local_record_id"] = record["email_id"]
        sent.append(record)
        self._save(self.sent_file, sent)
        add_log_entry(f"[Email Tool] Simulated local email record for '{record['to']}'")
        return record

    def verify(self, provider_message_id: str, expected: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        for item in reversed(self._load(self.sent_file)):
            if item.get("email_id") == provider_message_id:
                return {
                    "verified": True,
                    "status": item.get("status", "SIMULATED"),
                    "provider_message_id": provider_message_id,
                    "verification_status": item.get("verification_status", "SIMULATED_LOCAL_RECORD"),
                    "evidence": item.get("verification_evidence", {}),
                    "delivery_confirmed": False,
                }
        return {
            "verified": False,
            "status": "PENDING_VERIFICATION",
            "provider_message_id": provider_message_id,
            "verification_status": "LOCAL_RECORD_NOT_FOUND",
            "evidence": {},
            "delivery_confirmed": False,
        }


class GmailProvider(BaseEmailProvider):
    """Gmail API provider using OAuth 2.0 user authorization."""

    name = "Gmail"
    mode = "gmail"

    def __init__(self, credentials_file: Optional[str] = None, token_file: Optional[str] = None):
        self.credentials_file = _repo_path(credentials_file or os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json"))
        self.token_file = _repo_path(token_file or os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json"))
        self._service = None
        self._credentials = None

    @staticmethod
    def _imports_available() -> bool:
        try:
            import googleapiclient.discovery  # noqa: F401
            import google_auth_oauthlib.flow  # noqa: F401
            import google.oauth2.credentials  # noqa: F401
            return True
        except ImportError:
            return False

    def connection_status(self) -> Dict[str, Any]:
        if not self._imports_available():
            return {"provider": self.name, "mode": self.mode, "connected": False, "reason": "Google API dependencies are not installed."}
        if not os.path.exists(self.credentials_file):
            return {"provider": self.name, "mode": self.mode, "connected": False, "reason": "GMAIL_CREDENTIALS_FILE is missing."}
        if not os.path.exists(self.token_file):
            return {"provider": self.name, "mode": self.mode, "connected": False, "reason": "Gmail account has not been authorized yet."}
        try:
            self._get_service()
            profile = self._service.users().getProfile(userId="me").execute()
            return {
                "provider": self.name,
                "mode": self.mode,
                "connected": True,
                "account": profile.get("emailAddress"),
                "scopes": GMAIL_SCOPES,
                "external_send": True,
            }
        except Exception as exc:
            return {"provider": self.name, "mode": self.mode, "connected": False, "reason": str(exc)}

    def connect(self) -> Dict[str, Any]:
        if not self._imports_available():
            raise EmailNotConfiguredError("Install Gmail API dependencies before connecting a Gmail account.")
        if not os.path.exists(self.credentials_file):
            raise EmailNotConfiguredError(
                f"Add the OAuth desktop-app client file at '{self.credentials_file}' or set GMAIL_CREDENTIALS_FILE."
            )
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, GMAIL_SCOPES)
        credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        os.makedirs(os.path.dirname(self.token_file) or ".", exist_ok=True)
        with open(self.token_file, "w", encoding="utf-8") as handle:
            handle.write(credentials.to_json())
        self._credentials = credentials
        self._service = None
        return self.connection_status()

    def _get_service(self):
        if self._service is not None:
            return self._service
        if not self._imports_available():
            raise EmailNotConfiguredError("Google API dependencies are not installed.")
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = None
        if os.path.exists(self.token_file):
            credentials = Credentials.from_authorized_user_file(self.token_file, GMAIL_SCOPES)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            with open(self.token_file, "w", encoding="utf-8") as handle:
                handle.write(credentials.to_json())
        if not credentials or not credentials.valid:
            raise EmailNotConfiguredError(
                "Gmail account is not authorized. Use the Connect Gmail control before reading or sending email."
            )
        self._credentials = credentials
        self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        return self._service

    @staticmethod
    def _decode(data: str) -> str:
        if not data:
            return ""
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode((data + padding).encode("utf-8")).decode("utf-8", errors="replace")

    def _flatten_parts(self, part: Dict[str, Any], message_id: str, result: Dict[str, Any]) -> None:
        filename = part.get("filename") or ""
        body = part.get("body", {}) or {}
        if filename and body.get("attachmentId"):
            result.setdefault("attachments", []).append(
                {"filename": filename, "attachment_id": body.get("attachmentId"), "mime_type": part.get("mimeType")}
            )
        data = body.get("data")
        mime_type = part.get("mimeType", "")
        if data and mime_type == "text/plain":
            result["body"] += self._decode(data)
        elif data and mime_type == "text/html" and not result.get("body"):
            result["body"] = re.sub(r"<[^>]+>", " ", unescape(self._decode(data)))
        for child in part.get("parts", []) or []:
            self._flatten_parts(child, message_id, result)

    def _normalize(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {}) or {}
        headers = _safe_headers(payload)
        result = {
            "id": message.get("id"),
            "message_id": message.get("id"),
            "thread_id": message.get("threadId"),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "body": "",
            "attachments": [],
            "label_ids": message.get("labelIds", []),
        }
        self._flatten_parts(payload, str(message.get("id", "")), result)
        return result

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        service = self._get_service()
        response = service.users().messages().list(userId="me", q=query or "", maxResults=limit).execute()
        results = []
        for ref in response.get("messages", []) or []:
            message = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
            results.append(self._normalize(message))
        return results

    def read(self, email_id: str) -> Optional[Dict[str, Any]]:
        service = self._get_service()
        try:
            message = service.users().messages().get(userId="me", id=email_id, format="full").execute()
        except Exception:
            return None
        return self._normalize(message)

    def download_attachment(self, email_id: str, attachment_id: str, filename: str) -> str:
        service = self._get_service()
        response = service.users().messages().attachments().get(userId="me", messageId=email_id, id=attachment_id).execute()
        data = base64.urlsafe_b64decode((response.get("data", "") + "=" * 3).encode("utf-8"))
        output_dir = Path(_repo_path(os.getenv("EMAIL_DOWNLOAD_DIR", "downloads/email_attachments")))
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / Path(filename).name
        output.write_bytes(data)
        return str(output)

    def send(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        service = self._get_service()
        message = EmailMessage()
        message["To"] = draft["to"]
        message["Subject"] = draft["subject"]
        message.set_content(draft.get("body", ""))
        for path in draft.get("attachments", []):
            file_path = Path(path)
            content_type, _ = mimetypes.guess_type(file_path.name)
            maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
            message.add_attachment(file_path.read_bytes(), maintype=maintype, subtype=subtype, filename=file_path.name)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        response = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        provider_id = response.get("id")
        if not provider_id:
            raise EmailPendingVerification("Gmail accepted the request without returning a message ID.")
        return {
            "email_id": provider_id,
            "provider_message_id": provider_id,
            "thread_id": response.get("threadId"),
            "to": draft.get("to"),
            "subject": draft.get("subject"),
            "body": draft.get("body", ""),
            "attachments": draft.get("attachments", []),
            "sent_at": current_iso_time(),
            "status": "SENT",
            "simulated": False,
            "verification_status": "PROVIDER_ACCEPTED",
            "verification_evidence": {"provider": "Gmail", "message_id": provider_id},
        }

    def verify(self, provider_message_id: str, expected: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        service = self._get_service()
        try:
            message = service.users().messages().get(
                userId="me", id=provider_message_id, format="metadata", metadataHeaders=["To", "Subject"]
            ).execute()
        except Exception as exc:
            logger.warning("Gmail verification is inconclusive for %s: %s", provider_message_id, exc)
            return {
                "verified": False,
                "status": "PENDING_VERIFICATION",
                "provider_message_id": provider_message_id,
                "verification_status": "PROVIDER_LOOKUP_INCONCLUSIVE",
                "evidence": {"provider": "Gmail", "error": str(exc)},
                "delivery_confirmed": False,
            }
        headers = _safe_headers(message.get("payload", {}) or {})
        return {
            "verified": True,
            "status": "SENT",
            "provider_message_id": provider_message_id,
            "verification_status": "PROVIDER_MESSAGE_FOUND",
            "evidence": {
                "provider": "Gmail",
                "message_id": provider_message_id,
                "label_ids": message.get("labelIds", []),
                "to": headers.get("to"),
                "subject": headers.get("subject"),
            },
            "delivery_confirmed": False,
        }

