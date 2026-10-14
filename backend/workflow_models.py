from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ActionEnum(str, Enum):
    OPEN = "open"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    UPLOAD = "upload"
    WAIT = "wait"
    SCREENSHOT = "screenshot"


ALLOWED_ACTIONS = {action.value for action in ActionEnum}


class WorkflowStep(BaseModel):
    action: str = Field(description="The action type: open, click, fill, select, upload, wait, screenshot")
    field: Optional[str] = Field(default=None, description="Target label, placeholder, name, id, or selector")
    value: Optional[str] = Field(default=None, description="Input text, selected value, file path, or wait seconds")
    url: Optional[str] = Field(default=None, description="URL for 'open' action")
    selector: Optional[str] = Field(default=None, description="Explicit CSS or XPath selector if available")

    @field_validator("action", mode="before")
    @classmethod
    def validate_action_name(cls, v: str) -> str:
        if isinstance(v, str):
            clean_action = v.strip().lower()
            if clean_action in ALLOWED_ACTIONS:
                return clean_action
            raise ValueError(f"Unsupported action: '{v}'. Must be one of {sorted(list(ALLOWED_ACTIONS))}")
        return v

    def to_display_tuple(self) -> tuple:
        """Converts step to (Action, Target, Details) tuple matching frontend UI expectations."""
        action_title = self.action.capitalize()
        target = self.field or self.url or self.selector or "Page"
        details = self.value or self.url or self.field or "Execute step"
        return (action_title, str(target), str(details))


class Workflow(BaseModel):
    understood: bool = Field(default=True, description="Whether the user instruction was successfully understood")
    steps: List[WorkflowStep] = Field(default_factory=list, description="List of validated workflow steps")
    question: Optional[str] = Field(default=None, description="Clarification question if understood is False")

    @field_validator("steps")
    @classmethod
    def validate_understood_steps(cls, steps: List[WorkflowStep], info) -> List[WorkflowStep]:
        # We can check understood state from values if needed
        return steps


class WorkflowResult(BaseModel):
    success: bool
    completed_steps: int
    total_steps: int
    message: str
    error: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    screenshots: List[str] = Field(default_factory=list)
