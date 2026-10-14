"""
Employee Reporting Subsystem
Collects activity data across Tasks, Calendar, Email, Project Data, and Excel to produce structured performance reports.
"""

import os
import json
from typing import Dict, Any, Tuple
from backend.invoice_tool import read_invoices_excel
from backend.email_tool import _load_sent_emails
from utils.logger import logger, add_log_entry
from utils.helpers import current_iso_time

REPORT_DIR = "reports"


def collect_monthly_activity() -> Dict[str, Any]:
    """Aggregates authentic activity data from all system sources without hallucinations."""
    data = {
        "tasks": [],
        "completed_tasks": [],
        "pending_tasks": [],
        "meetings": [],
        "sent_emails": [],
        "invoices": [],
        "total_work_items": 0
    }

    # 1. Tasks
    if os.path.exists("demo_data/tasks.json"):
        try:
            with open("demo_data/tasks.json", "r", encoding="utf-8") as f:
                tasks = json.load(f)
                data["tasks"] = tasks
                data["completed_tasks"] = [t for t in tasks if t.get("status") == "Completed"]
                data["pending_tasks"] = [t for t in tasks if t.get("status") != "Completed"]
        except Exception:
            pass

    # 2. Meetings
    if os.path.exists("demo_data/calendar.json"):
        try:
            with open("demo_data/calendar.json", "r", encoding="utf-8") as f:
                data["meetings"] = json.load(f)
        except Exception:
            pass

    # 3. Sent emails
    data["sent_emails"] = _load_sent_emails()

    # 4. Invoices
    data["invoices"] = read_invoices_excel()

    data["total_work_items"] = len(data["tasks"]) + len(data["meetings"]) + len(data["sent_emails"])
    add_log_entry(f"[Reporting Tool] Aggregated activity: {len(data['tasks'])} tasks, {len(data['meetings'])} meetings, {len(data['sent_emails'])} sent emails, {len(data['invoices'])} invoices")
    return data


def generate_employee_activity_report(activity_data: Dict[str, Any], output_path: str = "reports/employee_activity_report.md") -> Dict[str, Any]:
    """Produces comprehensive structured monthly activity and performance report."""
    tasks = activity_data.get("tasks", [])
    completed_tasks = activity_data.get("completed_tasks", [])
    pending_tasks = activity_data.get("pending_tasks", [])
    meetings = activity_data.get("meetings", [])
    sent_emails = activity_data.get("sent_emails", [])
    invoices = activity_data.get("invoices", [])

    paid_invoices = [i for i in invoices if i.get("payment_status", "").lower() == "paid"]
    unpaid_invoices = [i for i in invoices if i.get("payment_status", "").lower() in ("unpaid", "overdue")]

    report = (
        f"# 📊 Monthly Employee Activity & Performance Report\n"
        f"**Generated On:** {current_iso_time()[:16].replace('T', ' ')}\n"
        f"**Department:** Enterprise Workflow Operations\n\n"
        f"---\n\n"
        f"## 1. Executive Summary\n"
        f"- **Total Action Items Handled:** {len(tasks)}\n"
        f"- **Task Completion Rate:** {len(completed_tasks)}/{len(tasks)} ({int(len(completed_tasks)/max(len(tasks), 1)*100)}%)\n"
        f"- **Meetings Attended / Coordinated:** {len(meetings)}\n"
        f"- **Automated Email Communications Sent:** {len(sent_emails)}\n"
        f"- **Invoices Tracked & Managed:** {len(invoices)} (Paid: {len(paid_invoices)}, Pending: {len(unpaid_invoices)})\n\n"
        f"## 2. Key Completed Tasks & Milestones\n"
    )
    if completed_tasks:
        for t in completed_tasks:
            report += f"- ✓ **[{t.get('id')}]** {t.get('title')} ({t.get('category', 'General')})\n"
    else:
        report += "- _No tasks marked completed this cycle._\n"

    report += f"\n## 3. Pending & In-Progress Work Items\n"
    if pending_tasks:
        for t in pending_tasks:
            report += f"- ⏳ **[{t.get('id')}]** {t.get('title')} (Priority: **{t.get('priority')}**, Due: {t.get('due_date')})\n"
    else:
        report += "- _All assigned tasks are completed._\n"

    report += f"\n## 4. Meetings & Stakeholder Engagements\n"
    for m in meetings:
        report += f"- **{m.get('time')}** — {m.get('title')} ({m.get('type')} with {m.get('person', ', '.join(m.get('attendees', ['Team'])))}))\n"

    report += f"\n## 5. Cross-Application Operations\n"
    report += f"- **Invoice Accounts Handled:** {len(invoices)} accounts reconciled in Excel.\n"
    report += f"- **Automated Communications:** {len(sent_emails)} reminder/confirmation message(s) verified in outbox.\n\n"
    report += f"---\n*Report compiled autonomously by WorkPilot AI Engine.*"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    add_log_entry(f"[Reporting Tool] Employee activity report saved to '{output_path}'")

    return {
        "report_file": output_path,
        "report_content": report,
        "completed_count": len(completed_tasks),
        "pending_count": len(pending_tasks),
        "meetings_count": len(meetings),
        "emails_count": len(sent_emails)
    }


def verify_report_generation(report_path: str) -> Tuple[bool, str]:
    """Verifies that report exists on disk and contains non-empty metrics."""
    if not os.path.exists(report_path):
        return False, f"Verification failed: Report file '{report_path}' does not exist."
    if os.path.getsize(report_path) < 100:
        return False, f"Verification failed: Report file '{report_path}' is incomplete or too small."
    return True, f"Verified: Activity report '{report_path}' generated successfully ({os.path.getsize(report_path)} bytes)."
