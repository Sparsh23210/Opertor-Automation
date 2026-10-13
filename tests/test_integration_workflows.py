import uuid
import pytest
from backend.database.session import SessionLocal
from backend.database.models import TaskModel, TaskStepModel, ApprovalModel
from backend.engine.executor import run_task_execution
from backend.engine.approvals import approve_step_action, reject_step_action, cancel_task_execution
from backend.config import settings

def test_workflow_a_invoice_audit_end_to_end():
    task_id = str(uuid.uuid4())
    db = SessionLocal()
    task = TaskModel(
        id=task_id,
        original_request="Find overdue invoices, identify the customers who need reminders, prepare reminder messages, save the report, and verify the results.",
        normalized_goal="",
        status="pending"
    )
    db.add(task)
    db.commit()
    db.close()

    result = run_task_execution(task_id)
    assert result["status"] == "completed"
    assert result["current_step_index"] == 4

    # Verify database state
    db = SessionLocal()
    saved_task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    assert saved_task.status == "completed"
    assert len(saved_task.steps) == 5
    assert all(s.status == "completed" for s in saved_task.steps)

    # Verify evidence ledger
    assert len(saved_task.evidence) >= 5
    verification_entry = next((e for e in saved_task.evidence if e.tool_name == "verify_artifact_content"), None)
    assert verification_entry is not None
    assert verification_entry.verification_status == "verified"

    # Verify created artifacts
    assert len(saved_task.artifacts) >= 2
    for art in saved_task.artifacts:
        art_file = settings.OUTPUT_DIR / art.filename
        assert art_file.exists()
        assert art_file.stat().st_size > 0
        assert art.verification_status == "verified"
    db.close()

def test_workflow_b_operations_audit_end_to_end():
    task_id = str(uuid.uuid4())
    db = SessionLocal()
    task = TaskModel(
        id=task_id,
        original_request="Review the provided sales and inventory files, identify inconsistencies, prepare a summary, and save the verified report.",
        normalized_goal="",
        status="pending"
    )
    db.add(task)
    db.commit()
    db.close()

    result = run_task_execution(task_id)
    assert result["status"] == "completed"

    db = SessionLocal()
    saved_task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    assert saved_task.status == "completed"
    assert len(saved_task.steps) == 4
    assert len(saved_task.artifacts) >= 2

    # Check report artifact content
    report_art = next((a for a in saved_task.artifacts if a.artifact_type == "operations_report"), None)
    assert report_art is not None
    content = (settings.OUTPUT_DIR / report_art.filename).read_text(encoding="utf-8")
    assert "Executive Summary" in content
    assert "Inventory Reconciliation" in content
    assert "Discrepancies" in content
    db.close()

def test_human_approval_pause_and_resume():
    task_id = str(uuid.uuid4())
    db = SessionLocal()
    task = TaskModel(
        id=task_id,
        original_request="Perform protected audit operation requiring human signoff",
        normalized_goal="",
        status="running"
    )
    db.add(task)
    db.commit()

    step = TaskStepModel(
        id=str(uuid.uuid4()),
        task_id=task_id,
        step_index=0,
        name="High-risk protected ledger modification",
        tool_name="search_company_policies",
        tool_args_json='{"query": "invoice"}',
        status="pending",
        requires_approval=True,
        approval_status="none"
    )
    db.add(step)
    db.commit()
    db.close()

    # Run execution -> should stop and wait for approval
    res = run_task_execution(task_id)
    assert res["status"] == "waiting_for_approval"

    # Check approval request was created
    db = SessionLocal()
    app = db.query(ApprovalModel).filter(ApprovalModel.task_id == task_id, ApprovalModel.status == "pending").first()
    assert app is not None
    app_id = app.id
    db.close()

    # Now approve action
    approved_res = approve_step_action(task_id, app_id, notes="Approved by Senior Audit Manager")
    assert approved_res["success"]
    assert approved_res["task"]["status"] == "completed"

def test_human_approval_rejection():
    task_id = str(uuid.uuid4())
    db = SessionLocal()
    task = TaskModel(
        id=task_id,
        original_request="Protected action to be rejected",
        normalized_goal="",
        status="running"
    )
    db.add(task)
    db.commit()

    step = TaskStepModel(
        id=str(uuid.uuid4()),
        task_id=task_id,
        step_index=0,
        name="Unauthorized risky action",
        tool_name="search_company_policies",
        tool_args_json='{"query": "invoice"}',
        status="pending",
        requires_approval=True,
        approval_status="none"
    )
    db.add(step)
    db.commit()
    db.close()

    run_task_execution(task_id)

    db = SessionLocal()
    app = db.query(ApprovalModel).filter(ApprovalModel.task_id == task_id, ApprovalModel.status == "pending").first()
    app_id = app.id
    db.close()

    # Reject
    reject_res = reject_step_action(task_id, app_id, notes="Rejected due to compliance policy")
    assert reject_res["success"]
    assert reject_res["task"]["status"] == "failed"

def test_task_cancellation():
    task_id = str(uuid.uuid4())
    db = SessionLocal()
    task = TaskModel(
        id=task_id,
        original_request="Task to be cancelled",
        normalized_goal="",
        status="running"
    )
    db.add(task)
    db.commit()
    db.close()

    cancel_res = cancel_task_execution(task_id)
    assert cancel_res["success"]
    assert cancel_res["task"]["status"] == "cancelled"
