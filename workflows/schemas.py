"""
Pydantic Schemas for WorkPilot Workflow Automation System
Supports Browser and Cross-Application Workflows with Verification & History Tracking.
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class TargetElement(BaseModel):
    """Represents a DOM target strategy."""
    type: str = Field(default="css", description="Selector type: 'id', 'name', 'css', 'xpath', or 'semantic'")
    value: str = Field(..., description="Selector query or semantic name")


class WorkflowStep(BaseModel):
    """Represents a single atomic action (browser or cross-application)."""
    step: int = Field(default=1, description="Step sequence number")
    action: str = Field(..., description="Action name, e.g., OPEN_URL, TYPE, READ_EXCEL, SEND_EMAIL, VERIFY, etc.")
    target: Optional[Union[TargetElement, str]] = Field(default=None, description="Element target identifier or parameter")
    value: Optional[str] = Field(default=None, description="Input text, file path, status, or parameter")
    url: Optional[str] = Field(default=None, description="Target URL for OPEN_URL action")
    description: Optional[str] = Field(default=None, description="Human-readable step description")
    app: Optional[str] = Field(default=None, description="Associated application: Browser, Excel, Email, Calendar, Tasks, Invoice")
    requires_confirmation: Optional[bool] = Field(default=False, description="True if step requires human confirmation before running")

    def get_target_string(self) -> str:
        """Returns target as string representation."""
        if isinstance(self.target, TargetElement):
            return self.target.value
        return str(self.target or "")

    def to_display_label(self) -> str:
        """Formats the step for friendly display in Streamlit."""
        act = self.action.upper()
        if self.description:
            return self.description

        if act == "OPEN_URL":
            return f"Open {self.url or 'URL'}"
        elif act in ("TYPE", "SEARCH"):
            t = self.get_target_string() or "input"
            return f"Enter '{self.value or ''}' into {t}"
        elif act == "CLICK":
            return f"Click {self.get_target_string() or 'button'}"
        elif act == "SELECT":
            return f"Select '{self.value or ''}' from {self.get_target_string() or 'dropdown'}"
        elif act == "SCROLL":
            return f"Scroll page {self.value or 'down'}"
        elif act == "WAIT":
            return f"Wait {self.value or '2'} seconds"
        elif act == "SCREENSHOT":
            return "Take page screenshot"
        elif act == "GO_BACK":
            return "Go back to previous page"
        elif act == "GET_TEXT":
            return f"Extract text from {self.get_target_string()}"
        elif act == "READ_EXCEL":
            return f"Read data from {self.value or 'Excel spreadsheet'}"
        elif act == "SEARCH_EMAIL":
            return f"Search authorized email account for '{self.value or self.get_target_string() or 'matching messages'}'"
        elif act == "READ_EMAIL":
            return "Read the matching email messages"
        elif act == "EXTRACT_EMAIL_INFO":
            return "Extract action items, invoice references, deadlines, and payment details"
        elif act == "COMPOSE_EMAIL":
            return "Compose personalized email previews from validated source data"
        elif act == "ATTACH_FILE":
            return "Validate and attach the matching document for each recipient"
        elif act == "RECORD_RESULT":
            return "Record provider evidence and per-recipient outcome"
        elif act == "FIND_UNPAID_INVOICES":
            return "Find unpaid and overdue invoices"
        elif act == "EXTRACT_INVOICE":
            return f"Locate and extract invoice document for {self.get_target_string() or 'unpaid accounts'}"
        elif act == "GENERATE_REMINDER":
            return f"Generate reminder email drafts with invoice attachments"
        elif act == "SEND_EMAIL":
            return f"Send emails to {self.get_target_string() or 'clients'}"
        elif act == "SEARCH_EMAIL":
            return f"Search mailbox for {self.value or self.get_target_string() or 'matching messages'}"
        elif act == "READ_EMAIL":
            return f"Read matching email messages"
        elif act == "COMPOSE_EMAIL":
            return "Compose personalized email previews"
        elif act == "ATTACH_FILE":
            return "Validate and attach the matching document"
        elif act == "UPDATE_EXCEL":
            return f"Update status in Excel records"
        elif act == "SEARCH_PRODUCT":
            return f"Search relevant websites for '{self.value or self.get_target_string()}'"
        elif act == "EXTRACT_PRODUCT_DATA":
            return f"Extract real product data (Name, Website, Price, Link) across shopping websites"
        elif act == "VALIDATE_PRODUCTS":
            return f"Validate collected products, apply budget filters, and deduplicate"
        elif act == "GENERATE_EXCEL":
            return f"Automatically generate structured Excel report (.xlsx)"
        elif act == "ADD_TO_CART":
            return f"Add matching product to cart"
        elif act == "REVIEW_ORDER":
            return "Review staged order and calculate totals"
        elif act == "DOWNLOAD_INVOICE":
            return "Download order invoice"
        elif act == "CHECK_CALENDAR":
            return f"Check today's schedule for {self.value or 'meetings'}"
        elif act == "CHECK_TASKS":
            return "Read pending tasks from task board"
        elif act == "UPDATE_TASK":
            return f"Update task status to {self.value or 'Completed'}"
        elif act == "GENERATE_BRIEF":
            return f"Synthesize meeting brief with emails & project documents"
        elif act == "GENERATE_REPORT":
            return f"Aggregate activity data and compile employee report"
        elif act == "VERIFY":
            return f"Verify execution status and data integrity"
        return f"{self.action} on {self.get_target_string() or self.url or self.value or ''}"


class Workflow(BaseModel):
    """Represents a complete validated workflow."""
    workflow_id: Optional[str] = Field(default=None, description="Unique workflow ID")
    workflow_name: str = Field(default="Automated Task", description="Human-friendly workflow title")
    prompt: str = Field(default="", description="Original natural-language user prompt")
    steps: List[WorkflowStep] = Field(default_factory=list, description="Sequence of workflow steps")
    understood: bool = Field(default=True, description="True if AI successfully understood the task")
    question: Optional[str] = Field(default=None, description="Clarification question if understood is False")
    user_id: Optional[str] = Field(default=None, description="Owner user ID")
    status: str = Field(default="CREATED", description="Workflow status: CREATED, VALIDATED, RUNNING, COMPLETED, FAILED")
    applications: List[str] = Field(default_factory=list, description="List of applications used in workflow")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp")


class Execution(BaseModel):
    """Represents an execution run of a workflow."""
    execution_id: str = Field(..., description="Unique execution UUID")
    workflow_id: str = Field(..., description="Associated workflow ID")
    user_id: str = Field(..., description="User ID that triggered the execution")
    status: str = Field(default="RUNNING", description="RUNNING, COMPLETED, FAILED, WAITING_CONFIRMATION")
    started_at: str = Field(..., description="ISO start timestamp")
    completed_at: Optional[str] = Field(default=None, description="ISO finish timestamp")
    completed_steps: int = Field(default=0, description="Count of successfully executed steps")
    total_steps: int = Field(default=0, description="Total steps in workflow")
    failed_step: Optional[int] = Field(default=None, description="Step number that failed, if any")
    error_message: Optional[str] = Field(default=None, description="Error explanation on failure")
    execution_time: float = Field(default=0.0, description="Execution duration in seconds")
    screenshots: List[str] = Field(default_factory=list, description="Screenshot URLs or file paths")
    applications: List[str] = Field(default_factory=list, description="Applications touched")
    step_results: List[Dict[str, Any]] = Field(default_factory=list, description="Per-step execution logs")
    verification_results: List[Dict[str, Any]] = Field(default_factory=list, description="Verification checks")


class ExecutionResult(BaseModel):
    """Represents the finalized outcome of a workflow execution."""
    result_id: str = Field(..., description="Unique result UUID")
    execution_id: str = Field(..., description="Associated execution ID")
    workflow_id: str = Field(..., description="Associated workflow ID")
    user_id: str = Field(..., description="User ID")
    status: str = Field(default="SUCCESS", description="SUCCESS, PARTIAL_SUCCESS, FAILED")
    summary: str = Field(default="", description="Human-readable result summary")
    output: Dict[str, Any] = Field(default_factory=dict, description="Execution metrics and extracted data")
    applications: List[str] = Field(default_factory=list, description="Applications used")
    step_executions: List[str] = Field(default_factory=list, description="Completed execution checklist items")
    verification_items: List[str] = Field(default_factory=list, description="Verification checklist items")
    created_at: str = Field(..., description="ISO creation timestamp")
