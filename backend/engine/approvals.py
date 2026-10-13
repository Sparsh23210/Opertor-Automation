import json
from datetime import datetime, timezone
from backend.database.session import SessionLocal
from backend.database.models import TaskModel, TaskStepModel, ApprovalModel
from backend.engine.state_machine import transition_task
from backend.tools.registry import registry

def approve_step_action(task_id: str, approval_id: str, notes: str = "") -> dict:
    db = SessionLocal()
    try:
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return {"error": f"Task '{task_id}' not found."}

        app = db.query(ApprovalModel).filter(ApprovalModel.id == approval_id, ApprovalModel.task_id == task_id).first()
        if not app:
            return {"error": f"Approval request '{approval_id}' not found."}

        if app.status != "pending":
            return {"error": f"Approval request is already '{app.status}'."}

        step = db.query(TaskStepModel).filter(TaskStepModel.id == app.step_id).first()
        if not step:
            return {"error": f"Associated step '{app.step_id}' not found."}

        # Security check: Re-validate arguments against registered tool schema
        tool_def = registry.get(step.tool_name)
        if not tool_def:
            return {"error": f"Security violation: tool '{step.tool_name}' is not registered."}

        try:
            payload = json.loads(step.tool_args_json or "{}")
            tool_def.input_schema(**payload)
        except Exception as e:
            return {"error": f"Re-validation failed upon approval: {str(e)}"}

        app.status = "approved"
        app.reviewer_notes = notes or "Approved by operator"
        app.responded_at = datetime.now(timezone.utc)

        step.approval_status = "approved"
        step.status = "pending"

        task.status = "running"
        db.commit()

        # Import run_task_execution to continue execution
        from backend.engine.executor import run_task_execution
        result = run_task_execution(task.id)
        return {"success": True, "task": result}
    finally:
        db.close()

def reject_step_action(task_id: str, approval_id: str, notes: str = "") -> dict:
    db = SessionLocal()
    try:
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return {"error": f"Task '{task_id}' not found."}

        app = db.query(ApprovalModel).filter(ApprovalModel.id == approval_id, ApprovalModel.task_id == task_id).first()
        if not app:
            return {"error": f"Approval request '{approval_id}' not found."}

        if app.status != "pending":
            return {"error": f"Approval request is already '{app.status}'."}

        step = db.query(TaskStepModel).filter(TaskStepModel.id == app.step_id).first()
        if step:
            step.approval_status = "rejected"
            step.status = "failed"
            step.error_message = f"Action rejected: {notes or 'No reason provided'}"

        app.status = "rejected"
        app.reviewer_notes = notes or "Rejected by operator"
        app.responded_at = datetime.now(timezone.utc)

        task = transition_task(db, task, "failed", error_message=f"Action '{step.name if step else 'Protected step'}' was rejected by human operator.")
        db.commit()

        return {"success": True, "task": task.to_dict()}
    finally:
        db.close()

def cancel_task_execution(task_id: str) -> dict:
    db = SessionLocal()
    try:
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return {"error": f"Task '{task_id}' not found."}

        if task.status in ("completed", "cancelled", "failed", "partially_completed"):
            return {"error": f"Cannot cancel task in terminal state '{task.status}'."}

        # Cancel pending approvals
        for app in task.approvals:
            if app.status == "pending":
                app.status = "cancelled"

        # Cancel pending steps
        for step in task.steps:
            if step.status in ("pending", "waiting_approval"):
                step.status = "skipped"

        task = transition_task(db, task, "cancelled", error_message="Task cancelled by user.")
        db.commit()
        return {"success": True, "task": task.to_dict()}
    finally:
        db.close()
