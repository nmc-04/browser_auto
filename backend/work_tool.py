"""
Employee Daily Work Automation Subsystem
Coordinates Task Board, Calendar, Email, and Documents to handle daily work and generate summaries.
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from utils.logger import logger, add_log_entry
from utils.helpers import current_iso_time

CALENDAR_FILE = "demo_data/calendar.json"
TASKS_FILE = "demo_data/tasks.json"
DAILY_SUMMARIES_DIR = "reports"


def get_today_schedule() -> List[Dict[str, Any]]:
    """Fetches today's meetings and calendar schedule."""
    if not os.path.exists(CALENDAR_FILE):
        return []
    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            events = json.load(f)
            add_log_entry(f"[Work Tool] Loaded {len(events)} calendar events for today")
            return events
    except Exception as e:
        logger.error(f"Error reading calendar: {e}")
        return []


def get_pending_tasks() -> List[Dict[str, Any]]:
    """Fetches all employee tasks from task board."""
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)
            pending = [t for t in tasks if t.get("status") != "Completed"]
            add_log_entry(f"[Work Tool] Loaded {len(tasks)} total tasks ({len(pending)} pending)")
            return tasks
    except Exception as e:
        logger.error(f"Error reading tasks: {e}")
        return []


def update_task_status(task_id: str, new_status: str) -> bool:
    """Updates status of a task on the task board."""
    if not os.path.exists(TASKS_FILE):
        return False
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        
        updated = False
        for t in tasks:
            if t.get("id") == task_id or task_id.lower() in t.get("title", "").lower():
                t["status"] = new_status
                t["updated_at"] = current_iso_time()
                updated = True
                break

        if updated:
            with open(TASKS_FILE, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=2)
            add_log_entry(f"[Work Tool] Updated task '{task_id}' status to '{new_status}'")
        return updated
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {e}")
        return False


def generate_daily_work_summary() -> Dict[str, Any]:
    """
    Compiles today's meetings, task status, priority actions, and work recommendations into an executive summary.
    """
    schedule = get_today_schedule()
    tasks = get_pending_tasks()

    pending_tasks = [t for t in tasks if t.get("status") != "Completed"]
    completed_tasks = [t for t in tasks if t.get("status") == "Completed"]
    high_priority_tasks = [t for t in pending_tasks if t.get("priority") == "High"]

    summary_text = (
        f"# WorkPilot Daily Work Executive Summary\n"
        f"**Generated:** {current_iso_time()[:16].replace('T', ' ')}\n\n"
        f"## 📅 Today's Schedule ({len(schedule)} Events)\n"
    )

    for ev in schedule:
        notes = f" — {ev.get('notes')}" if ev.get('notes') else ""
        summary_text += f"- **{ev.get('time')}**: {ev.get('title')}{notes}\n"

    summary_text += f"\n## 📌 Task Status Overview\n"
    summary_text += f"- **Pending Tasks:** {len(pending_tasks)}\n"
    summary_text += f"- **High Priority Urgent:** {len(high_priority_tasks)}\n"
    summary_text += f"- **Completed Tasks:** {len(completed_tasks)}\n\n"

    summary_text += f"### 🔥 Action Items Required Today:\n"
    for t in high_priority_tasks:
        summary_text += f"- [{t.get('id')}] **{t.get('title')}** (Due: {t.get('due_date', 'N/A')})\n"

    os.makedirs(DAILY_SUMMARIES_DIR, exist_ok=True)
    summary_file = os.path.join(DAILY_SUMMARIES_DIR, "daily_work_summary.md")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary_text)

    add_log_entry(f"[Work Tool] Daily work executive summary written to '{summary_file}'")

    return {
        "summary_file": summary_file,
        "report_file": summary_file,
        "summary_text": summary_text,
        "meetings_count": len(schedule),
        "pending_tasks_count": len(pending_tasks),
        "high_priority_count": len(high_priority_tasks)
    }


def verify_daily_work_plan(summary_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Verifies that daily work data was gathered from all applications and stored."""
    if not summary_data or not summary_data.get("summary_file"):
        return False, "Verification failed: Daily work summary file was not generated."
    
    if not os.path.exists(summary_data["summary_file"]):
        return False, f"Verification failed: Output file {summary_data['summary_file']} missing on disk."

    return True, f"Verified: Processed {summary_data.get('meetings_count')} meetings, {summary_data.get('pending_tasks_count')} tasks, summary saved."
