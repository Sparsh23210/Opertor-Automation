import uuid
import pytest
from backend.database.session import SessionLocal
from backend.database.models import TaskModel, TaskStepModel
from backend.engine.planner import (
    analyze_and_plan,
    validate_plan_tools,
    diagnose_failure_with_llm,
    PREDEFINED_WORKFLOWS
)
from backend.engine.executor import run_task_execution, is_saved_output_reusable

def test_predefined_workflow_registry_validity():
    """All registered predefined workflows must pass strict tool schema validation."""
    for wf in PREDEFINED_WORKFLOWS:
        plan = wf.builder(f"test_{wf.workflow_id}", "Sample request")
        assert plan.plan_valid
        is_valid, err = validate_plan_tools(plan)
        assert is_valid, f"Workflow {wf.workflow_id} failed tool validation: {err}"

def test_hybrid_fallback_on_unconfigured_llm(monkeypatch):
    """When Gemini LLM is not configured, system seamlessly activates Level 3 predefined workflow."""
    from backend.config import settings
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    plan = analyze_and_plan("Find overdue invoices and draft payment reminder emails", "test_task_hybrid_1")
    assert plan.plan_valid
    assert plan.plan_source == "predefined_fallback"
    assert plan.plan_type == "invoice_audit"
    assert len(plan.steps) >= 4

def test_hybrid_planning_with_gemini_active():
    """When Gemini LLM is configured, system plans successfully via Gemini or predefined fallback."""
    plan = analyze_and_plan("Find overdue invoices and draft payment reminder emails", "test_task_hybrid_gemini")
    assert plan.plan_valid
    assert plan.plan_type == "invoice_audit"
    assert len(plan.steps) >= 3

def test_failure_diagnosis_classifier():
    """Level 2 / Level 1 diagnostic classifier categorizes failure modes correctly."""
    # Permission error -> abort
    diag_perm = diagnose_failure_with_llm("Audit", "Read", "read_file", "Permission denied: access outside root")
    assert diag_perm["category"] == "permission"
    assert not diag_perm["can_retry"]

    # Missing file -> abort
    diag_miss = diagnose_failure_with_llm("Audit", "Read", "read_file", "File not found: data/missing.csv")
    assert diag_miss["category"] == "missing_data"
    assert not diag_miss["can_retry"]

    # Timeout -> retry
    diag_trans = diagnose_failure_with_llm("Audit", "Query", "query_invoices", "Database locked timeout error")
    assert diag_trans["category"] == "transient"
    assert diag_trans["can_retry"]

def test_saved_output_reuse_behavior():
    """Verifies that an already completed step with valid upstream dependencies is reused."""
    task_id = str(uuid.uuid4())
    db = SessionLocal()
    task = TaskModel(id=task_id, original_request="Audit invoices", normalized_goal="", status="running")
    db.add(task)

    step0 = TaskStepModel(
        id=str(uuid.uuid4()), task_id=task_id, step_index=0, name="Step 0",
        tool_name="search_company_policies", tool_args_json='{"query": "invoice"}',
        status="completed", result_json='{"matches": []}', attempt_count=1
    )
    step1 = TaskStepModel(
        id=str(uuid.uuid4()), task_id=task_id, step_index=1, name="Step 1",
        tool_name="query_invoice_records", tool_args_json='{"limit": 100}',
        status="completed", result_json='{"records": []}', attempt_count=1
    )
    db.add_all([step0, step1])
    db.commit()

    # Step 1 with matching args and completed upstream -> reusable
    assert is_saved_output_reusable(step1, db, {"limit": 100}) is True

    # Step 1 with changed args -> NOT reusable
    assert is_saved_output_reusable(step1, db, {"limit": 50}) is False

    # If upstream step was failed -> NOT reusable
    step0.status = "failed"
    db.commit()
    assert is_saved_output_reusable(step1, db, {"limit": 100}) is False
    db.close()
