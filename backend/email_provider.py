"""Provider boundary for email automation.

The application deliberately keeps email transport behind a small interface.  The
local provider is useful for deterministic development and tests; the Gmail
provider uses OAuth 2.0 and the Gmail API when explicitly configured.  No provider
stores or accepts an email password.
"""

from __future__ import annotations

import base64
import os
import re
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from utils.logger import add_log_entry, logger
from utils.helpers import current_iso_time, generate_id


class EmailProviderError(RuntimeError):
    """An email provider could not complete an operation."""


class EmailAuthenticationError(EmailProviderError):
    """The provider is not authorized or its authorization has expired."""


class BaseEmailProvider:
    name = "base"

    def status(self) -> Dict[str, Any]:
        return {"provider": self.name, "connected": False, "message": "Not configured."}

    def search(self, query: str = "", limit: int = 25) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def read(self, message_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def send(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def verify(self, provider_message_id: str) -> Dict[str, Any]:
        raise NotImplementedError


def _safe_headers(value: Any) -> Dict[str, str]:
    """Convert provider headers into a case-insensitive-friendly dictionary."""
    if isinstance(value, dict):
        return {str(k).lower(): str(v) for k, v in value.items()}
    return {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in (value or [])}


class LocalDemoEmailProvider(BaseEmailProvider):
    """JSON-backed provider used only when EMAIL_PROVIDER=demo (the default)."""

    name = "demo"

    def __init__(self, inbox_path: str, sent_path: str):
        self.inbox_path = inbox_path
        self.sent_path = sent_path

    @staticmethod
    def _load(path: str) -> List[Dict[str, Any]]:
        import json

        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, list) else []
        except (OSError, ValueError) as exc:
            logger.warning("Unable to read local email store: %s", exc)
            return []

    def _save(self, path: str, data: List[Dict[str, Any]]) -> None:
        import json

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "connected": True,
            "account": "local-demo",
            "message": "Local demo mailbox connected; no external email will be sent.",
        }

    def search(self, query: str = "", limit: int = 25) -> List[Dict[str, Any]]:
        messages = self._load(self.inbox_path)
        if not query:
            return messages[:limit]
        tokens = [t for t in re.findall(r"[\w@.+-]+", query.lower()) if len(t) > 1]
        matches = []
        for message in messages:
            haystack = " ".join(
                str(message.get(key, "")) for key in ("subject", "body", "from", "to", "date", "timestamp")
            ).lower()
            if all(token in haystack for token in tokens):
                matches.append(self._normalise(message))
        return matches[:limit]

    def read(self, message_id: str) -> Optional[Dict[str, Any]]:
        for message in self._load(self.inbox_path):
            if str(message.get("id") or message.get("email_id")) == str(message_id):
                return self._normalise(message)
        return None

    def send(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        message_id = generate_id("demo_msg")
        record = {
            "email_id": message_id,
            "provider_message_id": message_id,
            "draft_id": draft.get("draft_id"),
            "operation_key": draft.get("operation_key"),
            "to": draft.get("to"),
            "client_name": draft.get("client_name"),
            "subject": draft.get("subject"),
            "body": draft.get("body"),
            "attachments": draft.get("attachments", []),
            "invoice_number": draft.get("invoice_number"),
            "sent_at": current_iso_time(),
            "status": "SENT",
            "provider": self.name,
            "accepted": True,
            "delivery_status": "UNKNOWN",
            "verified": True,
        }
        sent = self._load(self.sent_path)
        sent.append(record)
        self._save(self.sent_path, sent)
        return {
            **record,
            "verification": {
                "status": "SENT",
                "evidence": "Local demo provider recorded the message.",
                "provider_message_id": message_id,
            },
        }

    def verify(self, provider_message_id: str) -> Dict[str, Any]:
        for message in reversed(self._load(self.sent_path)):
            if str(message.get("provider_message_id") or message.get("email_id")) == str(provider_message_id):
                return {
                    "status": "SENT",
                    "verified": True,
                    "evidence": "Message record exists in the local sent store.",
                    "provider_message_id": provider_message_id,
                    "delivery_status": "UNKNOWN",
                }
        return {
            "status": "PENDING_VERIFICATION",
            "verified": False,
            "evidence": "No matching local provider record was found.",
            "provider_message_id": provider_message_id,
        }

    @staticmethod
    def _normalise(message: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **message,
            "id": message.get("id") or message.get("email_id"),
            "from": message.get("from", ""),
            "to": message.get("to", ""),
            "subject": message.get("subject", ""),
            "body": message.get("body", ""),
            "timestamp": message.get("timestamp") or message.get("date", ""),
            "attachments": message.get("attachments", []),
            "provider": "demo",
        }


class GmailEmailProvider(BaseEmailProvider):
    """Gmail API provider using an installed-app OAuth 2.0 flow."""

    name = "gmail"
    DEFAULT_SCOPES = (
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    )

    def __init__(self, credentials_file: Optional[str] = None, token_file: Optional[str] = None, scopes: Optional[Iterable[str]] = None):
        self.credentials_file = credentials_file or os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
        self.token_file = token_file or os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json")
        configured_scopes = scopes or [s.strip() for s in os.getenv("GMAIL_SCOPES", "").split(",") if s.strip()]
        self.scopes = list(configured_scopes or self.DEFAULT_SCOPES)
        self._service = None

    def status(self) -> Dict[str, Any]:
        if not os.path.exists(self.credentials_file):
            return {
                "provider": self.name,
                "connected": False,
                "message": f"Add the OAuth client file at '{self.credentials_file}' to connect Gmail.",
            }
        try:
            service = self._get_service(interactive=False)
            profile = service.users().getProfile(userId="me").execute()
            return {"provider": self.name, "connected": True, "account": profile.get("emailAddress"), "message": "Gmail OAuth connected."}
        except FileNotFoundError:
            return {"provider": self.name, "connected": False, "message": "Gmail OAuth is not authorized yet. Use the Connect Gmail action."}
        except EmailAuthenticationError as exc:
            return {"provider": self.name, "connected": False, "message": str(exc)}
        except Exception as exc:
            logger.warning("Gmail status check failed: %s", exc)
            return {"provider": self.name, "connected": False, "message": "Gmail connection could not be verified."}

    def connect(self) -> Dict[str, Any]:
        service = self._get_service(interactive=True)
        profile = service.users().getProfile(userId="me").execute()
        return {"provider": self.name, "connected": True, "account": profile.get("emailAddress"), "message": "Gmail OAuth connected."}

    def _get_service(self, interactive: bool = False):
        if self._service is not None:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise EmailProviderError("Gmail support requires google-api-python-client, google-auth-oauthlib, and google-auth-httplib2.") from exc

        credentials = None
        if os.path.exists(self.token_file):
            credentials = Credentials.from_authorized_user_file(self.token_file, self.scopes)
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception as exc:
                raise EmailAuthenticationError("Gmail authorization expired or was revoked. Reconnect the Gmail account.") from exc
        if not credentials or not credentials.valid:
            if not interactive:
                raise FileNotFoundError(self.token_file)
            if not os.path.exists(self.credentials_file):
                raise EmailProviderError(f"OAuth client file not found: {self.credentials_file}")
            flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, self.scopes)
            credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        os.makedirs(os.path.dirname(os.path.abspath(self.token_file)) or ".", exist_ok=True)
        with open(self.token_file, "w", encoding="utf-8") as handle:
            handle.write(credentials.to_json())
        self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        return self._service

    def _service_or_error(self):
        try:
            return self._get_service(interactive=False)
        except FileNotFoundError as exc:
            raise EmailAuthenticationError("Gmail is not connected. Authorize the account before reading or sending email.") from exc

    def search(self, query: str = "", limit: int = 25) -> List[Dict[str, Any]]:
        service = self._service_or_error()
        response = service.users().messages().list(userId="me", q=query or "in:anywhere", maxResults=limit).execute()
        messages = []
        for item in response.get("messages", []):
            message = self.read(item.get("id"))
            if message:
                messages.append(message)
        return messages

    def read(self, message_id: str) -> Optional[Dict[str, Any]]:
        service = self._service_or_error()
        raw = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        if not raw:
            return None
        payload = raw.get("payload", {})
        headers = _safe_headers(payload.get("headers"))
        body = self._find_text(payload)
        attachments = self._find_attachments(payload)
        return {
            "id": raw.get("id"),
            "thread_id": raw.get("threadId"),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "timestamp": headers.get("date", "") or raw.get("internalDate", ""),
            "body": body,
            "attachments": attachments,
            "label_ids": raw.get("labelIds", []),
            "provider": self.name,
        }

    @staticmethod
    def _find_text(payload: Dict[str, Any]) -> str:
        data = payload.get("body", {}).get("data")
        mime = payload.get("mimeType", "")
        if data and (mime == "text/plain" or not payload.get("parts")):
            try:
                return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="replace")
            except Exception:
                return ""
        for part in payload.get("parts", []) or []:
            if part.get("mimeType") == "text/plain":
                text = GmailEmailProvider._find_text(part)
                if text:
                    return text
        return ""

    @staticmethod
    def _find_attachments(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        result = []
        for part in payload.get("parts", []) or []:
            filename = part.get("filename")
            if filename:
                result.append({"filename": filename, "attachment_id": part.get("body", {}).get("attachmentId"), "mime_type": part.get("mimeType")})
            result.extend(GmailEmailProvider._find_attachments(part))
        return result

    def send(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        service = self._service_or_error()
        message = EmailMessage()
        message["To"] = draft["to"]
        message["Subject"] = draft.get("subject", "")
        if draft.get("from"):
            message["From"] = draft["from"]
        message["X-WorkPilot-Operation-Key"] = draft.get("operation_key", "")
        message.set_content(draft.get("body", ""))
        for attachment in draft.get("attachments", []):
            path = Path(attachment)
            data = path.read_bytes()
            import mimetypes

            mime_type, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
            message.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        try:
            response = service.users().messages().send(userId="me", body={"raw": encoded}).execute()
        except Exception as exc:
            text = str(exc).lower()
            if "401" in text or "unauthorized" in text or "invalid credentials" in text:
                raise EmailAuthenticationError("Gmail authorization failed. Reconnect the Gmail account.") from exc
            raise EmailProviderError("Gmail rejected the message or the network request failed.") from exc
        provider_message_id = response.get("id")
        return {
            "provider_message_id": provider_message_id,
            "email_id": provider_message_id,
            "status": "SENT" if provider_message_id else "PENDING_VERIFICATION",
            "accepted": bool(provider_message_id),
            "provider": self.name,
            "sent_at": current_iso_time(),
            "verification": {"status": "SENT" if provider_message_id else "PENDING_VERIFICATION", "provider_message_id": provider_message_id, "evidence": "Gmail API returned a message ID." if provider_message_id else "Gmail returned no message ID."},
        }

    def verify(self, provider_message_id: str) -> Dict[str, Any]:
        service = self._service_or_error()
        try:
            message = service.users().messages().get(userId="me", id=provider_message_id, format="metadata", metadataHeaders=["To", "Subject"]).execute()
        except Exception as exc:
            if "404" in str(exc):
                return {"status": "PENDING_VERIFICATION", "verified": False, "provider_message_id": provider_message_id, "evidence": "Gmail has not returned the submitted message yet."}
            raise EmailProviderError("Gmail verification could not be completed.") from exc
        return {"status": "SENT", "verified": bool(message.get("id")), "provider_message_id": message.get("id"), "evidence": "Gmail returned the submitted message from the provider."}


def build_email_provider(inbox_path: str, sent_path: str) -> BaseEmailProvider:
    provider_name = os.getenv("EMAIL_PROVIDER", "demo").strip().lower()
    if provider_name == "gmail":
        return GmailEmailProvider()
    if provider_name not in ("demo", "local"):
        logger.warning("Unknown EMAIL_PROVIDER '%s'; using local demo provider.", provider_name)
    return LocalDemoEmailProvider(inbox_path, sent_path)
