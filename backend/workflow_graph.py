"""
LangGraph Workflow Orchestrator
Manages state transitions: Parse -> Generate -> Validate -> Execute (Selenium) -> Result -> Save (Firebase).
"""

import time
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, START, END

from workflows.schemas import Workflow, WorkflowStep, Execution, ExecutionResult
from backend.workflow_generator import generate_workflow as generate_wf_service
from backend.workflow_validator import validate_workflow as validate_wf_service
from backend.selenium_engine import run_selenium_workflow
from backend.cross_app_engine import execute_cross_app_workflow
from firebase.database import save_workflow, save_execution, save_result
from firebase.storage import upload_screenshot
from utils.logger import logger, add_log_entry
from utils.helpers import generate_id, current_iso_time


class WorkflowState(TypedDict, total=False):
    """LangGraph shared workflow state."""
    user_id: str
    prompt: str
    workflow_id: str
    workflow_name: str
    generated_steps: List[Dict[str, Any]]
    current_step: int
    completed_steps: int
    total_steps: int
    execution_status: str  # READY, RUNNING, COMPLETED, FAILED
    error_message: Optional[str]
    result_summary: str
    execution_time: float
    screenshots: List[str]
    extracted_data: Dict[str, Any]
    workflow_obj: Optional[Workflow]
    headless: bool
    status_callback: Any


# ==========================================
# LANGGRAPH NODE FUNCTIONS
# ==========================================

def node_parse_prompt(state: WorkflowState) -> WorkflowState:
    """Node 1: Parses and prepares user prompt."""
    prompt = (state.get("prompt") or "").strip()
    add_log_entry(f"[LangGraph Node: parse_prompt] Received prompt: '{prompt}'")
    return {
        **state,
        "prompt": prompt,
        "execution_status": "PARSING",
        "error_message": None
    }


def node_generate_workflow(state: WorkflowState) -> WorkflowState:
    """Node 2: Calls Ollama to produce structured workflow."""
    prompt = state.get("prompt", "")
    user_id = state.get("user_id", "anonymous")
    add_log_entry("[LangGraph Node: generate_workflow] Querying Ollama...")

    try:
        wf = generate_wf_service(prompt=prompt, user_id=user_id)
        steps_dict = [s.model_dump() for s in wf.steps]
        return {
            **state,
            "workflow_id": wf.workflow_id or generate_id("wf"),
            "workflow_name": wf.workflow_name,
            "generated_steps": steps_dict,
            "total_steps": len(wf.steps),
            "workflow_obj": wf,
            "execution_status": "GENERATED"
        }
    except Exception as e:
        logger.error(f"Generation error in LangGraph: {e}")
        return {
            **state,
            "execution_status": "FAILED",
            "error_message": str(e)
        }


def node_validate_workflow(state: WorkflowState) -> WorkflowState:
    """Node 3: Validates actions and schema safety."""
    add_log_entry("[LangGraph Node: validate_workflow] Checking action safety and parameters...")
    wf = state.get("workflow_obj")

    if not wf:
        return {
            **state,
            "execution_status": "FAILED",
            "error_message": state.get("error_message") or "No workflow object generated to validate."
        }

    is_valid, err = validate_wf_service(wf)
    if not is_valid:
        add_log_entry(f"[LangGraph Validation Failed]: {err}")
        return {
            **state,
            "execution_status": "FAILED",
            "error_message": err
        }

    add_log_entry("[LangGraph Validation Succeeded]: Workflow verified.")
    return {
        **state,
        "execution_status": "VALIDATED"
    }


def node_workflow_ready(state: WorkflowState) -> WorkflowState:
    """Node 4: Marks workflow as ready for user execution."""
    add_log_entry("[LangGraph Node: workflow_ready] Workflow is staged and ready to run.")
    return {
        **state,
        "execution_status": "READY"
    }


def node_execute_workflow(state: WorkflowState) -> WorkflowState:
    """Node 5: Executes validated actions using Selenium engine and enterprise tools."""
    wf = state.get("workflow_obj")
    headless = state.get("headless", False)
    status_cb = state.get("status_callback")
    confirmed = state.get("confirmed", False)

    add_log_entry(f"[LangGraph Node: execute_workflow] Launching execution for '{wf.workflow_name if wf else 'Task'}' (Headless={headless})...")
    start_time = time.time()

    res = execute_cross_app_workflow(
        workflow=wf,
        headless=headless,
        timeout=20,
        confirmed=confirmed,
        status_callback=status_cb
    )

    duration = round(time.time() - start_time, 2)
    success = res["success"]
    completed_steps = res["completed_steps"]
    screenshots = res.get("screenshots", [])
    err = res.get("error")
    status_str = res.get("status", "COMPLETED" if success else "FAILED")

    extracted = {
        "applications": res.get("applications", []),
        "execution_checklist": res.get("execution_checklist", []),
        "verification_items": res.get("verification_items", []),
        "context": res.get("context", {}),
        "email_results": res.get("email_results", []),
        "email_summary": res.get("email_summary", {}),
    }

    return {
        **state,
        "execution_status": status_str,
        "completed_steps": completed_steps,
        "execution_time": duration,
        "screenshots": screenshots,
        "extracted_data": extracted,
        "error_message": err
    }


def node_generate_result(state: WorkflowState) -> WorkflowState:
    """Node 6: Creates human-readable result summary."""
    completed = state.get("completed_steps", 0)
    total = state.get("total_steps", 0)
    duration = state.get("execution_time", 0.0)
    wf_name = state.get("workflow_name", "Browser Task")

    execution_status = state.get("execution_status", "COMPLETED")
    email_summary = state.get("extracted_data", {}).get("email_summary", {})
    if execution_status == "PARTIAL_SUCCESS":
        summary = (
            f"Workflow '{wf_name}' partially completed ({completed}/{total} steps) in {duration}s. "
            f"Submitted {email_summary.get('submitted', 0)} email(s); failed {email_summary.get('failed', 0)}."
        )
    elif execution_status == "PENDING_VERIFICATION":
        summary = (
            f"Workflow '{wf_name}' is pending provider verification after {completed}/{total} steps. "
            f"Submitted {email_summary.get('submitted', 0)} email(s)."
        )
    else:
        summary = f"Workflow '{wf_name}' completed successfully ({completed}/{total} steps) in {duration}s."
    add_log_entry(f"[LangGraph Node: generate_result] {summary}")

    return {
        **state,
        "result_summary": summary
    }


def node_save_to_firebase(state: WorkflowState) -> WorkflowState:
    """Node 7: Persists workflow, execution, and result in Firebase."""
    user_id = state.get("user_id", "anonymous")
    wf_id = state.get("workflow_id", generate_id("wf"))
    exec_id = generate_id("exec")
    status = state.get("execution_status", "UNKNOWN")
    error_msg = state.get("error_message")
    screenshots = state.get("screenshots", [])

    add_log_entry(f"[LangGraph Node: save_to_firebase] Saving records for user '{user_id}'...")

    # Upload screenshots to Firebase Storage
    storage_urls = []
    for shot in screenshots:
        url = upload_screenshot(shot, user_id=user_id, execution_id=exec_id)
        storage_urls.append(url or shot)

    # 1. Save Workflow
    wf_record = {
        "workflow_id": wf_id,
        "user_id": user_id,
        "prompt": state.get("prompt", ""),
        "workflow_name": state.get("workflow_name", "Browser Workflow"),
        "generated_steps": state.get("generated_steps", []),
        "status": status,
        "created_at": current_iso_time()
    }
    save_workflow(wf_record)

    # 2. Save Execution
    exec_record = {
        "execution_id": exec_id,
        "workflow_id": wf_id,
        "user_id": user_id,
        "status": status,
        "started_at": current_iso_time(),
        "completed_at": current_iso_time(),
        "completed_steps": state.get("completed_steps", 0),
        "total_steps": state.get("total_steps", 0),
        "failed_step": (state.get("completed_steps", 0) + 1) if status == "FAILED" else None,
        "error_message": error_msg,
        "execution_time": state.get("execution_time", 0.0),
        "screenshots": storage_urls,
        "applications": state.get("applications", []),
        "email_summary": state.get("extracted_data", {}).get("email_summary", {}),
        "email_results": state.get("extracted_data", {}).get("email_results", [])
    }
    save_execution(exec_record)

    # 3. Save Result
    res_record = {
        "result_id": generate_id("res"),
        "execution_id": exec_id,
        "workflow_id": wf_id,
        "user_id": user_id,
        "status": (
            "SUCCESS" if status == "COMPLETED" else
            ("WAITING_CONFIRMATION" if status == "WAITING_CONFIRMATION" else
             ("PARTIAL_SUCCESS" if status == "PARTIAL_SUCCESS" else
              ("PENDING_VERIFICATION" if status == "PENDING_VERIFICATION" else "FAILED")))
        ),
        "summary": state.get("result_summary") or error_msg or "Execution concluded.",
        "output": state.get("extracted_data", {}),
        "created_at": current_iso_time()
    }
    save_result(res_record)

    return state


def node_error_handler(state: WorkflowState) -> WorkflowState:
    """Node 8: Handles failures and formats error summary."""
    err = state.get("error_message") or "An unexpected error occurred."
    completed = state.get("completed_steps", 0)
    failed_step = completed + 1

    summary = f"Workflow failed at step {failed_step}: {err}"
    add_log_entry(f"[LangGraph Node: error_handler] {summary}")

    return {
        **state,
        "result_summary": summary,
        "execution_status": "FAILED"
    }


# ==========================================
# CONDITIONAL ROUTING EDGES
# ==========================================

def route_after_validation(state: WorkflowState) -> str:
    """Routes to workflow_ready on valid, else to error_handler."""
    if state.get("execution_status") == "VALIDATED":
        return "workflow_ready"
    return "error_handler"


def route_after_execution(state: WorkflowState) -> str:
    """Routes to generate_result on success, else to error_handler."""
    if state.get("execution_status") == "COMPLETED":
        return "generate_result"
    return "error_handler"


# ==========================================
# GRAPH BUILDER
# ==========================================

def build_workflow_graph() -> StateGraph:
    """Constructs the complete compiled LangGraph StateGraph."""
    graph = StateGraph(WorkflowState)

    # Add Nodes
    graph.add_node("parse_prompt", node_parse_prompt)
    graph.add_node("generate_workflow", node_generate_workflow)
    graph.add_node("validate_workflow", node_validate_workflow)
    graph.add_node("workflow_ready", node_workflow_ready)
    graph.add_node("execute_workflow", node_execute_workflow)
    graph.add_node("generate_result", node_generate_result)
    graph.add_node("save_to_firebase", node_save_to_firebase)
    graph.add_node("error_handler", node_error_handler)

    # Define Graph Edges
    graph.add_edge(START, "parse_prompt")
    graph.add_edge("parse_prompt", "generate_workflow")
    graph.add_edge("generate_workflow", "validate_workflow")

    graph.add_conditional_edges(
        "validate_workflow",
        route_after_validation,
        {
            "workflow_ready": "workflow_ready",
            "error_handler": "error_handler"
        }
    )

    graph.add_edge("workflow_ready", "execute_workflow")

    graph.add_conditional_edges(
        "execute_workflow",
        route_after_execution,
        {
            "generate_result": "generate_result",
            "error_handler": "error_handler"
        }
    )

    graph.add_edge("generate_result", "save_to_firebase")
    graph.add_edge("error_handler", "save_to_firebase")
    graph.add_edge("save_to_firebase", END)

    return graph.compile()


# Singleton compiled graph instance
compiled_graph = build_workflow_graph()
