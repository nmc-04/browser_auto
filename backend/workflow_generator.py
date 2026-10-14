"""
Workflow Generator Module
Bridges natural language prompts and Pydantic Workflow models via Ollama and Integrated Portal Planners.
All major employee workflows operate through the unified Employee Work Portal (employee_portal/index.html).
"""

from typing import Optional, List, Dict, Any
from backend.ollama_service import query_ollama, OllamaUnavailableError, OllamaParseError
from workflows.schemas import Workflow, WorkflowStep
from workflows.actions import (
    ACTION_OPEN_URL,
    ACTION_TYPE,
    ACTION_CLICK,
    ACTION_SEARCH,
    ACTION_SELECT,
    ACTION_READ_EXCEL,
    ACTION_FIND_UNPAID_INVOICES,
    ACTION_EXTRACT_INVOICE,
    ACTION_GENERATE_REMINDER,
    ACTION_SEND_EMAIL,
    ACTION_SEARCH_EMAIL,
    ACTION_READ_EMAIL,
    ACTION_EXTRACT_EMAIL_INFO,
    ACTION_COMPOSE_EMAIL,
    ACTION_ATTACH_FILE,
    ACTION_RECORD_RESULT,
    ACTION_UPDATE_EXCEL,
    ACTION_SEARCH_PRODUCT,
    ACTION_ADD_TO_CART,
    ACTION_REVIEW_ORDER,
    ACTION_DOWNLOAD_INVOICE,
    ACTION_CHECK_CALENDAR,
    ACTION_CHECK_TASKS,
    ACTION_UPDATE_TASK,
    ACTION_GENERATE_BRIEF,
    ACTION_GENERATE_REPORT,
    ACTION_VERIFY,
    ACTION_EXTRACT_PRODUCT_DATA,
    ACTION_VALIDATE_PRODUCTS,
    ACTION_GENERATE_EXCEL,
)
from backend.product_search_tool import parse_product_search_intent
from utils.helpers import generate_id, current_iso_time
from utils.logger import logger, add_log_entry

PORTAL_URL = "employee_portal/index.html"


def get_email_workflow(prompt: str, user_id: Optional[str] = None) -> Optional[Workflow]:
    """Build provider-neutral workflows for email and invoice instructions."""
    p = prompt.lower().strip()
    email_terms = ["email", "inbox", "mail", "gmail", "message", "invoice"]
    if not any(term in p for term in email_terms):
        return None

    # Exclude canonical Demo 2 invoice processing prompts so they are handled by the portal enterprise template
    if any(k in p for k in ["process all unpaid invoices", "process invoice", "process today's invoices", "process unpaid invoices", "invoice reminder"]):
        return None

    read_search_intent = any(term in p for term in ["find email", "find emails", "search email", "search emails", "search my inbox", "read the latest", "summarize", "summarise", "action item"])
    invoice_intent = any(term in p for term in ["invoice", "unpaid", "overdue invoice", "payment reminder"]) and not read_search_intent
    send_requested = any(term in p for term in ["send", "dispatch", "mail them", "email them"])

    if invoice_intent:
        spreadsheet = "demo_data/invoices.xlsx"
        for token in prompt.split():
            clean = token.strip("\"'.,()")
            if clean.lower().endswith((".xlsx", ".xls", ".csv")):
                spreadsheet = clean
                break
        steps = [
            WorkflowStep(step=1, action=ACTION_READ_EXCEL, value=spreadsheet, app="Excel", description=f"Read invoice records from {spreadsheet}"),
            WorkflowStep(step=2, action=ACTION_FIND_UNPAID_INVOICES, app="Excel", description="Identify unpaid and overdue invoice records"),
            WorkflowStep(step=3, action=ACTION_EXTRACT_INVOICE, app="Invoices", description="Match each invoice to its document and validate the client details"),
            WorkflowStep(step=4, action=ACTION_COMPOSE_EMAIL, app="Email", description="Compose a personalized reminder preview for each validated invoice"),
            WorkflowStep(step=5, action=ACTION_ATTACH_FILE, app="Email", description="Validate the correct invoice attachment for every recipient"),
        ]
        next_step = 6
        if send_requested:
            steps.append(WorkflowStep(
                step=next_step,
                action=ACTION_SEND_EMAIL,
                app="Email",
                requires_confirmation=True,
                description="Submit approved reminder emails through the authorized email provider",
            ))
            next_step += 1
        steps.extend([
            WorkflowStep(step=next_step, action=ACTION_VERIFY, app="Verification", description="Verify provider submission evidence and per-recipient outcomes"),
            WorkflowStep(step=next_step + 1, action=ACTION_RECORD_RESULT, app="Workflow History", description="Record the complete email automation result"),
        ])
        return Workflow(
            workflow_id=generate_id("wf"),
            workflow_name="Invoice Email Automation",
            prompt=prompt,
            applications=["Excel", "Invoice System", "Email", "Workflow History"],
            steps=steps,
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time(),
        )

    if read_search_intent:
        return Workflow(
            workflow_id=generate_id("wf"),
            workflow_name="Email Search and Understanding",
            prompt=prompt,
            applications=["Email", "Workflow History"],
            steps=[
                WorkflowStep(step=1, action=ACTION_SEARCH_EMAIL, value=prompt, app="Email", description="Search the authorized email account using the natural-language instruction"),
                WorkflowStep(step=2, action=ACTION_READ_EMAIL, app="Email", description="Read each matching message and its attachment metadata"),
                WorkflowStep(step=3, action=ACTION_EXTRACT_EMAIL_INFO, app="Email", description="Extract factual details, deadlines, payment references, and action items"),
                WorkflowStep(step=4, action=ACTION_VERIFY, app="Verification", description="Verify the messages processed and the extracted evidence"),
                WorkflowStep(step=5, action=ACTION_RECORD_RESULT, app="Workflow History", description="Record the search and analysis result"),
            ],
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time(),
        )

    if any(term in p for term in ["send email", "reply", "respond"]):
        return Workflow(
            workflow_id=generate_id("wf"),
            workflow_name="Approved Email Dispatch",
            prompt=prompt,
            applications=["Email", "Workflow History"],
            steps=[
                WorkflowStep(step=1, action=ACTION_COMPOSE_EMAIL, value=prompt, app="Email", description="Compose a reviewable email preview from the instruction"),
                WorkflowStep(step=2, action=ACTION_ATTACH_FILE, app="Email", description="Validate any requested attachments"),
                WorkflowStep(step=3, action=ACTION_SEND_EMAIL, app="Email", requires_confirmation=True, description="Submit the approved message through the authorized email provider"),
                WorkflowStep(step=4, action=ACTION_VERIFY, app="Verification", description="Verify provider submission evidence"),
                WorkflowStep(step=5, action=ACTION_RECORD_RESULT, app="Workflow History", description="Record the dispatch result"),
            ],
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time(),
        )
    return None


def get_template_workflow(prompt: str, user_id: Optional[str] = None) -> Optional[Workflow]:
    """Provides portal-driven workflow decomposition for the five major enterprise workflows."""
    p = prompt.lower().strip()

    # Natural-language inbox work is routed through the provider API.  The
    # message contents are treated as data and never as executable instructions.
    if any(k in p for k in ["find emails", "search my inbox", "search emails", "read the latest email", "summarize emails", "email action items", "emails from my"]):
        return Workflow(
            workflow_id=generate_id("wf"),
            workflow_name="Email Search and Analysis",
            prompt=prompt,
            applications=["Email", "Verification"],
            steps=[
                WorkflowStep(step=1, action=ACTION_SEARCH_EMAIL, value=prompt, app="Email", description="Search the authorized mailbox using the natural-language criteria"),
                WorkflowStep(step=2, action=ACTION_READ_EMAIL, app="Email", description="Read matching messages and their attachment metadata"),
                WorkflowStep(step=3, action=ACTION_VERIFY, app="Verification", description="Record the messages processed and extracted action items"),
            ],
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time()
        )

    # 1. Invoice Processing & Client Reminders (Employee Work Portal)
    if any(k in p for k in ["unpaid invoice", "process invoice", "invoice reminder", "overdue invoice", "process today's invoices", "process all unpaid invoices"]):
        return Workflow(
            workflow_id=generate_id("wf"),
            workflow_name="Invoice Processing & Client Reminders",
            prompt=prompt,
            applications=["Excel", "Invoice System", "Email", "Verification"],
            steps=[
                WorkflowStep(step=1, action=ACTION_READ_EXCEL, value="demo_data/invoices.xlsx", app="Excel", description="Read invoice records from the configured Excel workbook"),
                WorkflowStep(step=2, action=ACTION_FIND_UNPAID_INVOICES, app="Invoice System", description="Identify unpaid and overdue invoices"),
                WorkflowStep(step=3, action=ACTION_EXTRACT_INVOICE, app="Invoice System", description="Locate and validate the matching invoice documents"),
                WorkflowStep(step=4, action=ACTION_GENERATE_REMINDER, app="Email", description="Compose personalized reminder previews with validated attachments"),
                WorkflowStep(step=5, action=ACTION_SEND_EMAIL, app="Email", requires_confirmation=True, description="Send approved reminders through the authorized email provider"),
                WorkflowStep(step=6, action=ACTION_UPDATE_EXCEL, value="Reminder Sent", app="Excel", description="Record successful submissions in invoice records"),
                WorkflowStep(step=7, action=ACTION_VERIFY, app="Verification", description="Verify provider message evidence and recorded invoice results")
            ],
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time()
        )

    # 2. Product Procurement / Office Supplies (Employee Work Portal)
    if any(k in p for k in ["office supply", "order the office supplies", "procurement", "order the required office supplies", "supply order", "products.xlsx", "product list"]):
        return Workflow(
            workflow_id=generate_id("wf"),
            workflow_name="Office Supplies Procurement",
            prompt=prompt,
            applications=["Employee Work Portal", "Procurement", "Selenium Browser"],
            steps=[
                WorkflowStep(step=1, action=ACTION_OPEN_URL, url=PORTAL_URL, app="Portal", description="Open Employee Work Portal in Chrome"),
                WorkflowStep(step=2, action=ACTION_CLICK, target="#nav-procurement", app="Procurement", description="Navigate to Office Supplies Procurement module"),
                WorkflowStep(step=3, action=ACTION_TYPE, target="#proc-search-input", value="A4 Copy Paper", app="Procurement", description="Search catalog for 'A4 Copy Paper'"),
                WorkflowStep(step=4, action=ACTION_CLICK, target="#proc-search-btn", app="Procurement", description="Submit product catalog search"),
                WorkflowStep(step=5, action=ACTION_CLICK, target="#proc-add-1", app="Procurement", description="Add A4 Copy Paper Ream to shopping cart"),
                WorkflowStep(step=6, action=ACTION_TYPE, target="#proc-search-input", value="Ballpoint Pens", app="Procurement", description="Search catalog for 'Ballpoint Pens'"),
                WorkflowStep(step=7, action=ACTION_CLICK, target="#proc-search-btn", app="Procurement", description="Submit product catalog search"),
                WorkflowStep(step=8, action=ACTION_CLICK, target="#proc-add-2", app="Procurement", description="Add Ballpoint Pens pack to shopping cart"),
                WorkflowStep(step=9, action=ACTION_CLICK, target="#proc-checkout-btn", app="Procurement", requires_confirmation=True, description="Review cart totals & stage order (Awaiting human confirmation)"),
                WorkflowStep(step=10, action=ACTION_CLICK, target="#proc-download-invoice-btn", app="Procurement", description="Download order procurement invoice"),
                WorkflowStep(step=11, action=ACTION_VERIFY, app="Verification", description="Verify items in cart and order invoice generation")
            ],
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time()
        )

    # 3. Employee Daily Work (Employee Work Portal)
    if any(k in p for k in ["handle my work", "work for today", "daily work", "today's work", "my tasks today"]):
        return Workflow(
            workflow_id=generate_id("wf"),
            workflow_name="Employee Daily Work Automation",
            prompt=prompt,
            applications=["Employee Work Portal", "Dashboard", "Tasks", "Calendar", "Reports"],
            steps=[
                WorkflowStep(step=1, action=ACTION_OPEN_URL, url=PORTAL_URL, app="Portal", description="Open Employee Work Portal in Chrome"),
                WorkflowStep(step=2, action=ACTION_CLICK, target="#nav-dashboard", app="Dashboard", description="Inspect Executive Dashboard daily metrics"),
                WorkflowStep(step=3, action=ACTION_CLICK, target="#nav-tasks", app="Tasks", description="Navigate to Task Board"),
                WorkflowStep(step=4, action=ACTION_CLICK, target="#task-filter-pending", app="Tasks", description="Filter pending priority tasks"),
                WorkflowStep(step=5, action=ACTION_CLICK, target="#task-btn-TASK-101", app="Tasks", description="Advance priority deliverable task (TASK-101)"),
                WorkflowStep(step=6, action=ACTION_CLICK, target="#task-btn-TASK-102", app="Tasks", description="Mark completed administrative task (TASK-102)"),
                WorkflowStep(step=7, action=ACTION_CLICK, target="#nav-calendar", app="Calendar", description="Inspect today's scheduled meetings"),
                WorkflowStep(step=8, action=ACTION_CLICK, target="#nav-reports", app="Reports", description="Open Reports module to view Daily Summary"),
                WorkflowStep(step=9, action=ACTION_CLICK, target="#btn-view-daily-summary", app="Reports", description="Inspect compiled Executive Daily Work Summary"),
                WorkflowStep(step=10, action=ACTION_VERIFY, app="Verification", description="Verify task board updates and executive summary document")
            ],
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time()
        )

    # 4. Meeting Assistant & Brief Compilation (Employee Work Portal)
    if any(k in p for k in ["client meeting", "prepare for my 3 pm", "meeting brief", "3 pm meeting", "prepare for meeting"]):
        return Workflow(
            workflow_id=generate_id("wf"),
            workflow_name="Client Meeting Preparation Assistant",
            prompt=prompt,
            applications=["Employee Work Portal", "Calendar", "Email", "Documents", "Reports"],
            steps=[
                WorkflowStep(step=1, action=ACTION_OPEN_URL, url=PORTAL_URL, app="Portal", description="Open Employee Work Portal in Chrome"),
                WorkflowStep(step=2, action=ACTION_CLICK, target="#nav-calendar", app="Calendar", description="Navigate to Calendar module"),
                WorkflowStep(step=3, action=ACTION_CLICK, target="#meeting-row-0300pm", app="Calendar", description="Inspect 3:00 PM Acrom Systems client meeting"),
                WorkflowStep(step=4, action=ACTION_CLICK, target="#nav-email", app="Email", description="Open Email to inspect Sarah Jenkins agenda thread"),
                WorkflowStep(step=5, action=ACTION_CLICK, target="#nav-documents", app="Documents", description="Access Acrom project deliverables & contract renewal terms"),
                WorkflowStep(step=6, action=ACTION_CLICK, target="#nav-reports", app="Reports", description="Navigate to Reports module"),
                WorkflowStep(step=7, action=ACTION_CLICK, target="#btn-view-meeting-brief", app="Reports", description="View compiled Executive Meeting Brief"),
                WorkflowStep(step=8, action=ACTION_VERIFY, app="Verification", description="Verify executive meeting brief saved on disk")
            ],
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time()
        )

    # 5. Monthly Employee Activity Report (Employee Work Portal)
    if any(k in p for k in ["activity report", "performance report", "monthly report", "employee report", "month's employee activity"]):
        return Workflow(
            workflow_id=generate_id("wf"),
            workflow_name="Monthly Employee Activity & Performance Report",
            prompt=prompt,
            applications=["Employee Work Portal", "Tasks", "Calendar", "Reports", "Email"],
            steps=[
                WorkflowStep(step=1, action=ACTION_OPEN_URL, url=PORTAL_URL, app="Portal", description="Open Employee Work Portal in Chrome"),
                WorkflowStep(step=2, action=ACTION_CLICK, target="#nav-tasks", app="Tasks", description="Inspect Task Board completion metrics"),
                WorkflowStep(step=3, action=ACTION_CLICK, target="#nav-calendar", app="Calendar", description="Review calendar meeting history"),
                WorkflowStep(step=4, action=ACTION_CLICK, target="#nav-invoices", app="Invoices", description="Review reconciled client invoices"),
                WorkflowStep(step=5, action=ACTION_CLICK, target="#nav-reports", app="Reports", description="Navigate to Reports module"),
                WorkflowStep(step=6, action=ACTION_CLICK, target="#btn-view-activity-report", app="Reports", description="View compiled Monthly Employee Activity Report"),
                WorkflowStep(step=7, action=ACTION_CLICK, target="#nav-email", app="Email", description="Open Email module to dispatch notification to management"),
                WorkflowStep(step=8, action=ACTION_VERIFY, app="Verification", description="Verify report document generated and email dispatched")
            ],
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time()
        )

    return None


def generate_workflow(prompt: str, user_id: Optional[str] = None) -> Workflow:
    """
    Calls Ollama or template planner to produce structured portal-driven or product search workflow.
    """
    # 1. Match email/invoice requests before the older browser portal templates.
    email_wf = get_email_workflow(prompt, user_id=user_id)
    if email_wf:
        add_log_entry(f"Generated email workflow '{email_wf.workflow_name}' ({len(email_wf.steps)} steps).")
        return email_wf

    # 2. Match against integrated portal templates first
    template_wf = get_template_workflow(prompt, user_id=user_id)
    if template_wf:
        add_log_entry(f"Generated portal workflow '{template_wf.workflow_name}' ({len(template_wf.steps)} steps).")
        return template_wf

    # 3. Check for Product Search & Automated Excel Reporting Intent
    intent = parse_product_search_intent(prompt)
    if intent:
        category = intent["category"]
        max_p = intent.get("maximum_price")
        task_type = intent.get("task_type", "product_search")
        query = intent.get("query", category)

        wf_title = f"Price Comparison: {category.title()}" if task_type == "product_comparison" else f"Product Search: {category.title()}"
        if max_p:
            wf_title += f" (Under ₹{max_p:,.0f})"

        steps = [
            WorkflowStep(
                step=1,
                action=ACTION_OPEN_URL,
                url="https://www.amazon.in",
                app="Browser",
                description=f"Open product search website in Chrome"
            ),
            WorkflowStep(
                step=2,
                action=ACTION_SEARCH_PRODUCT,
                target="search_box",
                value=query,
                app="Browser",
                description=f"Search relevant websites for '{query}'"
            ),
            WorkflowStep(
                step=3,
                action=ACTION_EXTRACT_PRODUCT_DATA,
                value=category,
                app="Browser",
                description=f"Extract authentic product data (Name, Website, Price, Link)"
            ),
            WorkflowStep(
                step=4,
                action=ACTION_VALIDATE_PRODUCTS,
                value=str(max_p or ""),
                app="Verification",
                description=f"Validate collected products, apply criteria filters, and deduplicate"
            ),
            WorkflowStep(
                step=5,
                action=ACTION_GENERATE_EXCEL,
                value=category,
                app="Excel",
                description=f"Automatically generate structured Excel report (.xlsx)"
            ),
            WorkflowStep(
                step=6,
                action=ACTION_VERIFY,
                app="Verification",
                description=f"Verify product data integrity and capture final browser state"
            )
        ]

        wf = Workflow(
            workflow_id=generate_id("wf"),
            workflow_name=wf_title,
            prompt=prompt,
            steps=steps,
            applications=["Selenium Browser", "Amazon", "Flipkart", "Excel"],
            understood=True,
            user_id=user_id,
            status="CREATED",
            created_at=current_iso_time()
        )
        add_log_entry(f"Generated product workflow '{wf.workflow_name}' ({len(wf.steps)} steps).", "SUCCESS")
        return wf

    # 4. Otherwise query local Ollama model
    try:
        raw_json = query_ollama(prompt)
        raw_steps = raw_json.get("steps", [])

        if raw_steps:
            parsed_steps = []
            for idx, s in enumerate(raw_steps, start=1):
                parsed_steps.append(
                    WorkflowStep(
                        step=s.get("step", idx),
                        action=s.get("action", "").upper(),
                        target=s.get("target"),
                        value=s.get("value"),
                        url=s.get("url"),
                        description=s.get("description"),
                        requires_confirmation=s.get("requires_confirmation", False)
                    )
                )

            wf = Workflow(
                workflow_id=generate_id("wf"),
                workflow_name=raw_json.get("workflow_name", "Automated Workflow"),
                prompt=prompt,
                steps=parsed_steps,
                applications=raw_json.get("applications", ["Employee Work Portal"]),
                understood=raw_json.get("understood", True),
                question=raw_json.get("question"),
                user_id=user_id,
                status="CREATED",
                created_at=current_iso_time()
            )
            add_log_entry(f"Generated workflow '{wf.workflow_name}' via Ollama with {len(wf.steps)} steps.")
            return wf

    except Exception as e:
        logger.warning(f"Ollama generation fallback triggered: {e}")

    # 5. Clarification fallback
    return Workflow(
        workflow_id=generate_id("wf"),
        workflow_name="Clarification Required",
        prompt=prompt,
        steps=[],
        understood=False,
        question="Please specify the workflow details or select one of the 5 quick examples (e.g., invoices, office supplies, daily work, meeting, or reporting).",
        user_id=user_id,
        status="FAILED",
        created_at=current_iso_time()
    )
