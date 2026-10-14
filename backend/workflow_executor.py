"""
Workflow Executor Module
High-level interface invoked by Streamlit frontend.
Executes both Browser (Selenium) and Enterprise Cross-Application Workflows with Verification.
"""

from typing import Dict, Any, Callable, Optional
from workflows.schemas import Workflow
from backend.workflow_generator import generate_workflow
from backend.workflow_validator import validate_workflow
from backend.cross_app_engine import execute_cross_app_workflow
from backend.workflow_graph import node_save_to_firebase, node_generate_result, node_error_handler
from utils.logger import logger, add_log_entry
from utils.helpers import generate_id, current_iso_time
from backend.db import save_history_entry


def plan_workflow(prompt: str, user_id: str) -> Dict[str, Any]:
    """
    Executes LangGraph planning stages (Parse -> Generate -> Validate).
    Returns dictionary with validated Workflow schema or error information.
    """
    try:
        wf = generate_workflow(prompt=prompt, user_id=user_id)
        is_valid, error = validate_workflow(wf)

        if not is_valid:
            return {
                "success": False,
                "workflow": wf,
                "error": error,
                "status": "VALIDATION_FAILED"
            }

        return {
            "success": True,
            "workflow": wf,
            "error": None,
            "status": "READY"
        }

    except Exception as e:
        logger.error(f"Planning failed: {e}")
        return {
            "success": False,
            "workflow": None,
            "error": str(e),
            "status": "ERROR"
        }


def execute_workflow_run(
    workflow: Workflow,
    user_id: str,
    headless: bool = False,
    timeout: int = 15,
    confirmed: bool = False,
    status_callback: Optional[Callable[[int, str, str], None]] = None
) -> Dict[str, Any]:
    """
    Executes validated workflow (Browser or Enterprise Cross-Application) and persists all data to Firebase.
    """
    add_log_entry(f"Executing workflow '{workflow.workflow_name}' for user '{user_id}' (Confirmed={confirmed})...")

    exec_res = execute_cross_app_workflow(
        workflow=workflow,
        headless=headless,
        timeout=timeout,
        confirmed=confirmed,
        status_callback=status_callback
    )

    success = exec_res["success"]
    completed_steps = exec_res["completed_steps"]
    total_steps = exec_res["total_steps"]
    duration = exec_res["execution_time"]
    err = exec_res["error"]
    screenshots = exec_res.get("screenshots", [])
    final_screenshot = exec_res.get("final_screenshot")
    apps_used = exec_res.get("applications", [])
    exec_checklist = exec_res.get("execution_checklist", [])
    verif_items = exec_res.get("verification_items", [])
    status_str = exec_res.get("status", "COMPLETED" if success else "FAILED")

    products = exec_res.get("products", [])
    excel_file = exec_res.get("excel_file")
    email_results = exec_res.get("email_results", [])
    email_summary = exec_res.get("email_summary", {})
    execution_context = exec_res.get("context", {})

    # State for Firebase saving
    state = {
        "user_id": user_id,
        "workflow_id": workflow.workflow_id or generate_id("wf"),
        "workflow_name": workflow.workflow_name,
        "prompt": workflow.prompt,
        "generated_steps": [s.model_dump() for s in workflow.steps],
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "execution_status": status_str,
        "error_message": err,
        "execution_time": duration,
        "screenshots": screenshots,
        "final_screenshot": final_screenshot,
        "applications": apps_used,
        "extracted_data": {
            "applications": apps_used,
            "execution_checklist": exec_checklist,
            "verification_items": verif_items,
            "final_screenshot": final_screenshot,
            "products": products,
            "excel_file": excel_file,
            "email_results": email_results,
            "email_summary": email_summary,
            "email_messages": execution_context.get("email_messages", []),
            "email_insights": execution_context.get("email_insights", []),
            "email_extracted": execution_context.get("email_extracted", []),
            "email_preview": execution_context.get("email_preview", []),
            "email_provider": execution_context.get("email_provider", {}),
            "context": execution_context,
        },
        "workflow_obj": workflow
    }

    if status_str in ("COMPLETED", "PARTIAL_SUCCESS", "PENDING_VERIFICATION"):
        state = node_generate_result(state)
    elif status_str == "WAITING_CONFIRMATION":
        state["result_summary"] = "Workflow prepared and paused. Awaiting human confirmation for sensitive operations."
    else:
        state = node_error_handler(state)

    # Persist in Firebase
    try:
        node_save_to_firebase(state)
    except Exception as e:
        logger.warning(f"Firebase save notice: {e}")

    # Keep the existing local SQLite history useful when Firebase is not
    # configured.  The structured email details remain in the Firebase/local
    # execution record above; this row is the compatible compact index.
    try:
        save_history_entry(
            instruction=workflow.prompt,
            steps=completed_steps,
            status=status_str,
            execution_time=duration,
            logs="\n".join(exec_checklist + verif_items),
        )
    except Exception as e:
        logger.warning(f"SQLite history save notice: {e}")

    return {
        "success": success,
        "status": status_str,
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "execution_time": duration,
        "error": err,
        "summary": state.get("result_summary"),
        "screenshots": screenshots,
        "final_screenshot": final_screenshot,
        "applications": apps_used,
        "execution_checklist": exec_checklist,
        "verification_items": verif_items,
        "requires_confirmation": exec_res.get("requires_confirmation", False),
        "products": products,
        "excel_file": excel_file,
        "context": execution_context,
        "email_results": email_results,
        "email_summary": email_summary,
        "extracted_data": state.get("extracted_data", {})
    }
