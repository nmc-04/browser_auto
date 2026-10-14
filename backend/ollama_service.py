"""
Ollama Service - Local LLM Natural Language Understanding
Converts natural-language instructions into structured JSON workflows for browser and enterprise tasks.
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from workflows.schemas import Workflow, WorkflowStep
from workflows.actions import SUPPORTED_ACTIONS
from utils.logger import logger, add_log_entry

load_dotenv(override=True)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


class OllamaUnavailableError(Exception):
    """Raised when Ollama local daemon is unreachable."""
    pass


class OllamaParseError(Exception):
    """Raised when LLM output cannot be parsed into valid Workflow JSON."""
    pass


SYSTEM_PROMPT = """You are WorkPilot AI, an expert autonomous Workflow Planner and Computer-Use Engine.
Your job is to convert natural-language user instructions into a strictly structured JSON multi-step automation workflow.

IMPORTANT RULES & CONSTRAINTS:
1. Respond ONLY with a valid JSON object. Do not include introductory text, conversational remarks, or markdown explanations.
2. Supported actions are:
   BROWSER ACTIONS:
   - "OPEN_URL": Open a webpage or local demo file (requires "url")
   - "TYPE": Enter text into an input field (requires "target" and "value")
   - "SEARCH": Enter text into search input and press Enter (requires "target" and "value")
   - "CLICK": Click a button, link, or element (requires "target")
   - "SELECT": Choose an option from a dropdown (requires "target" and "value")
   - "SCROLL": Scroll the webpage (optional "value" e.g. "down" or "up")
   - "WAIT": Pause execution (optional "value" in seconds, e.g. "2")
   - "GO_BACK": Navigate back to previous page
   - "GET_TEXT": Extract text from an element (requires "target")
   - "SCREENSHOT": Take a page screenshot
   - "SEARCH_PRODUCT": Search product catalog using Selenium (requires "value")
   - "ADD_TO_CART": Add matching product to cart using Selenium (requires "target")
   - "REVIEW_ORDER": Review cart and stage procurement order using Selenium (requires "target")
   - "DOWNLOAD_INVOICE": Download invoice/receipt via browser using Selenium (requires "target")

   CROSS-APPLICATION & ENTERPRISE ACTIONS:
   - "READ_EXCEL": Read data from an Excel workbook or spreadsheet (optional "value" file path)
   - "FIND_UNPAID_INVOICES": Filter unpaid or overdue invoices from loaded records
   - "EXTRACT_INVOICE": Locate and read corresponding invoice documents from archive
   - "GENERATE_REMINDER": Compose reminder email drafts with invoice attachments
   - "SEND_EMAIL": Send email notifications or reminders (optional "requires_confirmation": true)
   - "UPDATE_EXCEL": Update record status in Excel workbook (requires "value" e.g. "Reminder Sent")
   - "CHECK_CALENDAR": Check today's schedule and meetings (optional "value" e.g. "3 PM")
   - "CHECK_TASKS": Read pending tasks from task board
   - "UPDATE_TASK": Update task progress or status (requires "target" task ID and "value" status)
   - "GENERATE_BRIEF": Synthesize executive meeting brief from calendar, emails, and documents
   - "GENERATE_REPORT": Aggregate cross-app metrics and compile structured employee report
   - "VERIFY": Explicitly verify execution outcome, file creation, or data status

3. Schema required:
{
  "workflow_name": "Short Descriptive Title",
  "understood": true | false,
  "applications": ["Excel", "Email", "Invoice System", "Selenium Browser", "Calendar", "Task Board"],
  "steps": [
    {
      "step": 1,
      "action": "ACTION_NAME",
      "target": "target selector, field, or identifier",
      "value": "parameter or text value",
      "url": "url if OPEN_URL",
      "description": "Human readable action description",
      "requires_confirmation": false
    }
  ],
  "question": null
}

4. EXAMPLES FOR FIVE MAJOR DEMONSTRATIONS:

Demo 1: "Handle my work for today."
{
  "workflow_name": "Employee Daily Work Automation",
  "understood": true,
  "applications": ["Calendar", "Task Board", "Email", "Documents"],
  "steps": [
    {"step": 1, "action": "CHECK_CALENDAR", "description": "Check today's schedule and client meetings"},
    {"step": 2, "action": "CHECK_TASKS", "description": "Read pending daily tasks from Task Board"},
    {"step": 3, "action": "UPDATE_TASK", "target": "TASK-101", "value": "In Progress", "description": "Advance high-priority task preparation"},
    {"step": 4, "action": "UPDATE_TASK", "target": "TASK-102", "value": "Completed", "description": "Mark completed administrative tasks"},
    {"step": 5, "action": "GENERATE_REPORT", "description": "Synthesize daily executive work summary"},
    {"step": 6, "action": "VERIFY", "description": "Verify task status updates and summary generation"}
  ],
  "question": null
}

Demo 2: "Find all unpaid invoices and send reminder emails" OR "Process today's invoices" OR "Process all unpaid invoices"
{
  "workflow_name": "Invoice Reconcile & Client Reminder Workflow",
  "understood": true,
  "applications": ["Excel", "Invoice System", "Email"],
  "steps": [
    {"step": 1, "action": "READ_EXCEL", "value": "demo_data/invoices.xlsx", "description": "Read invoice data from Excel"},
    {"step": 2, "action": "FIND_UNPAID_INVOICES", "description": "Identify all unpaid and overdue invoices"},
    {"step": 3, "action": "EXTRACT_INVOICE", "description": "Find and extract corresponding invoice documents"},
    {"step": 4, "action": "GENERATE_REMINDER", "description": "Generate reminder emails with invoice attachments"},
    {"step": 5, "action": "SEND_EMAIL", "requires_confirmation": true, "description": "Send reminder emails to respective clients"},
    {"step": 6, "action": "UPDATE_EXCEL", "value": "Reminder Sent", "description": "Update invoice payment status in Excel records"},
    {"step": 7, "action": "VERIFY", "description": "Verify sent emails and updated invoice records"}
  ],
  "question": null
}

Demo 3: "Order the office supplies in this spreadsheet" OR "Order the required office supplies from the product list"
{
  "workflow_name": "Office Supplies Procurement Workflow",
  "understood": true,
  "applications": ["Excel", "Selenium Browser", "Procurement System", "Email"],
  "steps": [
    {"step": 1, "action": "READ_EXCEL", "value": "demo_data/products.xlsx", "description": "Read required product list from Excel"},
    {"step": 2, "action": "OPEN_URL", "url": "demo_site/ecommerce.html", "description": "Open office supply e-commerce store in Selenium"},
    {"step": 3, "action": "SEARCH_PRODUCT", "value": "A4 Copy Paper", "description": "Search for A4 copy paper using Selenium"},
    {"step": 4, "action": "ADD_TO_CART", "target": "#add-btn-1", "description": "Add A4 paper reams to shopping cart"},
    {"step": 5, "action": "SEARCH_PRODUCT", "value": "Ballpoint Pens", "description": "Search for ballpoint pens using Selenium"},
    {"step": 6, "action": "ADD_TO_CART", "target": "#add-btn-2", "description": "Add pen pack to shopping cart"},
    {"step": 7, "action": "REVIEW_ORDER", "target": "#checkout-btn", "requires_confirmation": true, "description": "Review order totals and stage checkout (Awaiting confirmation)"},
    {"step": 8, "action": "DOWNLOAD_INVOICE", "target": "#downloadInvoiceBtn", "description": "Download order invoice statement"},
    {"step": 9, "action": "VERIFY", "description": "Verify items in cart and order staging"}
  ],
  "question": null
}

Demo 4: "Prepare for my 3 PM client meeting."
{
  "workflow_name": "Client Meeting Preparation Assistant",
  "understood": true,
  "applications": ["Calendar", "Email", "Documents", "Task Board"],
  "steps": [
    {"step": 1, "action": "CHECK_CALENDAR", "value": "3 PM", "description": "Find 3 PM meeting in calendar schedule"},
    {"step": 2, "action": "GENERATE_BRIEF", "target": "3 PM", "value": "Acrom Systems", "description": "Search related emails, project documents, and contract terms"},
    {"step": 3, "action": "GENERATE_BRIEF", "description": "Compile structured executive meeting brief"},
    {"step": 4, "action": "VERIFY", "description": "Verify meeting brief created and all client docs attached"}
  ],
  "question": null
}

Demo 5: "Prepare this month's employee activity report."
{
  "workflow_name": "Monthly Employee Activity & Performance Report",
  "understood": true,
  "applications": ["Task Board", "Calendar", "Email", "Excel"],
  "steps": [
    {"step": 1, "action": "CHECK_TASKS", "description": "Collect completed and pending tasks from Task Board"},
    {"step": 2, "action": "CHECK_CALENDAR", "description": "Collect calendar meeting history and engagements"},
    {"step": 3, "action": "GENERATE_REPORT", "description": "Aggregate authentic activity metrics and compile report"},
    {"step": 4, "action": "SEND_EMAIL", "target": "management@workpilot.com", "requires_confirmation": true, "description": "Send activity report to manager"},
    {"step": 5, "action": "VERIFY", "description": "Verify report document generated and email dispatched"}
  ],
  "question": null
}

BROWSER FORM EXAMPLE:
"Open demo_site/form.html, enter John Doe as name, john@example.com as email, select Male, and click submit"
{
  "workflow_name": "Submit Demo Registration Form",
  "understood": true,
  "applications": ["Selenium Browser"],
  "steps": [
    {"step": 1, "action": "OPEN_URL", "url": "demo_site/form.html", "description": "Open registration form in browser"},
    {"step": 2, "action": "TYPE", "target": "name", "value": "John Doe", "description": "Enter name"},
    {"step": 3, "action": "TYPE", "target": "email", "value": "john@example.com", "description": "Enter email"},
    {"step": 4, "action": "SELECT", "target": "gender", "value": "Male", "description": "Select Male"},
    {"step": 5, "action": "CLICK", "target": "submit-btn", "description": "Click submit button"}
  ],
  "question": null
}
"""


def check_ollama_status(host: str = OLLAMA_HOST) -> bool:
    """Checks if Ollama server is alive and reachable."""
    try:
        resp = requests.get(f"{host}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def get_available_models(host: str = OLLAMA_HOST) -> List[str]:
    """Returns list of model names currently installed in Ollama."""
    try:
        resp = requests.get(f"{host}/api/tags", timeout=3)
        if resp.status_code == 200:
            return [m.get("name") for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def query_ollama(prompt: str, model: Optional[str] = None, host: Optional[str] = None) -> Dict[str, Any]:
    """
    Sends natural language prompt to Ollama and returns parsed JSON dictionary.
    """
    load_dotenv(override=True)
    target_host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
    target_model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    timeout = int(os.getenv("OLLAMA_TIMEOUT", "180"))

    if not check_ollama_status(target_host):
        raise OllamaUnavailableError("Ollama is not running. Please start the Ollama service (`ollama serve`) and try again.")

    # Auto-detect available models to prevent mismatches
    installed_models = get_available_models(target_host)
    if installed_models and target_model not in installed_models:
        matches = [m for m in installed_models if target_model in m or m.startswith(target_model.split(":")[0])]
        if matches:
            target_model = matches[0]
        elif len(installed_models) == 1:
            target_model = installed_models[0]

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Instruction: {prompt}"}
        ],
        "stream": False,
        "format": "json"
    }

    add_log_entry(f"Sending prompt to Ollama model '{target_model}'...")

    try:
        response = requests.post(f"{target_host}/api/chat", json=payload, timeout=timeout)
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            try:
                err_data = response.json()
                if "error" in err_data:
                    error_msg = err_data["error"]
            except Exception:
                pass
            raise OllamaUnavailableError(f"Ollama returned error: {error_msg}")

        data = response.json()
        content = data.get("message", {}).get("content", "").strip()

    except requests.exceptions.Timeout:
        raise OllamaUnavailableError(f"Ollama request timed out after {timeout}s while processing with model '{target_model}'.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama connection error: {e}")
        raise OllamaUnavailableError(f"Failed to communicate with Ollama: {e}")

    if not content:
        raise OllamaParseError("Ollama returned an empty response.")

    # Cleanup potential markdown wrapper blocks
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()

    try:
        parsed_json = json.loads(content)
        return parsed_json
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode failed on Ollama output: {content}")
        raise OllamaParseError(f"Could not parse AI output into JSON: {e}")
