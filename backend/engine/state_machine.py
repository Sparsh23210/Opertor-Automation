from typing import Literal
from sqlalchemy.orm import Session
from backend.database.models import TaskModel

TaskStatus = Literal[
    "pending",
    "understanding",
    "planning",
    "validating",
    "running",
    "executing",
    "waiting_for_approval",
    "awaiting_clarification",
    "blocked",
    "verifying",
    "completed",
    "partially_completed",
    "failed",
    "cancelled"
]

LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"planning", "understanding", "cancelled"},
    "understanding": {"planning", "awaiting_clarification", "blocked", "failed", "cancelled"},
    "planning": {"running", "executing", "waiting_for_approval", "awaiting_clarification", "blocked", "failed", "cancelled"},
    "validating": {"running", "executing", "planning", "blocked", "failed", "cancelled"},
    "running": {"running", "executing", "waiting_for_approval", "awaiting_clarification", "blocked", "verifying", "partially_completed", "failed", "cancelled"},
    "executing": {"running", "waiting_for_approval", "awaiting_clarification", "blocked", "verifying", "partially_completed", "failed", "cancelled"},
    "waiting_for_approval": {"running", "executing", "failed", "cancelled"},
    "awaiting_clarification": {"planning", "cancelled", "failed"},
    "blocked": {"planning", "failed", "cancelled"},
    "verifying": {"completed", "partially_completed", "failed"},
    "completed": set(),            # Terminal state
    "partially_completed": set(),  # Terminal state
    "failed": set(),               # Terminal state
    "cancelled": set()             # Terminal state
}

class InvalidStateTransitionError(Exception):
    pass

def can_transition(current_status: str, target_status: str) -> bool:
    allowed = LEGAL_TRANSITIONS.get(current_status, set())
    return target_status in allowed

def transition_task(db: Session, task: TaskModel, target_status: str, error_message: str | None = None) -> TaskModel:
    current = task.status
    if not can_transition(current, target_status):
        raise InvalidStateTransitionError(
            f"Illegal state transition from '{current}' to '{target_status}'. Allowed transitions: {LEGAL_TRANSITIONS.get(current, set())}"
        )

    task.status = target_status
    if error_message:
        task.error_message = error_message

    db.add(task)
    db.commit()
    db.refresh(task)
    return task
