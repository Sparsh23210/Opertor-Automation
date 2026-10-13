import pytest
from pathlib import Path
from backend.config import resolve_safe_path, settings
from backend.engine.planner import analyze_and_plan, validate_plan_tools
from backend.engine.state_machine import can_transition, transition_task, InvalidStateTransitionError
from backend.database.session import SessionLocal
from backend.database.models import TaskModel
from backend.tools.invoice_tools import handle_audit_invoices, AuditInvoicesInput

def test_resolve_safe_path_valid():
    safe = resolve_safe_path("data/policies/sop_invoice_collection.md")
    assert safe.exists()
    assert "data" in safe.as_posix()

def test_resolve_safe_path_traversal_blocked():
    with pytest.raises(PermissionError):
        resolve_safe_path("../../windows/system32/cmd.exe")

def test_empty_request_rejected():
    plan = analyze_and_plan("", "test_task_empty")
    assert not plan.plan_valid
    assert "empty" in plan.error_message.lower()

def test_unsupported_transfer_request_rejected():
    plan = analyze_and_plan("Send real payment of $50,000 to vendor via wire", "test_unsupported")
    assert not plan.plan_valid
    assert plan.plan_type == "unsupported"
    assert "safety" in plan.clarification_message.lower()

def test_ambiguous_request_triggers_clarification():
    plan = analyze_and_plan("check files", "test_ambiguous")
    assert not plan.plan_valid
    assert plan.plan_type == "ambiguous"
    assert plan.clarification_message is not None

def test_valid_invoice_plan_generation():
    plan = analyze_and_plan("Find overdue invoices, prepare reminders, and verify results.", "task_inv_1")
    assert plan.plan_valid
    assert plan.plan_type in ("invoice_audit", "predefined_fallback")
    assert len(plan.steps) >= 3
    is_valid, err = validate_plan_tools(plan)
    assert is_valid, err

def test_valid_operations_plan_generation():
    plan = analyze_and_plan("Review sales and inventory files for inconsistencies and save report.", "task_ops_1")
    assert plan.plan_valid
    assert plan.plan_type in ("operations_report", "predefined_fallback")
    assert len(plan.steps) >= 3
    is_valid, err = validate_plan_tools(plan)
    assert is_valid, err

def test_state_machine_legal_transitions():
    assert can_transition("pending", "planning")
    assert can_transition("planning", "running")
    assert can_transition("running", "verifying")
    assert can_transition("verifying", "completed")
    assert can_transition("running", "waiting_for_approval")
    assert can_transition("waiting_for_approval", "running")

def test_state_machine_terminal_state_enforced():
    # Once completed, a task cannot transition back to running
    assert not can_transition("completed", "running")
    assert not can_transition("failed", "running")
    assert not can_transition("cancelled", "running")

def test_invoice_audit_determines_correct_overdue_status():
    res = handle_audit_invoices(AuditInvoicesInput(reference_date="2026-10-10"))
    assert res.success
    summary = res.data["summary"]
    assert summary["overdue_unpaid_count"] == 4
    assert summary["disputed_count"] == 1
    assert summary["invalid_count"] == 1
    assert summary["paid_count"] == 1
