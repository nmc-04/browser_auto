"""
Workflow Validator Module
Strictly validates workflow schemas, allowed browser and enterprise actions, parameters, URLs, and targets.
"""

from typing import Tuple, Optional
from workflows.actions import (
    SUPPORTED_ACTIONS,
    BROWSER_ACTIONS,
    CROSS_APP_ACTIONS,
    ACTION_OPEN_URL,
    ACTION_TYPE,
    ACTION_CLICK,
    ACTION_SEARCH,
    ACTION_SELECT,
    ACTION_WAIT,
    ACTION_GET_TEXT,
    ACTION_READ_EXCEL,
    ACTION_SEND_EMAIL,
    ACTION_SEARCH_EMAIL,
    ACTION_READ_EMAIL,
    ACTION_EXTRACT_EMAIL_INFO,
    ACTION_COMPOSE_EMAIL,
    ACTION_ATTACH_FILE,
    ACTION_RECORD_RESULT,
    ACTION_UPDATE_EXCEL,
    ACTION_UPDATE_TASK,
    ACTION_SEARCH_PRODUCT,
)
from workflows.schemas import Workflow, WorkflowStep
from utils.helpers import is_valid_url
from utils.logger import logger


def validate_workflow(workflow: Workflow) -> Tuple[bool, Optional[str]]:
    """
    Validates a Workflow object for strict execution safety.
    Returns: (is_valid: bool, error_message: Optional[str])
    """
    if not isinstance(workflow, Workflow):
        return False, "Input is not a valid Workflow schema instance."

    # 1. Check if AI indicated it didn't understand
    if not workflow.understood:
        question = workflow.question or "Instruction was unclear or incomplete. Please provide more details."
        return False, f"Clarification required: {question}"

    # 2. Check if steps exist
    if not workflow.steps:
        return False, "Generated workflow contains no actionable steps."

    # 3. Validate each individual step
    for idx, step in enumerate(workflow.steps, start=1):
        if not isinstance(step, WorkflowStep):
            return False, f"Step {idx} has invalid schema structure."

        action = (step.action or "").upper()

        # Check action in allowed list
        if action not in SUPPORTED_ACTIONS:
            return False, f"Step {idx}: Unsupported action '{step.action}'. Permitted actions: {sorted(list(SUPPORTED_ACTIONS))}."

        # Action-specific field validations
        if action == ACTION_OPEN_URL:
            url = step.url or step.value or step.get_target_string()
            if not url:
                return False, f"Step {idx} (OPEN_URL): Missing required URL parameter."
            if not (is_valid_url(url) or "html" in url.lower() or "." in url):
                return False, f"Step {idx} (OPEN_URL): Invalid URL format '{url}'."

        elif action in (ACTION_TYPE, ACTION_SEARCH):
            target = step.get_target_string()
            if not target:
                return False, f"Step {idx} ({action}): Missing target input field or selector."
            if step.value is None:
                return False, f"Step {idx} ({action}): Missing text 'value' to enter."

        elif action == ACTION_CLICK:
            target = step.get_target_string()
            if not target:
                return False, f"Step {idx} (CLICK): Missing target element to click."

        elif action == ACTION_SELECT:
            target = step.get_target_string()
            if not target:
                return False, f"Step {idx} (SELECT): Missing dropdown target element."
            if not step.value:
                return False, f"Step {idx} (SELECT): Missing option 'value' to select."

        elif action == ACTION_WAIT:
            if step.value:
                try:
                    val = float(step.value)
                    if val < 0 or val > 60:
                        return False, f"Step {idx} (WAIT): Wait duration must be between 0 and 60 seconds."
                except ValueError:
                    return False, f"Step {idx} (WAIT): Invalid numeric wait duration '{step.value}'."

        elif action == ACTION_GET_TEXT:
            target = step.get_target_string()
            if not target:
                return False, f"Step {idx} (GET_TEXT): Missing target element to extract text from."

        # Enterprise action checks
        elif action == ACTION_READ_EXCEL:
            # path is optional (defaults to demo_data files)
            pass

        elif action == ACTION_SEARCH_EMAIL:
            if not step.value and not step.get_target_string():
                return False, f"Step {idx} (SEARCH_EMAIL): Missing natural-language search query."

        elif action in (ACTION_READ_EMAIL, ACTION_EXTRACT_EMAIL_INFO, ACTION_COMPOSE_EMAIL, ACTION_ATTACH_FILE, ACTION_RECORD_RESULT):
            # These actions operate on the shared execution context. A target
            # is optional because batch email workflows use all prior matches.
            pass

        elif action == ACTION_SEND_EMAIL:
            if not step.requires_confirmation:
                return False, f"Step {idx} (SEND_EMAIL): External email dispatch must require human confirmation."

        elif action == ACTION_SEARCH_PRODUCT:
            if not step.value and not step.get_target_string():
                return False, f"Step {idx} (SEARCH_PRODUCT): Missing product search keyword."

        elif action == ACTION_UPDATE_TASK:
            if not step.get_target_string() and not step.value:
                return False, f"Step {idx} (UPDATE_TASK): Missing task identifier or new status."

    logger.info(f"Workflow '{workflow.workflow_name}' ({len(workflow.steps)} steps) passed all validation checks.")
    return True, None
