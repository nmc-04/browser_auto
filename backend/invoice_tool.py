"""
Invoice Automation Subsystem
Cross-application processor for Excel invoice records, invoice documents, reminder generation, and status updates.
"""

import os
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from openpyxl import load_workbook
from utils.logger import logger, add_log_entry

DEFAULT_EXCEL_PATH = "demo_data/invoices.xlsx"
DEFAULT_CSV_PATH = "demo_data/invoices.csv"
INVOICE_DOCS_DIR = "demo_data/invoices"


def read_invoices_excel(file_path: str = DEFAULT_EXCEL_PATH) -> List[Dict[str, Any]]:
    """
    Reads invoice records from Excel workbook.
    Falls back to CSV if xlsx is inaccessible.
    """
    invoices = []
    if os.path.exists(file_path):
        try:
            wb = load_workbook(file_path, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
                for r in rows[1:]:
                    if not any(r):
                        continue
                    item = dict(zip(headers, r))
                    invoices.append({
                        "client_name": str(item.get("Client Name", "")).strip(),
                        "invoice_number": str(item.get("Invoice Number", "")).strip(),
                        "amount": float(item.get("Amount", 0) or 0),
                        "invoice_date": str(item.get("Invoice Date", "")).strip(),
                        "due_date": str(item.get("Due Date", "")).strip(),
                        "payment_status": str(item.get("Payment Status", "")).strip(),
                        "client_email": str(item.get("Client Email", "")).strip()
                    })
            add_log_entry(f"[Invoice Tool] Loaded {len(invoices)} invoices from '{file_path}'")
            return invoices
        except Exception as e:
            logger.warning(f"Failed to read xlsx {file_path}: {e}. Trying CSV fallback...")

    # Fallback to CSV
    if os.path.exists(DEFAULT_CSV_PATH):
        with open(DEFAULT_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for item in reader:
                invoices.append({
                    "client_name": item.get("Client Name", "").strip(),
                    "invoice_number": item.get("Invoice Number", "").strip(),
                    "amount": float(item.get("Amount", 0) or 0),
                    "invoice_date": item.get("Invoice Date", "").strip(),
                    "due_date": item.get("Due Date", "").strip(),
                    "payment_status": item.get("Payment Status", "").strip(),
                    "client_email": item.get("Client Email", "").strip()
                })
        add_log_entry(f"[Invoice Tool] Loaded {len(invoices)} invoices from CSV fallback")
    return invoices


def reset_invoice_demo_data(file_path: str = DEFAULT_EXCEL_PATH) -> None:
    """Restores initial demonstration invoices with unpaid and overdue status."""
    raw_data = [
        ("Client Name", "Invoice Number", "Amount", "Invoice Date", "Due Date", "Payment Status", "Client Email"),
        ("Apex Solutions", "INV-2024-001", 45000, "2024-08-01", "2024-08-31", "Overdue", "billing@apexsolutions.com"),
        ("Nexus Tech", "INV-2024-002", 18500, "2024-08-15", "2024-09-15", "Paid", "accounts@nexustech.io"),
        ("Quantum Corp", "INV-2024-003", 32000, "2024-09-01", "2024-09-25", "Overdue", "finance@quantumcorp.com"),
        ("Vertex Media", "INV-2024-004", 12750, "2024-08-10", "2024-09-10", "Unpaid", "payables@vertexmedia.org"),
        ("Horizon Labs", "INV-2024-005", 68000, "2024-09-05", "2024-09-28", "Overdue", "contact@horizonlabs.net")
    ]
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Invoices"
        for r in raw_data:
            ws.append(r)
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        wb.save(file_path)
    except Exception as e:
        logger.warning(f"Failed to reset demo xlsx: {e}")

    try:
        with open(DEFAULT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(raw_data)
    except Exception:
        pass
    add_log_entry("[Invoice Tool] Demo invoices restored to initial Unpaid/Overdue state for demonstration.")


def filter_invoices(status: Optional[str] = None, file_path: str = DEFAULT_EXCEL_PATH) -> List[Dict[str, Any]]:
    """
    Returns invoices matching a status filter (e.g. 'Unpaid', 'Overdue', 'Paid').
    If status is 'unpaid_or_overdue', returns all non-paid invoices.
    Auto-replenishes demonstration data if all demo invoices have previously been processed.
    """
    all_inv = read_invoices_excel(file_path)
    if not status:
        return all_inv

    target = status.lower()
    if target in ("unpaid_or_overdue", "unpaid", "pending"):
        matched = [i for i in all_inv if i.get("payment_status", "").lower() in ("unpaid", "overdue", "past due")]
        # Auto-replenish demonstration data if a previous run marked them all as 'Reminder Sent'
        if not matched and any(i.get("payment_status", "") == "Reminder Sent" for i in all_inv):
            reset_invoice_demo_data(file_path)
            all_inv = read_invoices_excel(file_path)
            matched = [i for i in all_inv if i.get("payment_status", "").lower() in ("unpaid", "overdue", "past due")]
    else:
        matched = [i for i in all_inv if i.get("payment_status", "").lower() == target]

    add_log_entry(f"[Invoice Tool] Filtered invoices by status '{status}': Found {len(matched)}")
    return matched


def find_invoice_documents(invoice_number: str, client_name: Optional[str] = None, search_dir: str = INVOICE_DOCS_DIR) -> List[str]:
    """Return all plausible invoice documents for safe ambiguity handling."""
    if not invoice_number or not os.path.isdir(search_dir):
        return []
    number = str(invoice_number).strip().lower()
    client_tokens = [token for token in (client_name or "").lower().split() if len(token) > 2]
    candidates: List[str] = []
    for path in Path(search_dir).iterdir():
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".xlsx", ".xls", ".csv", ".doc", ".docx", ".txt"}:
            continue
        name = path.name.lower()
        if number in name:
            candidates.append(str(path))
            continue
        # A client-name match is only useful when the invoice number is also
        # present in the document name or content; do not guess from a client
        # name alone.
        if client_tokens and all(token in name for token in client_tokens) and number in name:
            candidates.append(str(path))
    return sorted(set(candidates))


def find_invoice_document(invoice_number: str, client_name: Optional[str] = None) -> Optional[str]:
    """Return one exact invoice document, or None when missing/ambiguous."""
    matches = find_invoice_documents(invoice_number, client_name=client_name)
    return matches[0] if len(matches) == 1 else None


def extract_invoice_file(file_path: str) -> Dict[str, Any]:
    """Extracts text metadata from an invoice document file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Invoice document not found: {file_path}")

    data = {
        "file_path": file_path,
        "invoice_number": "",
        "client_name": "",
        "amount": 0.0,
        "payment_status": ""
    }
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str.startswith("Invoice Number:"):
                data["invoice_number"] = line_str.split(":", 1)[1].strip()
            elif line_str.startswith("Client:"):
                data["client_name"] = line_str.split(":", 1)[1].strip()
            elif line_str.startswith("Payment Status:"):
                data["payment_status"] = line_str.split(":", 1)[1].strip()
            elif "Total Amount Payable:" in line_str or "Amount Due:" in line_str:
                parts = line_str.split("INR")
                if len(parts) > 1:
                    try:
                        data["amount"] = float(parts[1].strip().replace(",", ""))
                    except ValueError:
                        pass
    return data


def prepare_invoice_reminders(unpaid_invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generates reminder email drafts for each unpaid or overdue invoice,
    locating and attaching the corresponding invoice document.
    """
    reminders = []
    for inv in unpaid_invoices:
        inv_num = inv.get("invoice_number")
        client = inv.get("client_name")
        email = str(inv.get("client_email") or "").strip()
        amount = inv.get("amount", 0)
        due_date = inv.get("due_date", "Immediate")
        status = inv.get("payment_status", "Unpaid")

        doc_matches = find_invoice_documents(inv_num, client_name=client)
        doc_path = doc_matches[0] if len(doc_matches) == 1 else None

        subject = f"Urgent: Payment Reminder for Invoice {inv_num} ({client})"
        body = (
            f"Dear {client} Accounts Team,\n\n"
            f"This is an automated reminder regarding outstanding invoice {inv_num}.\n\n"
            f"• Invoice Number: {inv_num}\n"
            f"• Amount Due: INR {amount:,.2f}\n"
            f"• Due Date: {due_date}\n"
            f"• Current Status: {status.upper()}\n\n"
            f"Please find the invoice statement attached. Kindly process this payment at your earliest convenience.\n\n"
            f"Best regards,\n"
            f"Finance & Operations Team\n"
            f"WorkPilot Enterprise Automation"
        )

        reminders.append({
            "to": email,
            "client_name": client,
            "invoice_number": inv_num,
            "amount": amount,
            "subject": subject,
            "body": body,
            "attachment": doc_path,
            "attachments": [doc_path] if doc_path else [],
            "attachments_required": True,
            "status": "PREPARED" if email and doc_path else "SKIPPED",
            "document_found": doc_path is not None,
            "validation_errors": (["Missing client email address."] if not email else []) + (["Missing or ambiguous invoice document."] if not doc_path else []),
            "attachment_candidates": doc_matches
        })

    add_log_entry(f"[Invoice Tool] Prepared {len(reminders)} reminder email draft(s)")
    return reminders


def update_invoice_status(invoice_number: str, new_status: str, file_path: str = DEFAULT_EXCEL_PATH) -> bool:
    """Updates the Payment Status column for a specific invoice in Excel and CSV."""
    updated = False
    if os.path.exists(file_path):
        try:
            wb = load_workbook(file_path)
            ws = wb.active
            for row in ws.iter_rows(min_row=2):
                if row[1].value and str(row[1].value).strip() == invoice_number:
                    row[5].value = new_status
                    updated = True
                    break
            if updated:
                wb.save(file_path)
                add_log_entry(f"[Invoice Tool] Updated Excel status for '{invoice_number}' to '{new_status}'")
        except Exception as e:
            logger.warning(f"Could not update Excel {file_path} (file may be open in Excel): {e}. Falling back to CSV.")

    # Also update CSV
    if os.path.exists(DEFAULT_CSV_PATH):
        try:
            rows = []
            with open(DEFAULT_CSV_PATH, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows.append(headers)
                for r in reader:
                    if len(r) > 5 and r[1].strip() == invoice_number:
                        r[5] = new_status
                        updated = True
                    rows.append(r)
            with open(DEFAULT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            add_log_entry(f"[Invoice Tool] Updated CSV status for '{invoice_number}' to '{new_status}'")
        except Exception as e:
            logger.error(f"Failed to update CSV {DEFAULT_CSV_PATH}: {e}")

    return updated


def verify_invoice_status(invoice_number: str, expected_status: str, file_path: str = DEFAULT_EXCEL_PATH) -> Tuple[bool, str]:
    """
    Verifies invoice status by reloading and re-reading the record from storage (Excel or CSV fallback).
    """
    all_invoices = read_invoices_excel(file_path)
    for inv in all_invoices:
        if inv.get("invoice_number") == invoice_number:
            actual = inv.get("payment_status")
            if actual.lower() == expected_status.lower():
                return True, f"Verified: Invoice {invoice_number} status is correctly recorded as '{actual}'."

    # If Excel reading failed or had stale locked data, inspect CSV fallback directly
    if os.path.exists(DEFAULT_CSV_PATH):
        try:
            with open(DEFAULT_CSV_PATH, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for item in reader:
                    if item.get("Invoice Number", "").strip() == invoice_number:
                        actual = item.get("Payment Status", "").strip()
                        if actual.lower() == expected_status.lower():
                            return True, f"Verified: Invoice {invoice_number} status is correctly recorded as '{actual}' (via CSV)."
                        else:
                            return False, f"Verification failed: Invoice {invoice_number} status is '{actual}', expected '{expected_status}'."
        except Exception as e:
            logger.warning(f"Error checking CSV fallback during verification: {e}")

    return False, f"Verification failed: Invoice {invoice_number} not found in database."
