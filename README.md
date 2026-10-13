# ProofLoop: Hybrid Autonomous AI Operations Operator
## Evidence-Driven Autonomous Task Worker & Financial Reconciliation Engine

ProofLoop is an evidence-driven, hybrid autonomous AI operator engineered to convert business requests into verifiable, audit-trailed company work. It initially focuses on invoice audit, purchase-order reconciliation, business operations reporting, and bounded browser verification.

Its central operational law is simple: **no evidence, no success claim**. After executing operations, ProofLoop reads generated records and artifacts back from the database or filesystem and independently verifies them against ground truth source records. It does not treat a successful tool HTTP return code or an LLM's statement as proof that a task succeeded.

Crucially, ProofLoop does not depend exclusively on an LLM. It implements a **three-tier hybrid architecture** combining Google Gemini LLM reasoning with deterministic rule-based execution and a manually maintained fallback workflow registry.

---

## 1. Project Objective & Core Capabilities

ProofLoop completes real operations tasks end-to-end through a bounded execution loop:
$$\text{Goal} \longrightarrow \text{Understand} \longrightarrow \text{Plan} \longrightarrow \text{Execute} \longrightarrow \text{Observe} \longrightarrow \text{Adapt} \longrightarrow \text{Verify} \longrightarrow \text{Complete}$$

- **Parses natural-language requests into structured tasks:** Identifies task intent, entities, dates, constraints, and success conditions.
- **Hybrid Planning with Gemini API & Fallbacks:** Combines LLM cognitive planning (via Google Gemini) with deterministic NLP and predefined workflow fallbacks when the LLM is unconfigured, times out, or produces invalid output.
- **Discovers and extracts company data safely:** Safe file operations and SQL access with path-traversal prevention (`resolve_safe_path`).
- **Maintains database and ledger integrity:** Enforces unique constraints, parameterized read-only queries, and idempotency keys to prevent duplicate writes.
- **Human-in-the-Loop approval gates:** Automatically pauses and requires operator authorization for high-value actions (invoices > $5,000 / ₹50,000) or disputed customer accounts.
- **Recovers from timeouts and failures safely:** Inspects database state before retrying to prevent duplicate side effects.
- **Reuses valid saved outputs:** Intelligently reuses previously computed step outputs if arguments, upstream dependencies, and data freshness requirements remain satisfied.
- **Independently verifies results:** Re-opens saved artifacts from disk and reconciles numbers against SQLite databases before marking tasks `completed`.
- **Maintains tamper-evident audit ledger:** Persists immutable step-by-step evidence with input summaries, execution status, tool outputs, and source citations.
- **React + Vite Dashboard:** Modern dark-mode interface with live task timelines, approval actions, evidence viewer, and artifact inspection modals.

---

## 2. Three-Tier Hybrid Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │          Natural-Language User Request       │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 1: LLM-Driven Reasoning (Google Gemini API)                                      │
│ • Understands ambiguous requests & extracts constraints                                │
│ • Generates structured JSON execution plans using registered tools                     │
│ • Diagnoses unexpected/complex failures and proposes revised recovery steps           │
└──────────────────────────────────────┬─────────────────────────────────────────────────┘
                                       │
                      LLM Call Fails / │ Unusable Plan /
                         Timeout (12s) │ No API Key
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 3: Predefined Fallback Workflow Registry & NLP Classifier                         │
│ • Keyword & semantic intent mapping against registered workflows                      │
│ • Loads typed, pre-authored DAGs (WF-INV-001, WF-OPS-002, WF-BROWSER-003)             │
│ • Validates inputs, dependencies, permissions, and verification criteria               │
│ • Rejects unsupported/malicious requests truthfully without guessing                   │
└──────────────────────────────────────┬─────────────────────────────────────────────────┘
                                       │
                                       ▼ (Validated Execution Plan)
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 2: Deterministic Rule-Based Execution & Recovery Engine                          │
│ • Plan schema validation & strict tool argument checks                                 │
│ • Dependency cycle detection & step readiness ordering                                 │
│ • Saved-Output Reuse Check: Reuses cached outputs if inputs & dependencies are fresh   │
│ • Error Classification (transient, permanent, permission, missing_data)                │
│ • Bounded Exponential Backoff Retries (up to 3 attempts with jitter)                   │
│ • Authorization & Approval Policy Enforcement (> $5,000 threshold or disputed)         │
│ • Independent Read-Back Verification (asserts artifacts match database records)        │
│ • SQLite Evidence Ledger & State Machine Persistence (WAL mode)                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Level 1: LLM-Driven Planning & Reasoning (Google Gemini)
When configured with `GEMINI_API_KEY` (and `EXECUTION_MODE=hybrid` or `ai`):
- Uses Google Gemini (`gemini-1.5-flash` or configured model) with structured JSON generation.
- Disambiguates complex user intent, identifies parameters, and extracts entities (vendors, dates, currencies).
- Formulates multi-step execution plans selecting among explicitly registered tools.
- Diagnoses runtime failures (`diagnose_failure_with_llm`) and suggests adaptive recovery actions.
- **Safety Boundary:** The LLM cannot execute arbitrary code, invent un-registered tools, override security boundaries, or bypass schema validation.

### Level 2: Rule-Based Execution & Recovery (Python Engine)
Python handles all predictable operations deterministically without relying on the LLM:
- **Plan & Argument Validation:** Validates plans against Pydantic schemas and ToolRegistry signatures.
- **Dependency Ordering & Cycle Detection:** Executes dependency-ready steps and sequences prerequisites.
- **Error Classification:** Classifies errors using exception types and structured return codes into `transient`, `permanent`, `permission`, and `missing_data`.
- **Bounded Backoff Retries:** Automatically retries transient errors with bounded backoff. Permanently fatal or permission errors halt immediately.
- **Idempotency & State Tracking:** Checks database state before retrying write operations to guarantee at-most-once side effects.
- **Saved-Output Freshness & Reuse:** Validates cached outputs to prevent redundant computation after replanning.
- **Independent Verification:** Deterministically computes totals and checks artifact contents against source records.

### Level 3: Manually Configured Fallback Workflows
Maintains a registry of validated, pre-authored workflows in Python (`PREDEFINED_WORKFLOWS`):

| Workflow ID | Name | Task Type | Key Steps & Tools | Verification Method |
|---|---|---|---|---|
| **WF-INV-001** | Invoice Audit & Reminder Drafts | `invoice_audit` | `search_company_policies` → `query_invoice_records` → `audit_invoices` → `save_reminder_drafts` → `verify_artifact_content` | Re-opens draft files, recalculates customer balances against SQLite, confirms zero disputed/paid accounts included. |
| **WF-OPS-002** | Operations & Inventory Audit | `operations_report` | `search_company_policies` → `calculate_operations_summary` → `save_operations_report` → `verify_artifact_content` | Verifies required report sections (Executive Summary, Reconciliation, Discrepancies), asserts calculation match. |
| **WF-BROWSER-003**| Bounded Browser Portal Audit | `browser_audit_portal` | `browser_audit_portal` | Confirms target host is localhost/127.0.0.1, fills batch verification, asserts DOM confirmation badge, captures screenshot. |

A predefined workflow is activated **only** when its registered intent and keywords match the request. If an unsupported request is received and no matching workflow exists, the system reports `blocked` or requests clarification rather than fabricating a workflow.

---

## 3. LLM Failure and Fallback Policy

The system explicitly distinguishes between LLM service failures, invalid LLM plans, and tool execution failures:

### When the LLM Fails During Planning
1. Attempts the Gemini API call with a strict timeout (12 seconds) and retry limits.
2. Validates the returned JSON plan against `ExecutionPlan` and registered tool schemas.
3. If the LLM call times out, returns HTTP 429/500, or produces an invalid plan schema:
   - Records the LLM failure reason in task metadata.
   - Activates **Level 3 Predefined Workflow Registry** using deterministic keyword and entity matching.
   - If a matching workflow is found (e.g. `WF-INV-001`), loads and validates it.
   - If the request is genuinely ambiguous, transitions to `awaiting_clarification` and asks the user.
   - If the request is unsupported or malicious, transitions to `blocked` with a safety notice.

### When a Tool Fails During Execution
1. Captures the exception and persists it in the step record and evidence ledger.
2. Classifies the failure:
   - **Permission / Security Violations:** Halts immediately.
   - **Missing Files / Missing Data:** Halts immediately with clear diagnostic explanation.
   - **Transient Timeouts / DB Locks:** Retries up to 3 times with exponential backoff.
3. If the failure is complex, requests a diagnosis from Gemini (`diagnose_failure_with_llm`).
4. If Gemini is unavailable, applies deterministic error classification rules.
5. If recovery is not possible, halts safely and marks the task `failed`.

### When the LLM Fails During Diagnosis or Replanning
The system avoids infinite LLM retry loops. It allows a single bounded diagnosis attempt; if Gemini fails or is unreachable, the system falls back to rule-based classification and terminates execution truthfully.

---

## 4. Complete End-to-End Execution Workflow

1. **Submission:** User enters a natural-language task in the React interface.
2. **Persistence:** FastAPI assigns a unique UUID and inserts initial state into SQLite (`tasks` table).
3. **Context Retrieval:** Loads relevant approved company policies and procedures from `data/policies/`.
4. **Intent Interpretation:** Gemini interprets the request to extract goal, entities, and constraints.
5. **Clarification Check:** If ambiguous, transitions to `awaiting_clarification` and asks the user.
6. **Plan Generation:** Gemini generates a typed execution plan using registered tools.
7. **LLM Fallback:** If Gemini is unreachable or returns an invalid plan, rule-based matching loads a predefined workflow (`WF-INV-001`, `WF-OPS-002`, `WF-BROWSER-003`).
8. **Plan Validation:** Python validates tool schemas, argument types, and step dependencies.
9. **Authorization Check:** Blocks unauthorized paths (`resolve_safe_path`) and flags protected actions.
10. **Dependency Resolution:** Identifies dependency-ready steps.
11. **Output Reuse Check:** Evaluates whether previously executed steps have valid cached outputs.
12. **Tool Execution:** Reuses valid outputs; otherwise executes the tool with parameters.
13. **Result Validation:** Validates output schemas, captures SHA-256 hashes, and records artifacts.
14. **Evidence Logging:** Appends an immutable record to `evidence_entries`.
15. **Failure Handling:** On failure, classifies the error and applies backoff retries if transient.
16. **Diagnostic Reasoning:** For complex errors, queries Gemini for adaptive recovery diagnosis.
17. **Deterministic Fallback:** If Gemini diagnosis is unavailable, applies deterministic recovery rules.
18. **Resumption:** Resumes from the earliest failed step without re-running valid prior steps.
19. **Output Invalidation:** Invalidates only downstream steps whose input dependencies changed.
20. **Final Verification:** Verification engine re-reads generated artifacts and independently validates them against source database records.
21. **Recovery on Verification Failure:** If verification fails, attempts bounded recovery; otherwise halts truthfully.
22. **Evidence Finalization:** Commits verification results and output artifact links.
23. **Completion:** Transitions task to `completed` and notifies the frontend.

---

## 5. Saved-Output Reuse and Dependency Validation

To prevent redundant execution after replanning, Python evaluates whether a previously computed output is reusable:

### Reusability Criteria
For each step, all of the following must hold:
1. `step.status == "completed"` and `step.result_json` is non-empty.
2. Output schema validation passed during the initial run.
3. Saved parameters (`tool_args_json`) match target step arguments exactly.
4. All upstream dependency steps remain in `completed` status.
5. Source data freshness requirements are satisfied (file modification timestamps and DB version matches).
6. Security permissions and authorization conditions remain valid.

If all criteria pass, the system reuses the output without re-executing the tool. If any criterion fails, the step is re-executed, and downstream steps depending on its output are invalidated.

---

## 6. Persistence and Evidence Schema

Persistence uses SQLite configured with Write-Ahead Logging (`WAL`) and foreign-key constraints via SQLAlchemy:

- **`tasks`**: Task ID, original request, normalized goal, status, plan JSON, metadata JSON, error message, timestamps.
- **`task_steps`**: Step ID, task ID, step index, name, tool name, tool args JSON, status, attempt count, result JSON, approval requirements, started/completed timestamps.
- **`evidence_entries`**: Entry ID, task ID, step ID, tool name, input summary, output summary, execution status, error details, source references, output artifact references, verification status, timestamp.
- **`approval_requests`**: Approval ID, task ID, step ID, action description, payload JSON, status (`pending`, `approved`, `rejected`), reviewer notes, timestamps.
- **`artifacts`**: Artifact ID, task ID, filename, file path, artifact type, content hash (SHA-256), verification status (`pending`, `verified`, `failed`), verification details, timestamp.

Large files (reports, JSON datasets, screenshots) are stored in `data/outputs/` with only cryptographic hashes and paths stored in SQLite.

---

## 7. Task Lifecycle States

```
[pending] ──► [understanding] ──► [planning] ──► [validating] ──► [running/executing]
                     │                 │               │                  │
                     ▼                 ▼               ▼                  ▼
          [awaiting_clarification]  [blocked]       [blocked]   [waiting_for_approval]
                                                                          │
                                                                   [approved] ──► [verifying]
                                                                                    │
                                                                       ┌────────────┴────────────┐
                                                                       ▼                         ▼
                                                                  [completed]                 [failed]
```

- **`pending`**: Task created and queued.
- **`understanding`**: Request is being parsed for intent and entities.
- **`planning`**: Gemini or Predefined Workflow Registry is assembling the step DAG.
- **`validating`**: Plan schema and tool arguments are undergoing deterministic validation.
- **`running` / `executing`**: Steps are actively executing in dependency order.
- **`waiting_for_approval`**: Paused pending operator authorization (invoices > $5,000 or disputed).
- **`awaiting_clarification`**: Request is ambiguous; system awaits user input.
- **`blocked`**: Request violates safety policy or requires unsupported external actions.
- **`verifying`**: All steps executed; independent read-back verification is underway.
- **`completed`**: All steps succeeded and all independent verification checks passed.
- **`failed`**: Step failed permanently or verification failed after recovery attempts exhausted.
- **`cancelled`**: Terminated by user request.

---

## 8. Independent Verification Requirements

Verification evaluates physical outputs on disk against ground-truth source data:

### Invoice Audit & Reminder Verification
- Artifact files exist in `data/outputs/` and are non-empty.
- Draft customer IDs and invoice numbers match records in `invoices.db`.
- Calculated amounts match database values to within $0.01.
- No invoices marked `paid`, `cancelled`, or `disputed` are included in reminder drafts.
- Cryptographic SHA-256 hashes match artifact metadata.

### Operations & Inventory Report Verification
- Report markdown exists and contains required sections: Executive Summary, Inventory Reconciliation, Discrepancies, and Limitations.
- Calculated revenue ($11,010.00) matches deterministic recomputation from `sales_2026_q1.csv`.
- Discrepancy list correctly isolates duplicate order `ORD-101`, revenue variance in `ORD-105` ($140.00), and inventory deficit in `SKU-DELTA` (-2 units).

---

## 9. Test Suite & Verification Results (37 / 37 Tests Passing)

The project includes an automated test suite in `tests/`:

```bash
python -m pytest tests/ -v
```

### Test Coverage Summary:
- **`test_hybrid_execution.py` (4 tests):** Predefined workflow registry validation, hybrid fallback when LLM is unconfigured, failure diagnosis classification, saved-output reuse and dependency invalidation.
- **`test_unit_validation.py` (10 tests):** Path sandboxing (`resolve_safe_path`), empty/unsupported request rejection, ambiguous request handling, plan validation, state machine legal transitions, terminal state enforcement.
- **`test_unit_calculations.py` (2 tests):** Deterministic sales revenue calculations, inventory shrinkage variance, invoice overdue math.
- **`test_integration_workflows.py` (5 tests):** Full Workflow A end-to-end, full Workflow B end-to-end, human approval pause/resume, approval rejection, task cancellation.
- **`test_failure_injection.py` (5 tests):** Missing input files, unauthorized browser destination blocking, independent verification failure simulation, prompt injection guardrails, malformed request handling.
- **`test_generalization.py` (9 tests):** Phrasing generalization across 4 invoice variants, 3 operations variants, ambiguous phrasing handling, unsafe request blocking.
- **`test_browser_automation.py` (2 tests):** Direct Playwright test portal interaction, browser workflow state machine execution.

**Result: 37 passed in 6.82 seconds (100% pass rate).**

---

## 10. Quickstart Commands

```bash
# 1. Install Dependencies
python -m pip install -r requirements.txt
npm --prefix frontend install

# 2. Seed Database & Test Datasets
python -m backend.database.init_db

# 3. Run Automated Tests
python -m pytest tests/ -v

# 4. Run Benchmark Evaluation Suite
python -m evaluation.run_eval

# 5. Start Backend API (Port 8000)
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

# 6. Start Frontend Dashboard (Port 5173)
npm --prefix frontend run dev
```

- **Frontend Dashboard:** `http://localhost:5173`
- **Interactive API Documentation:** `http://127.0.0.1:8000/docs`
- **Authorized Test Portal:** `http://127.0.0.1:8000/test-portal`
