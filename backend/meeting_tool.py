"""
Meeting Automation Subsystem
Cross-application meeting assistant: pulls calendar event, related emails, project documents, and pending tasks to synthesize a meeting brief.
"""

import os
import json
from typing import Dict, Any, Optional, Tuple, List
from backend.email_tool import search_emails
from utils.logger import logger, add_log_entry

CALENDAR_FILE = "demo_data/calendar.json"
TASKS_FILE = "demo_data/tasks.json"
DOCS_DIR = "demo_data/documents"
BRIEF_DIR = "reports"


def find_meeting(query: str = "3 PM") -> Optional[Dict[str, Any]]:
    """Finds matching meeting in the calendar schedule by time, client, or title."""
    if not os.path.exists(CALENDAR_FILE):
        return None
    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            events = json.load(f)
            q = query.lower()
            for ev in events:
                time_str = ev.get("time", "").lower()
                title = ev.get("title", "").lower()
                client = ev.get("client", "").lower()
                if q in time_str or q in title or q in client:
                    add_log_entry(f"[Meeting Tool] Found matching meeting: '{ev.get('title')}' at {ev.get('time')}")
                    return ev
    except Exception as e:
        logger.error(f"Error finding meeting: {e}")
    return None


def gather_meeting_context(meeting: Dict[str, Any]) -> Dict[str, Any]:
    """
    Searches Emails, Project Documents, and Tasks for information connected to the meeting client.
    """
    client = meeting.get("client") or meeting.get("title", "")
    client_keyword = client.split()[0] if client else ""

    # 1. Emails
    related_emails = search_emails(client_keyword) if client_keyword else []

    # 2. Project Documents
    related_docs = []
    if os.path.exists(DOCS_DIR):
        for fname in os.listdir(DOCS_DIR):
            if client_keyword.lower() in fname.lower():
                full_path = os.path.join(DOCS_DIR, fname)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        related_docs.append({
                            "filename": fname,
                            "content": f.read().strip()
                        })
                except Exception:
                    pass

    # 3. Tasks
    related_tasks = []
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
                for t in tasks:
                    if client_keyword.lower() in t.get("title", "").lower() and t.get("status") != "Completed":
                        related_tasks.append(t)
        except Exception:
            pass

    add_log_entry(f"[Meeting Tool] Gathered context for '{client}': {len(related_emails)} email(s), {len(related_docs)} document(s), {len(related_tasks)} task(s)")

    return {
        "meeting": meeting,
        "emails": related_emails,
        "documents": related_docs,
        "tasks": related_tasks
    }


def generate_meeting_brief(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generates structured meeting brief markdown document."""
    meeting = context.get("meeting", {})
    emails = context.get("emails", [])
    docs = context.get("documents", [])
    tasks = context.get("tasks", [])

    time_val = meeting.get("time", "3:00 PM")
    title = meeting.get("title", "Client Meeting")
    client = meeting.get("client", "Client")
    person = meeting.get("person", "Client Stakeholders")
    project = meeting.get("project", "Enterprise Services")
    agenda = meeting.get("agenda", ["Project status review", "Contract discussion"])

    brief = (
        f"# 📋 Executive Meeting Brief\n"
        f"**Meeting:** {title}\n"
        f"**Time:** {time_val}\n"
        f"**Client Organization:** {client}\n"
        f"**Primary Attendee:** {person}\n"
        f"**Associated Project:** {project}\n\n"
        f"---\n\n"
        f"## 🎯 Agenda Items\n"
    )
    for itm in agenda:
        brief += f"- {itm}\n"

    brief += f"\n## 📧 Recent Client Communications\n"
    if emails:
        for em in emails:
            brief += f"### Subject: {em.get('subject')}\n"
            brief += f"- **From:** {em.get('from')} ({em.get('date')})\n"
            brief += f"- **Excerpt:** {em.get('body', '')[:200]}...\n\n"
    else:
        brief += "_No recent email threads found._\n\n"

    brief += f"## 📄 Supporting Project Documents & Terms\n"
    if docs:
        for d in docs:
            brief += f"### Document: `{d.get('filename')}`\n"
            brief += f"```text\n{d.get('content')}\n```\n\n"
    else:
        brief += "_No project documents attached._\n\n"

    brief += f"## 📌 Pending Action Items & Deliverables\n"
    if tasks:
        for t in tasks:
            brief += f"- [{t.get('id')}] **{t.get('title')}** (Due: {t.get('due_date')})\n"
    else:
        brief += "_All prior deliverables completed._\n\n"

    brief += (
        f"## 💡 Strategic Talking Points\n"
        f"1. Highlight 100% completion of AWS ECS deployment with 142ms benchmark.\n"
        f"2. Present Q4 retainer renewal contract terms (INR 3,60,000/quarter) for signature.\n"
        f"3. Confirm scheduling for staging sign-off by end of this week.\n"
    )

    os.makedirs(BRIEF_DIR, exist_ok=True)
    brief_file = os.path.join(BRIEF_DIR, "meeting_brief_3pm.md")
    with open(brief_file, "w", encoding="utf-8") as f:
        f.write(brief)

    add_log_entry(f"[Meeting Tool] Meeting brief generated and saved to '{brief_file}'")

    return {
        "brief_file": brief_file,
        "brief_content": brief,
        "meeting_time": time_val,
        "client": client,
        "email_count": len(emails),
        "doc_count": len(docs)
    }


def verify_meeting_brief(brief_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Verifies that meeting was identified and brief was successfully compiled."""
    if not brief_data or not brief_data.get("brief_file"):
        return False, "Verification failed: Meeting brief was not created."
    
    path = brief_data["brief_file"]
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False, f"Verification failed: Brief file '{path}' is missing or empty."

    return True, f"Verified: Meeting brief created for {brief_data.get('client')} ({brief_data.get('meeting_time')}) containing {brief_data.get('doc_count')} docs and {brief_data.get('email_count')} emails."
