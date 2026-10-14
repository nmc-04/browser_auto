"""
Firestore Database Operations for Workflows, Executions, and Results
"""

from typing import List, Dict, Any, Optional
from firebase.firebase_config import get_firestore_db
from utils.logger import logger
from utils.helpers import current_iso_time

# Local in-memory store for fallback/demo when Firebase is unconfigured
_LOCAL_STORE: Dict[str, Dict[str, Dict[str, Any]]] = {
    "workflows": {},
    "executions": {},
    "results": {}
}


# ==========================================
# WORKFLOWS COLLECTION
# ==========================================

def save_workflow(workflow_data: Dict[str, Any]) -> str:
    """Saves workflow document into Firestore 'workflows' collection."""
    db = get_firestore_db()
    workflow_id = workflow_data.get("workflow_id")
    if not workflow_id:
        from utils.helpers import generate_id
        workflow_id = generate_id("wf")
        workflow_data["workflow_id"] = workflow_id

    if not workflow_data.get("created_at"):
        workflow_data["created_at"] = current_iso_time()

    if db:
        try:
            db.collection("workflows").document(workflow_id).set(workflow_data)
            logger.info(f"Saved workflow to Firestore: {workflow_id}")
            return workflow_id
        except Exception as e:
            logger.error(f"Firestore save_workflow error: {e}")

    _LOCAL_STORE["workflows"][workflow_id] = workflow_data
    return workflow_id


def get_user_workflows(user_id: str) -> List[Dict[str, Any]]:
    """Retrieves all workflows owned by a specific user_id."""
    db = get_firestore_db()
    results = []

    if db:
        try:
            docs = db.collection("workflows").where("user_id", "==", user_id).stream()
            for d in docs:
                results.append(d.to_dict())
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return results
        except Exception as e:
            logger.error(f"Firestore get_user_workflows error: {e}")

    # Fallback to local store
    for w in _LOCAL_STORE["workflows"].values():
        if w.get("user_id") == user_id:
            results.append(w)
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results


# ==========================================
# EXECUTIONS COLLECTION
# ==========================================

def save_execution(execution_data: Dict[str, Any]) -> str:
    """Saves execution run into Firestore 'executions' collection."""
    db = get_firestore_db()
    execution_id = execution_data.get("execution_id")

    if db:
        try:
            db.collection("executions").document(execution_id).set(execution_data)
            logger.info(f"Saved execution to Firestore: {execution_id}")
            return execution_id
        except Exception as e:
            logger.error(f"Firestore save_execution error: {e}")

    _LOCAL_STORE["executions"][execution_id] = execution_data
    return execution_id


def update_execution(execution_id: str, update_data: Dict[str, Any]) -> None:
    """Updates an existing execution document in Firestore."""
    db = get_firestore_db()
    if db:
        try:
            db.collection("executions").document(execution_id).update(update_data)
            return
        except Exception as e:
            logger.error(f"Firestore update_execution error: {e}")

    if execution_id in _LOCAL_STORE["executions"]:
        _LOCAL_STORE["executions"][execution_id].update(update_data)


def get_user_executions(user_id: str) -> List[Dict[str, Any]]:
    """Retrieves all execution records for a specific user."""
    db = get_firestore_db()
    results = []

    if db:
        try:
            docs = db.collection("executions").where("user_id", "==", user_id).stream()
            for d in docs:
                results.append(d.to_dict())
            results.sort(key=lambda x: x.get("started_at", ""), reverse=True)
            return results
        except Exception as e:
            logger.error(f"Firestore get_user_executions error: {e}")
            for d in docs:
                results.append(d.to_dict())
            return results
        except Exception as e:
            logger.error(f"Firestore get_user_executions error: {e}")

    for ex in _LOCAL_STORE["executions"].values():
        if ex.get("user_id") == user_id:
            results.append(ex)
    results.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return results


# ==========================================
# RESULTS COLLECTION
# ==========================================

def save_result(result_data: Dict[str, Any]) -> str:
    """Saves execution outcome in Firestore 'results' collection."""
    db = get_firestore_db()
    result_id = result_data.get("result_id")

    if db:
        try:
            db.collection("results").document(result_id).set(result_data)
            logger.info(f"Saved result to Firestore: {result_id}")
            return result_id
        except Exception as e:
            logger.error(f"Firestore save_result error: {e}")

    _LOCAL_STORE["results"][result_id] = result_data
    return result_id


def get_result(execution_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves the result document for a given execution ID."""
    db = get_firestore_db()

    if db:
        try:
            docs = db.collection("results").where("execution_id", "==", execution_id).limit(1).stream()
            doc = next(docs, None)
            if doc:
                return doc.to_dict()
        except Exception as e:
            logger.error(f"Firestore get_result error: {e}")

    for r in _LOCAL_STORE["results"].values():
        if r.get("execution_id") == execution_id:
            return r
    return None
