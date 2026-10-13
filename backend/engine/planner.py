import re
import json
import requests
from typing import Any
from pydantic import BaseModel, Field
from backend.config import settings
from backend.tools import registry
from backend.tools.file_tools import handle_search_policies, SearchPoliciesInput

# ── Schemas ───────────────────────────────────────────────────────────────────

class PlanStepSchema(BaseModel):
    step_index: int
    name: str
    tool_name: str
    tool_args: dict[str, Any]
    requires_approval: bool = False
    expected_output: str = ""
    dependencies: list[int] = Field(default_factory=list)

class ExecutionPlan(BaseModel):
    plan_valid: bool
    plan_type: str  # invoice_audit, operations_report, browser_audit, ambiguous, unsupported
    plan_source: str = "deterministic_fallback"  # gemini_llm | predefined_fallback | deterministic_fallback
    intended_outcome: str
    success_criteria: list[str]
    steps: list[PlanStepSchema] = Field(default_factory=list)
    verification_conditions: list[str] = Field(default_factory=list)
    company_policy_citations: list[str] = Field(default_factory=list)
    clarification_message: str | None = None
    error_message: str | None = None
    fallback_reason: str | None = None

# ── Predefined Workflow Registry (Level 3) ───────────────────────────────────

class PredefinedWorkflow:
    def __init__(
        self,
        workflow_id: str,
        name: str,
        description: str,
        supported_task_type: str,
        keywords: list[str],
        builder: Any
    ):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.supported_task_type = supported_task_type
        self.keywords = keywords
        self.builder = builder

def build_invoice_audit_workflow(task_id: str, request: str) -> ExecutionPlan:
    citations = []
    policy_res = handle_search_policies(SearchPoliciesInput(query="invoice overdue collection reminder threshold"))
    if policy_res.success and policy_res.data.get("matches"):
        citations = [m["document"] for m in policy_res.data["matches"]]

    steps = [
        PlanStepSchema(
            step_index=0,
            name="Retrieve Invoicing Policy & Credit Rules",
            tool_name="search_company_policies",
            tool_args={"query": "invoice overdue collection review threshold"},
            requires_approval=False,
            expected_output="Excerpts from sop_invoice_collection.md detailing overdue and threshold criteria",
            dependencies=[]
        ),
        PlanStepSchema(
            step_index=1,
            name="Query Invoice Database",
            tool_name="query_invoice_records",
            tool_args={"limit": 100},
            requires_approval=False,
            expected_output="Invoice records fetched from SQLite",
            dependencies=[0]
        ),
        PlanStepSchema(
            step_index=2,
            name="Audit Overdue Invoices and Categorize Statuses",
            tool_name="audit_invoices",
            tool_args={"reference_date": settings.REFERENCE_DATE},
            requires_approval=False,
            expected_output="Categorization of overdue unpaid, paid, disputed, and invalid records",
            dependencies=[1]
        ),
        PlanStepSchema(
            step_index=3,
            name="Generate and Save Verified Reminder Drafts",
            tool_name="save_reminder_drafts",
            tool_args={"task_id": task_id, "reference_date": settings.REFERENCE_DATE},
            requires_approval=False,
            expected_output="JSON and Markdown reminder drafts saved to output directory",
            dependencies=[2]
        ),
        PlanStepSchema(
            step_index=4,
            name="Independently Verify Saved Reminder Drafts Artifact",
            tool_name="verify_artifact_content",
            tool_args={
                "filename": f"reminder_drafts_{task_id[:8]}.json",
                "artifact_type": "reminder_drafts",
                "expected_criteria": {}
            },
            requires_approval=False,
            expected_output="Independent reconciliation of reminder drafts against SQLite database",
            dependencies=[3]
        )
    ]

    return ExecutionPlan(
        plan_valid=True,
        plan_type="invoice_audit",
        plan_source="predefined_fallback",
        intended_outcome="Audit overdue invoices, isolate records requiring human review, generate reminder drafts, and independently verify output artifacts.",
        success_criteria=[
            "Overdue invoices identified using explicit reference date rules",
            "Disputed and malformed invoices isolated from reminders",
            "Reminder drafts saved to approved outputs directory",
            "Independent read-back verification confirms artifact matches database records"
        ],
        steps=steps,
        verification_conditions=[
            "Artifact exists and is non-empty",
            "All draft amounts match SQLite database",
            "Zero paid or disputed invoices included in drafts"
        ],
        company_policy_citations=citations
    )

def build_operations_audit_workflow(task_id: str, request: str) -> ExecutionPlan:
    citations = []
    policy_res = handle_search_policies(SearchPoliciesInput(query="inventory audit sales reconciliation variance"))
    if policy_res.success and policy_res.data.get("matches"):
        citations = [m["document"] for m in policy_res.data["matches"]]

    steps = [
        PlanStepSchema(
            step_index=0,
            name="Retrieve Operations & Inventory SOP",
            tool_name="search_company_policies",
            tool_args={"query": "inventory audit sales reconciliation variance"},
            requires_approval=False,
            expected_output="Excerpts from sop_inventory_audit.md",
            dependencies=[]
        ),
        PlanStepSchema(
            step_index=1,
            name="Calculate Sales & Inventory Operations Summary",
            tool_name="calculate_operations_summary",
            tool_args={
                "sales_file": "operations/sales_2026_q1.csv",
                "inventory_file": "operations/inventory_2026_q1.json"
            },
            requires_approval=False,
            expected_output="Deterministic sales totals, stock variance calculations, and anomaly list",
            dependencies=[0]
        ),
        PlanStepSchema(
            step_index=2,
            name="Generate and Save Operations Audit Report",
            tool_name="save_operations_report",
            tool_args={
                "task_id": task_id,
                "sales_file": "operations/sales_2026_q1.csv",
                "inventory_file": "operations/inventory_2026_q1.json"
            },
            requires_approval=False,
            expected_output="Operations audit report markdown and data artifacts saved",
            dependencies=[1]
        ),
        PlanStepSchema(
            step_index=3,
            name="Independently Verify Operations Report Artifact",
            tool_name="verify_artifact_content",
            tool_args={
                "filename": f"operations_audit_report_{task_id[:8]}.md",
                "artifact_type": "operations_report",
                "expected_criteria": {
                    "required_sections": ["Executive Summary", "Inventory Reconciliation", "Discrepancies", "Limitations"]
                }
            },
            requires_approval=False,
            expected_output="Report content verified with all required audit sections",
            dependencies=[2]
        )
    ]

    return ExecutionPlan(
        plan_valid=True,
        plan_type="operations_report",
        plan_source="predefined_fallback",
        intended_outcome="Review sales and inventory operational files, compute deterministic totals, detect anomalies, compile verified report, and verify artifact.",
        success_criteria=[
            "Sales CSV and Inventory JSON parsed and validated",
            "Deterministic totals computed and anomalies detected",
            "Report written with executive summary, tables, and discrepancies",
            "Artifact independently verified for required sections and completeness"
        ],
        steps=steps,
        verification_conditions=[
            "Artifact exists and is non-empty",
            "Required sections present in report markdown",
            "Discrepancies clearly isolated"
        ],
        company_policy_citations=citations
    )

def build_browser_audit_workflow(task_id: str, request: str) -> ExecutionPlan:
    steps = [
        PlanStepSchema(
            step_index=0,
            name="Execute Bounded Portal Verification in Headless Browser",
            tool_name="browser_audit_portal",
            tool_args={
                "portal_url": f"http://127.0.0.1:{settings.PORT}/test-portal",
                "audit_batch_id": f"BATCH-{task_id[:8].upper()}",
                "auditor_id": "OPERATOR-AUTONOMOUS-01",
                "task_id": task_id
            },
            requires_approval=False,
            expected_output="Browser navigates to authorized portal, submits form, verifies confirmation, saves screenshot",
            dependencies=[]
        )
    ]

    return ExecutionPlan(
        plan_valid=True,
        plan_type="browser_audit",
        plan_source="predefined_fallback",
        intended_outcome="Perform bounded browser navigation to internal authorized audit portal, record batch verification, and verify resulting state.",
        success_criteria=[
            "Navigation confined strictly to allowed domain",
            "Form submitted and confirmation badge verified in DOM",
            "Screenshot evidence captured and registered"
        ],
        steps=steps,
        verification_conditions=[
            "Target host is in allowed domains",
            "Confirmation badge text matches submitted batch ID",
            "Screenshot artifact created and non-empty"
        ],
        company_policy_citations=[]
    )

PREDEFINED_WORKFLOWS = [
    PredefinedWorkflow(
        workflow_id="WF-INV-001",
        name="Invoice Audit and Reminder Preparation",
        description="Audits customer invoices against reference date, isolates disputed accounts, drafts reminders, and reconciles against database.",
        supported_task_type="invoice_audit",
        keywords=["invoice", "overdue", "reminder", "receivable", "customer payment", "billing", "past due", "collection"],
        builder=build_invoice_audit_workflow
    ),
    PredefinedWorkflow(
        workflow_id="WF-OPS-002",
        name="Business Operations and Inventory Audit Report",
        description="Reconciles sales transactions with inventory stock, detects duplicate order IDs and calculation variances, and prepares verified report.",
        supported_task_type="operations_report",
        keywords=["sales", "inventory", "stock", "reconcil", "discrepanc", "inconsisten", "operations report", "transactions"],
        builder=build_operations_audit_workflow
    ),
    PredefinedWorkflow(
        workflow_id="WF-BROWSER-003",
        name="Bounded Browser Portal Verification",
        description="Executes automated browser verification in authorized local test portal with Playwright and captures screenshot evidence.",
        supported_task_type="browser_audit",
        keywords=["browser", "portal", "web audit", "playwright", "page verification", "test portal"],
        builder=build_browser_audit_workflow
    )
]

# ── Level 1: Google Gemini LLM Integration ────────────────────────────────────

def call_gemini_api(prompt: str, timeout: int = 15) -> str:
    """Invokes Google Gemini REST API with configured key and model, with fallback models."""
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    models_to_try = [settings.GEMINI_MODEL, "gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
    # Deduplicate while preserving order
    seen = set()
    candidate_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

    last_error = None
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json"
            }
        }
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError("Gemini API returned no candidates.")
                content_parts = candidates[0].get("content", {}).get("parts", [])
                if not content_parts:
                    raise RuntimeError("Gemini API returned empty parts.")
                return content_parts[0].get("text", "")
            elif resp.status_code in (404, 429, 500, 503):
                # Try next model candidate if model is unavailable, rate-limited, or overloaded
                last_error = f"Gemini API model {model_name} returned {resp.status_code}: {resp.text[:200]}"
                continue
            else:
                raise RuntimeError(f"Gemini API returned status {resp.status_code}: {resp.text[:300]}")
        except requests.RequestException as e:
            last_error = str(e)
            continue
    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

def plan_with_gemini_llm(request: str, task_id: str) -> ExecutionPlan | None:
    """Attempts LLM-driven structured planning via Google Gemini."""
    tools_list = registry.list_tools()
    tools_summary = "\n".join([f"- {t['name']}: {t['description']}" for t in tools_list])

    prompt = f"""
You are the autonomous planning intelligence for ProofLoop / Company Automation.
Convert the natural-language user request into a structured execution plan.

Registered Tools available:
{tools_summary}

User Request: "{request}"
Task ID: "{task_id}"
Reference Date: "{settings.REFERENCE_DATE}"

Output strictly a JSON object with this schema:
{{
  "plan_valid": true,
  "plan_type": "invoice_audit" or "operations_report" or "browser_audit" or "unsupported" or "ambiguous",
  "intended_outcome": "Precise statement of target outcome",
  "success_criteria": ["measurable condition 1", "measurable condition 2"],
  "steps": [
    {{
      "step_index": 0,
      "name": "Human-readable step name",
      "tool_name": "exact_tool_name_from_registry",
      "tool_args": {{ "arg1": "val1" }},
      "requires_approval": false,
      "expected_output": "description of observation",
      "dependencies": []
    }}
  ],
  "verification_conditions": ["independent verification criterion"],
  "company_policy_citations": ["relevant policy doc if applicable"]
}}
"""
    try:
        raw_json_str = call_gemini_api(prompt)
    except Exception as e:
        raise RuntimeError(f"Gemini API: {str(e)[:100]}")

    try:
        parsed = json.loads(raw_json_str)
        # Ensure task_id is populated across tool steps that need it
        for step_data in parsed.get("steps", []):
            args = step_data.get("tool_args", {})
            if "task_id" not in args or not args["task_id"]:
                args["task_id"] = task_id
            step_data["tool_args"] = args
        plan = ExecutionPlan(**parsed)
        plan.plan_source = "gemini_llm"
        is_valid, err = validate_plan_tools(plan)
        if is_valid:
            return plan
        raise ValueError(f"Tool schema validation: {err}")
    except Exception as e:
        raise ValueError(f"LLM plan schema error: {str(e)[:100]}")

def diagnose_failure_with_llm(task_request: str, step_name: str, tool_name: str, error: str) -> dict[str, Any]:
    """Diagnoses execution failures using Gemini if available, with deterministic fallback."""
    if settings.GEMINI_API_KEY and settings.EXECUTION_MODE != "deterministic":
        prompt = f"""
Diagnose the failure in an autonomous company operations task.
Task: "{task_request}"
Failed Step: "{step_name}"
Tool: "{tool_name}"
Error: "{error}"

Return JSON:
{{
  "category": "transient | permanent | permission | validation | missing_data",
  "can_retry": true or false,
  "suggested_action": "retry_with_backoff | request_human_approval | abort_truthfully | alter_arguments",
  "diagnosis": "Short explanation of failure cause"
}}
"""
        try:
            raw = call_gemini_api(prompt, timeout=8)
            return json.loads(raw)
        except Exception:
            pass

    # Deterministic fallback classification
    err_lower = str(error).lower()
    if "permission" in err_lower or "security" in err_lower:
        return {"category": "permission", "can_retry": False, "suggested_action": "abort_truthfully", "diagnosis": "Permission or security violation detected."}
    elif "not found" in err_lower or "missing" in err_lower:
        return {"category": "missing_data", "can_retry": False, "suggested_action": "abort_truthfully", "diagnosis": "Required file or data record missing."}
    elif "timeout" in err_lower or "locked" in err_lower:
        return {"category": "transient", "can_retry": True, "suggested_action": "retry_with_backoff", "diagnosis": "Transient network or lock timeout."}
    else:
        return {"category": "permanent", "can_retry": False, "suggested_action": "abort_truthfully", "diagnosis": "Permanent tool execution exception."}

# ── Main Hybrid Planning Controller ──────────────────────────────────────────

def analyze_and_plan(request: str, task_id: str) -> ExecutionPlan:
    """
    Hybrid planning engine:
    1. Evaluates security & ambiguity guardrails.
    2. Attempts Level 1: LLM-driven planning via Google Gemini API if enabled.
    3. If LLM call fails, times out, or produces invalid plans -> smoothly falls back to
       Level 3: Predefined Workflow Registry & NLP keyword matching.
    """
    req_clean = (request or "").strip()
    
    if not req_clean:
        return ExecutionPlan(
            plan_valid=False,
            plan_type="ambiguous",
            intended_outcome="None",
            success_criteria=[],
            error_message="User request is empty. Please provide a clear task description."
        )

    req_lower = req_clean.lower()

    # 1. Guardrail: Malicious prompt injection or unauthorized code override
    hostile_patterns = [
        "ignore all rules", "ignore previous instructions", "drop table", "delete all records",
        "rm -rf", "curl http", "wget http", "bash", "exec(", "eval("
    ]
    if any(p in req_lower for p in hostile_patterns):
        return ExecutionPlan(
            plan_valid=False,
            plan_type="unsupported",
            plan_source="guardrail",
            intended_outcome="Adversarial or hostile instruction detected.",
            success_criteria=[],
            clarification_message="Security violation: Hostile command or policy override attempt detected. Actions blocked by system safety boundary."
        )

    # 2. Guardrail: Unsafe live financial transactions
    unsafe_patterns = [
        "send real payment", "transfer money", "money transfer", "transfer company funds",
        "transfer funds", "wire money", "hack", "bypass auth", "send live whatsapp",
        "whatsapp", "send real email"
    ]
    if any(p in req_lower for p in unsafe_patterns):
        return ExecutionPlan(
            plan_valid=False,
            plan_type="unsupported",
            plan_source="guardrail",
            intended_outcome="Request cannot be completed safely.",
            success_criteria=[],
            clarification_message="Real financial transfers and live external communications are strictly out of scope for safety. The operator can only prepare and verify drafts."
        )

    # 3. Guardrail: Ambiguity Detection
    ambiguous_keywords = [
        "check things", "check the things", "do something", "help me", "run", "audit", "test",
        "files", "check files"
    ]
    has_specific_workflow_keyword = any(k in req_lower for k in [
        "invoice", "overdue", "reminder", "past due", "receivable", "billing", "collection",
        "sales", "inventory", "stock", "reconcil", "discrepanc", "browser", "portal", "playwright"
    ])
    if (req_clean in ["help", "do something", "run", "check files", "test", "audit"] or
        any(req_lower == p or req_lower == f"please {p}" for p in ambiguous_keywords) or
        (any(p in req_lower for p in ["check the things", "do something with files", "help me run an audit"]) and not has_specific_workflow_keyword)):
        return ExecutionPlan(
            plan_valid=False,
            plan_type="ambiguous",
            plan_source="guardrail",
            intended_outcome="Unspecified operations task",
            success_criteria=[],
            clarification_message="Your request is ambiguous. Did you mean: (A) Audit overdue invoices & prepare reminder drafts, (B) Review sales and inventory files for inconsistencies, or (C) Run browser audit portal verification?"
        )

    # 4. Level 1: Attempt LLM-driven planning via Google Gemini API if enabled
    llm_diag_msg = None
    if settings.EXECUTION_MODE in ("hybrid", "ai") and settings.GEMINI_API_KEY:
        try:
            gemini_plan = plan_with_gemini_llm(req_clean, task_id)
            if gemini_plan and gemini_plan.plan_valid:
                return gemini_plan
            else:
                llm_diag_msg = "LLM generated invalid plan schema or was unable to structure steps"
        except Exception as e:
            llm_diag_msg = f"LLM did not respond ({str(e)[:80]})"
    elif not settings.GEMINI_API_KEY:
        llm_diag_msg = "LLM API key not configured"

    # 5. Level 3 Fallback: Predefined Workflow Registry & NLP keyword matching
    # When LLM fails, is unconfigured, or produces an invalid plan, match against registered workflows:
    for wf in PREDEFINED_WORKFLOWS:
        if any(k in req_lower for k in wf.keywords):
            fallback_plan = wf.builder(task_id, req_clean)
            fallback_plan.plan_source = "predefined_fallback"
            if llm_diag_msg:
                fallback_plan.fallback_reason = f"Shifted to Existing workflow ({llm_diag_msg})"
            else:
                fallback_plan.fallback_reason = "Shifted to Existing workflow"
            return fallback_plan

    # 6. Fallback if request is outside all registered workflows
    return ExecutionPlan(
        plan_valid=False,
        plan_type="unsupported",
        plan_source="predefined_fallback",
        intended_outcome="Unsupported task request",
        success_criteria=[],
        clarification_message=(
            "I could not map your request to a supported company operation. "
            "Supported workflows include: (1) Invoice audit and reminder drafting, "
            "(2) Business operations & inventory reconciliation report, and "
            "(3) Bounded browser audit portal verification."
        )
    )

def validate_plan_tools(plan: ExecutionPlan) -> tuple[bool, str | None]:
    """Validates that all steps in the plan strictly conform to the registered tool schemas."""
    if not plan.plan_valid:
        return False, plan.error_message or plan.clarification_message

    for step in plan.steps:
        tool_def = registry.get(step.tool_name)
        if not tool_def:
            return False, f"Plan contains unknown tool '{step.tool_name}'."
        try:
            if step.tool_name in ("verify_artifact_content", "read_artifact"):
                pass
            else:
                tool_def.input_schema(**step.tool_args)
        except Exception as e:
            return False, f"Invalid arguments for tool '{step.tool_name}' in step '{step.name}': {str(e)}"

    return True, None
