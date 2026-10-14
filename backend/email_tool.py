"""Provider-neutral email automation services.

This module preserves the original public helpers while adding a real Gmail
adapter, local fixture support for tests, safe attachment validation, message
deduplication, and evidence-based verification.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from backend.email_providers import (
    BaseEmailProvider,
    DemoEmailProvider,
    EmailNotConfiguredError,
    EmailProviderError,
    EmailPendingVerification,
    GmailProvider,
)
from utils.helpers import current_iso_time, generate_id
from utils.logger import add_log_entry

load_dotenv(override=True)

EMAIL_ADDRESS_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg"
}
_PROVIDER_OVERRIDE: Optional[BaseEmailProvider] = None


def set_email_provider(provider: Optional[BaseEmailProvider]) -> None:
    """Inject a provider for tests or an embedding application."""
    global _PROVIDER_OVERRIDE
    _PROVIDER_OVERRIDE = provider


def get_email_provider() -> BaseEmailProvider:
    if _PROVIDER_OVERRIDE is not None:
        return _PROVIDER_OVERRIDE
    provider_name = os.getenv("EMAIL_PROVIDER", "demo").strip().lower()
    if provider_name in {"gmail", "google"}:
        return GmailProvider()
    if provider_name in {"demo", "mock", "local"}:
        return DemoEmailProvider()
    raise EmailNotConfiguredError(
        f"Unsupported EMAIL_PROVIDER '{provider_name}'. Use 'gmail' for a real account or 'demo' for local fixtures."
    )


def email_connection_status() -> Dict[str, Any]:
    """Return safe connection metadata without exposing tokens or secrets."""
    try:
        return get_email_provider().connection_status()
    except Exception as exc:
        return {"provider": "unknown", "connected": False, "reason": str(exc)}


def connect_email_account() -> Dict[str, Any]:
    """Run Gmail OAuth when the configured provider supports it."""
    provider = get_email_provider()
    if not isinstance(provider, GmailProvider):
        return provider.connection_status()
    return provider.connect()


# Names used by the existing dashboard integration.
get_email_connection_status = email_connection_status
connect_gmail = connect_email_account


def validate_email_address(address: str) -> bool:
    return bool(address and EMAIL_ADDRESS_RE.fullmatch(address.strip()))


def build_provider_query(instruction: str) -> str:
    """Convert common natural-language filters into a Gmail-compatible query."""
    text = (instruction or "").strip()
    if not text:
        return ""
    if any(token in text.lower() for token in ("from:", "to:", "subject:", "after:", "before:", "is:", "has:", "newer_than:")):
        return text

    parts: List[str] = []
    sender = re.search(r"\bfrom\s+([\w.+-]+@[\w.-]+)", text, re.I)
    recipient = re.search(r"\bto\s+([\w.+-]+@[\w.-]+)", text, re.I)
    subject = re.search(r"\bsubject\s+[\"']?([^\"']+?)[\"']?(?:\s|$)", text, re.I)
    if sender:
        parts.append(f"from:{sender.group(1)}")
    if recipient:
        parts.append(f"to:{recipient.group(1)}")
    if subject:
        parts.append(f"subject:{subject.group(1).strip()}")
    if re.search(r"\bunread\b", text, re.I):
        parts.append("is:unread")
    if re.search(r"\b(today|today's)\b", text, re.I):
        parts.append("newer_than:1d")
    if re.search(r"\bwith attachments?\b|\battached\b", text, re.I):
        parts.append("has:attachment")

    cleaned = re.sub(
        r"\b(find|search|read|show|summarize|summarise|latest|email|emails|inbox|received|today|from|my|manager|and|them|about|the|please)\b",
        " ", text, flags=re.I
    )
    keywords = " ".join(token for token in re.findall(r"[\w@.-]+", cleaned) if token not in {".", ".."}).strip()
    if keywords:
        parts.append(keywords)
    return " ".join(parts)


def parse_email_search_intent(instruction: str) -> Dict[str, Any]:
    """Compatibility parser used by older workflow templates."""
    text = instruction or ""
    sender = re.search(r"\bfrom\s+([\w.+-]+@[\w.-]+)", text, re.I)
    recipient = re.search(r"\bto\s+([\w.+-]+@[\w.-]+)", text, re.I)
    subject = re.search(r"\bsubject\s+[\"']?([^\"']+?)[\"']?(?:\s|$)", text, re.I)
    status = "unread" if re.search(r"\bunread\b", text, re.I) else None
    return {
        "query": build_provider_query(text),
        "sender": sender.group(1) if sender else None,
        "recipient": recipient.group(1) if recipient else None,
        "subject": subject.group(1).strip() if subject else None,
        "status": status,
    }


def search_emails(
    query: str = "",
    limit: int = 10,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    subject: Optional[str] = None,
    status: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
) -> List[Dict[str, Any]]:
    provider = get_email_provider()
    provider_query = build_provider_query(query)
    filters = []
    if sender:
        filters.append(f"from:{sender}")
    if recipient:
        filters.append(f"to:{recipient}")
    if subject:
        filters.append(f"subject:{subject}")
    if status:
        filters.append(f"is:{status}")
    if date_after:
        filters.append(f"after:{date_after}")
    if date_before:
        filters.append(f"before:{date_before}")
    if keywords:
        filters.extend(str(item) for item in keywords if str(item).strip())
    if filters:
        provider_query = " ".join(filters)
    results = provider.search(provider_query, limit=limit)
    add_log_entry(f"[Email Tool] Searched {provider.name} for '{query}': Found {len(results)} match(es)")
    return results


def read_email(email_id: str) -> Optional[Dict[str, Any]]:
    return get_email_provider().read(email_id)


def extract_email_information(email: Dict[str, Any]) -> Dict[str, Any]:
    """Extract factual fields and possible action items without executing them."""
    body = str(email.get("body", ""))
    subject = str(email.get("subject", ""))
    combined = f"{subject}\n{body}"
    invoice_numbers = sorted(set(re.findall(r"\b(?:INV|INVOICE)[-\s#]?[A-Z0-9-]+\b", combined, re.I)))
    amounts = re.findall(r"(?:INR|₹|USD|\$|EUR|€)\s?[\d,]+(?:\.\d{1,2})?", combined, re.I)
    email_addresses = sorted(set(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", combined)))
    deadlines = re.findall(r"[^.\n]*(?:due|deadline|by|on)\s+[^.\n]+", combined, re.I)
    action_items = [
        line.strip(" -*•\t")
        for line in body.splitlines()
        if re.search(r"\b(please|need to|action|follow up|review|send|provide|confirm|ensure|deadline|due)\b", line, re.I)
    ]
    status_match = re.search(r"\b(unpaid|paid|overdue|pending|settled|payment received)\b", combined, re.I)
    return {
        "email_id": email.get("id") or email.get("message_id"),
        "from": email.get("from", ""),
        "to": email.get("to", ""),
        "subject": subject,
        "timestamp": email.get("date", ""),
        "invoice_references": invoice_numbers,
        "amounts": amounts,
        "email_addresses": email_addresses,
        "deadlines": deadlines,
        "payment_status": status_match.group(1).lower() if status_match else None,
        "action_items": action_items,
        "attachments": email.get("attachments", []),
    }


def extract_email_insights(email: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy name retained for older cross-application workflows."""
    return extract_email_information(email)


def validate_attachment_paths(attachments: Optional[List[str]], max_size_mb: Optional[float] = None) -> Dict[str, Any]:
    """Validate files before an email can be dispatched."""
    paths = [str(path) for path in (attachments or []) if path]
    max_bytes = int((max_size_mb or float(os.getenv("EMAIL_MAX_ATTACHMENT_MB", "25"))) * 1024 * 1024)
    valid: List[str] = []
    errors: List[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            errors.append(f"Attachment does not exist: {raw_path}")
            continue
        if path.suffix.lower() not in ALLOWED_ATTACHMENT_EXTENSIONS:
            errors.append(f"Unsupported attachment type: {path.name}")
            continue
        if path.stat().st_size > max_bytes:
            errors.append(f"Attachment exceeds {max_bytes // (1024 * 1024)} MB: {path.name}")
            continue
        valid.append(str(path))
    return {"valid": not errors, "attachments": valid, "errors": errors}


def validate_recipient(address: str) -> Tuple[bool, str]:
    """Return a safe validation result for a recipient address."""
    value = (address or "").strip()
    if validate_email_address(value):
        return True, value
    return False, "Recipient email address is invalid or missing."


def validate_attachments(attachments: Optional[List[str]]) -> Tuple[bool, List[str], Optional[str]]:
    result = validate_attachment_paths(attachments)
    return result["valid"], result["attachments"], "; ".join(result["errors"]) if result["errors"] else None


def _idempotency_key(to: str, subject: str, body: str, attachments: List[str], invoice_number: Optional[str]) -> str:
    material = "|".join([
        (to or "").strip().lower(), subject or "", body or "", invoice_number or "",
        ",".join(sorted(os.path.basename(item) for item in attachments)),
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def compose_email(
    to: str,
    subject: str,
    body: str,
    attachments: Optional[List[str]] = None,
    client_name: Optional[str] = None,
    invoice_number: Optional[str] = None,
    attachments_required: bool = False,
    tone: str = "professional",
) -> Dict[str, Any]:
    attachment_list = [str(item) for item in (attachments or []) if item]
    attachments_required = attachments_required or bool(invoice_number)
    recipient_ok, recipient_error = validate_recipient(to)
    attachment_check = validate_attachment_paths(attachment_list)
    errors = []
    if not recipient_ok:
        errors.append(recipient_error)
    errors.extend(attachment_check["errors"])
    if attachments_required and not attachment_check["attachments"]:
        errors.append("This message requires a validated attachment.")
    if not (subject or "").strip():
        errors.append("Email subject is required.")
    if not body:
        errors.append("Email body is required.")
    draft = {
        "draft_id": generate_id("draft"),
        "to": (to or "").strip(),
        "client_name": client_name or (to or "").strip(),
        "subject": (subject or "").strip(),
        "body": body or "",
        "attachments": attachment_check["attachments"],
        "attachments_required": attachments_required,
        "tone": tone,
        "invoice_number": invoice_number,
        "created_at": current_iso_time(),
        "status": "DRAFT" if not errors else "SKIPPED",
        "validation_errors": errors,
    }
    draft["idempotency_key"] = _idempotency_key(
        draft["to"], draft["subject"], draft["body"], attachment_list, invoice_number
    )
    add_log_entry(f"[Email Tool] Composed preview for '{draft['to']}' - Subject: '{draft['subject']}'")
    return draft


def send_email(draft: Dict[str, Any], simulate_network: bool = True) -> Dict[str, Any]:
    """Submit an approved draft through the configured provider."""
    if not draft or draft.get("status") != "DRAFT":
        return {**(draft or {}), "status": "SKIPPED", "skip_reason": "; ".join((draft or {}).get("validation_errors", [])) or "Draft did not pass validation."}
    to_addr = str(draft.get("to", "")).strip()
    if not validate_email_address(to_addr):
        return {**draft, "status": "SKIPPED", "skip_reason": f"Invalid recipient email address: {to_addr or '<missing>'}"}
    if not draft.get("subject"):
        return {**draft, "status": "SKIPPED", "skip_reason": "Cannot send email without a subject."}
    if not draft.get("body"):
        return {**draft, "status": "SKIPPED", "skip_reason": "Cannot send email without a body."}
    attachment_check = validate_attachment_paths(draft.get("attachments", []))
    if attachment_check["errors"]:
        return {**draft, "status": "SKIPPED", "skip_reason": "; ".join(attachment_check["errors"])}
    if draft.get("attachments_required") and not attachment_check["attachments"]:
        return {**draft, "status": "SKIPPED", "skip_reason": "This message requires a validated attachment."}
    provider = get_email_provider()
    try:
        result = provider.send(draft)
    except EmailPendingVerification as exc:
        return {**draft, "status": "PENDING_VERIFICATION", "error": str(exc), "failure_type": "PROVIDER_OR_NETWORK"}
    except (EmailProviderError, OSError) as exc:
        message = str(exc)
        status = "FAILED" if "authorization" in message.lower() or "credential" in message.lower() else "PENDING_VERIFICATION"
        return {**draft, "status": status, "error": message, "failure_type": "AUTHENTICATION" if status == "FAILED" else "PROVIDER_OR_NETWORK"}
    result.setdefault("provider", provider.name)
    result.setdefault("provider_message_id", result.get("email_id"))
    # Expose the domain-neutral status contract to the execution engine while
    # retaining simulated=True so the UI never presents demo mode as delivery.
    if result.get("status") == "SIMULATED":
        result["status"] = "SENT"
        result["simulated"] = True
    return result


def verify_email_sent(
    email_id: Optional[str] = None,
    recipient: Optional[str] = None,
    attachment: Optional[str] = None,
    subject: Optional[str] = None,
) -> Tuple[bool, str]:
    """Verify provider evidence; never claim delivery without evidence."""
    provider = get_email_provider()
    provider_id = email_id
    if not provider_id and recipient and isinstance(provider, DemoEmailProvider):
        records = provider._load(provider.sent_file)
        for item in reversed(records):
            if item.get("to", "").lower() == recipient.lower() and (not subject or item.get("subject") == subject):
                provider_id = item.get("email_id")
                break
    if not provider_id:
        return False, f"Verification pending: provider message ID is unavailable for '{recipient or 'message'}'."
    evidence = provider.verify(provider_id, {"recipient": recipient, "subject": subject})
    if not evidence.get("verified"):
        return False, f"Pending verification for provider message {provider_id}: {evidence.get('verification_status', 'unknown')}"
    if attachment:
        expected_name = os.path.basename(attachment)
        attached = evidence.get("evidence", {}).get("attachments", [])
        if attached and expected_name not in [os.path.basename(str(path)) for path in attached]:
            return False, f"Verification failed: attachment '{expected_name}' was not evidenced by the provider."
    status = evidence.get("status", "SENT")
    if status == "SIMULATED":
        return True, f"Simulated local submission verified for {provider_id}; no external delivery occurred."
    if status == "SKIPPED":
        return True, f"Duplicate prevented for provider message {provider_id}; no second message was sent."
    return True, f"Provider accepted message {provider_id}. Submission verified; delivery is not claimed."


def get_sent_emails() -> List[Dict[str, Any]]:
    provider = get_email_provider()
    if isinstance(provider, DemoEmailProvider):
        return provider._load(provider.sent_file)
    return []


def _load_sent_emails() -> List[Dict[str, Any]]:
    """Compatibility helper used by reporting_tool and legacy workflows."""
    return get_sent_emails()


def get_email_connection_status() -> Dict[str, Any]:
    return email_connection_status()


def connect_gmail() -> Dict[str, Any]:
    return connect_email_account()

