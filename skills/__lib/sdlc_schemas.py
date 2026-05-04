import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TaskRouting(BaseModel):
    skill: str = Field(..., description="The skill to route the task to (e.g., /code, /tdd)")
    route: str = Field(..., description="The internal route/mode for the skill")

class TaskContract(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    title: str
    objective: str
    status: str = "ready" # ready, in-progress, blocked, completed
    priority: str = "P2"
    scope_in: List[str] = []
    scope_out: List[str] = []
    forbidden_files: List[str] = []
    acceptance_criteria: List[str]
    verification_commands: List[str] = []
    task_type: str = "implementation"
    routing: TaskRouting

class PlanMetadata(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    version: str = "2.0.0"
    status: str = "draft" # draft, in-review, implementation-ready
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    terminal_id: str = Field(default_factory=lambda: os.environ.get("CLAUDE_TERMINAL_ID", "unknown"))

class ImplementationPlan(BaseModel):
    metadata: PlanMetadata
    goal: str
    architecture_summary: str
    tasks: List[TaskContract]
    assumptions: List[str] = []
    open_questions: List[str] = []
    contract_authority_reference: Optional[str] = None
