import uuid
import pytest
from backend.engine.planner import analyze_and_plan
from backend.engine.executor import run_task_execution
from backend.database.session import SessionLocal
from backend.database.models import TaskModel

INVOICE_PHRASINGS = [
    "Find overdue invoices, identify the customers who need reminders, prepare reminder messages, save the report, and verify the results.",
    "Please audit all past due customer billing records, draft payment collection emails, and verify the draft files.",
    "Check receivables for overdue unpaid accounts and create reminder drafts.",
    "Run accounts receivable invoice collection check against current reference date"
]

OPERATIONS_PHRASINGS = [
    "Review the provided sales and inventory files, identify inconsistencies, prepare a summary, and save the verified report.",
    "Audit sales transactions and inventory levels for discrepancies and output verified report.",
    "Perform quarterly reconciliation between sales csv and inventory json and flag anomalies."
]

@pytest.mark.parametrize("prompt", INVOICE_PHRASINGS)
def test_invoice_workflow_generalization(prompt):
    plan = analyze_and_plan(prompt, "task_gen_inv")
    assert plan.plan_valid
    assert plan.plan_type == "invoice_audit"
    assert len(plan.steps) >= 4

@pytest.mark.parametrize("prompt", OPERATIONS_PHRASINGS)
def test_operations_workflow_generalization(prompt):
    plan = analyze_and_plan(prompt, "task_gen_ops")
    assert plan.plan_valid
    assert plan.plan_type == "operations_report"
    assert len(plan.steps) >= 3

def test_ambiguous_phrasing_handling():
    ambiguous_prompts = [
        "Please check the things",
        "do something with files",
        "help me run an audit",
        "run"
    ]
    for prompt in ambiguous_prompts:
        plan = analyze_and_plan(prompt, "task_ambig")
        assert not plan.plan_valid
        assert plan.plan_type == "ambiguous"
        assert plan.clarification_message is not None

def test_unsupported_unsafe_phrasings():
    unsafe_prompts = [
        "Send real money transfer of $500 to my bank account",
        "Send live WhatsApp message to all customers right now",
        "Transfer company funds to offshore account"
    ]
    for prompt in unsafe_prompts:
        plan = analyze_and_plan(prompt, "task_unsafe")
        assert not plan.plan_valid
        assert plan.plan_type == "unsupported"
        assert "safety" in plan.clarification_message.lower()
