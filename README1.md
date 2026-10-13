# ProofLoop / Company Automation: Comprehensive System Architecture & Deep Interview Guide

> **Author / Project Engineer:** Sparsh Chaurasiya  
> **System Name:** ProofLoop (Autonomous AI Employee for Operations & Finance)  
> **Architecture Pattern:** Hybrid Level 1–3 Deterministic DAG & LLM Orchestrator  
> **Target Audience:** Technical Founders, Staff/Principal Engineers, System Design Interviewers  

---

## 1. Executive Summary & The 60-Second Pitch

### What is ProofLoop?
**ProofLoop** is an autonomous AI employee engineered to execute real-world enterprise back-office workflows—specifically **accounts receivable invoice reconciliation, customer reminder drafting, operational inventory auditing, and bounded internal browser portal verification**.

### The Core Problem in Enterprise AI Automation
Most AI agent frameworks (e.g., standard LangChain, CrewAI, AutoGen agents) suffer from three fatal flaws in corporate environments:
1. **Hallucination in Critical Math:** LLMs cannot reliably perform arithmetic or strict database lookups without drift or rounding errors.
2. **Infinite Loops & High Latency:** Calling an LLM after every single tool execution creates high API latency (10–30s per task), huge token costs, and non-deterministic branching where the agent forgets its goal.
3. **Fragility & Outages:** If the external LLM API experiences rate-limiting (HTTP 429), timeouts, or model deprecation, pure AI agents crash completely, paralyzing company operations.

### The ProofLoop Solution: The Hybrid 3-Level Architecture
ProofLoop implements a **Hybrid Autonomous Architecture**:
* **Level 1 (LLM Intelligence):** Google Gemini 3.8 Flash is invoked **once upfront** to understand the user's natural language request, enforce security guardrails, cite corporate SOPs, and compile a structured Directed Acyclic Graph (DAG) execution plan.
* **Level 2 (Deterministic Execution):** Python's deterministic runtime executes all data querying, calculations, file manipulation, and database operations. **Zero LLM hallucination in math or data retrieval.**
* **Level 3 (Resilient Fallback):** If the LLM is unavailable, times out, or hits API quotas, the system **never crashes**. It automatically transitions to the verified **Predefined Workflow Registry** and explicitly tags the task with:  
  `⚠️ Shifted to Existing workflow`
* **Level 4 (Independent Ground-Truth Verification):** Before any task is reported as "Completed", an isolated verification engine re-reads generated artifacts from disk, re-queries database ground truth, computes cryptographic SHA-256 hashes, and independently confirms compliance.

---

## 2. High-Level Architecture Diagram

```
User Request (Natural Language)
               │
               ▼
   [ Security & Ambiguity Guardrails ] ──── (Hostile / Ambiguous?) ───► Request Clarification / Abort
               │ (Valid Request)
               ▼
 ┌───────────────────────────────────────────────────────────────┐
 │               LEVEL 1: LLM PLANNING ENGINE                   │
 │                (Google Gemini 3.8 Flash)                      │
 │   - Understands intent & extracts parameters                 │
 │   - Maps request to Registered Tool DAG                      │
 │   - Generates Success Criteria & Verification Rules          │
 └───────────────────────────────┬───────────────────────────────┘
                                 │
             ┌───────────────────┴───────────────────┐
             │ LLM Success?                          │ LLM Failed / 429 / Offline?
             ▼                                       ▼
  [ Use Gemini Structured DAG ]          ┌───────────────────────────────────┐
                                         │   LEVEL 3: PREDEFINED WORKFLOW    │
                                         │             REGISTRY              │
                                         │   "Shifted to Existing workflow"  │
                                         │   - WF-INV-001 (Invoices)         │
                                         │   - WF-OPS-002 (Inventory Audit) │
                                         │   - WF-BROWSER-003 (Portal)       │
                                         └─────────────────┬─────────────────┘
                                                           │
             ┌─────────────────────────────────────────────┘
             ▼
 ┌───────────────────────────────────────────────────────────────┐
 │           LEVEL 2: DETERMINISTIC EXECUTION RUNTIME            │
 │                   (Pure Python Engine)                        │
 │                                                               │
 │  Step 1: search_company_policies   (Markdown Vector/Regex)    │
 │  Step 2: query_invoice_records     (SQLite Query Engine)      │
 │  Step 3: audit_invoices            (Deterministic Math)       │
 │  Step 4: [Human-in-the-Loop Gate]  (If >$5,000 or Disputed)   │
 │  Step 5: save_reminder_drafts      (Atomic File Writer)       │
 └───────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
 ┌───────────────────────────────────────────────────────────────┐
 │       LEVEL 4: INDEPENDENT GROUND-TRUTH VERIFIER              │
 │  - Re-opens artifact files directly from disk                 │
 │  - Re-computes sums directly from SQLite ground-truth         │
 │  - Validates SHA-256 hashes & ensures zero hallucinations      │
 └───────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
 ┌───────────────────────────────────────────────────────────────┐
 │       EVIDENCE LEDGER & AUDIT TRAIL (SQLite / UI)             │
 │  - State Machine Terminal State: 'completed'                  │
 │  - Structured Metrics, Artifact Viewer & Live DAG Visualizer  │
 └───────────────────────────────────────────────────────────────┘
```

---

## 3. Data Sources: Where Does the Data Come From?

ProofLoop operates on realistic enterprise data stored in the `./data/` directory:

| Data Source | Location | Format | Contents & Business Purpose |
| :--- | :--- | :--- | :--- |
| **Invoices Database** | `data/invoices.db` | SQLite Database | **Accounts Receivable Records.** Contains customer details, invoice numbers (`INV-2026-001` to `INV-2026-009`), amounts, due dates, and payment statuses (`unpaid`, `paid`, `disputed`, `pending`). |
| **Sales Transactions** | `data/operations/sales_2026_q1.csv` | CSV | **Q1 Enterprise Sales Log.** Contains order IDs (`ORD-101` to `ORD-106`), dates, SKUs, units sold, unit prices, and reported total revenue. Includes intentional anomalies (duplicate `ORD-101`, arithmetic variance in `ORD-105`). |
| **Inventory Stock** | `data/operations/inventory_2026_q1.json` | JSON | **Warehouse Stock Records.** Contains product SKU, starting stock, ending stock, and unit cost. Used for cross-reconciliation with sales to detect inventory shrinkage. |
| **Corporate Policies** | `data/policies/` | Markdown (`.md`) | **Governing Company SOPs:**<br>• `sop_invoice_collection.md` (credit rules, high-value limits, dispute handling).<br>• `sop_inventory_audit.md` (discrepancy thresholds, duplicate checking rules). |
| **System Database** | `data/company_automation.db` | SQLite Database | **System State & Audit Ledger.** Relational storage of tasks, DAG execution steps, approval requests, evidence ledger entries, and artifact hashes. |
| **Output Artifacts** | `data/outputs/` | Markdown, JSON, PNG | **Generated Work Products.** Verified reminder drafts (`.md`, `.json`), business operations reports (`.md`, `.json`), and browser audit screenshots (`.png`). |

---

## 4. Deep Dive: What Each Automated Workflow Does

### Workflow A: Accounts Receivable Audit & Payment Reminder Preparation
1. **Source Data:** `data/invoices.db` (Invoices table) + `data/policies/sop_invoice_collection.md`.
2. **Business Goal:** Audit outstanding customer debt against the company's reference date (`2026-10-10`), identify past-due accounts, filter out disputed invoices, and draft personalized collection notices.
3. **Execution Steps:**
   * **Step 1 (`search_company_policies`):** Searches company SOPs for overdue rules and threshold limits. Cites `sop_invoice_collection.md`.
   * **Step 2 (`query_invoice_records`):** Queries SQLite database for active invoice rows.
   * **Step 3 (`audit_invoices`):** Deterministically categorizes each invoice:
     - Evaluates whether `due_date < 2026-10-10` and `status == 'unpaid'`.
     - Flags `INV-2026-006` (`Umbrella Pharmaceuticals`, $6,400) as **Disputed** (halts automated emailing to prevent customer friction).
     - Flags `INV-2026-002` (`Globex Industries`, $8,200) as **High-Value** (exceeds $5,000 policy threshold, requiring human review).
     - Calculates total actionable overdue sum deterministically ($18,250.00).
   * **Step 4 (`save_reminder_drafts`):** Formats verified reminder letters and writes both structured JSON and formatted Markdown files to `data/outputs/`.
   * **Step 5 (`verify_artifact_content`):** Re-opens the generated file from disk, confirms every invoice is genuinely overdue in SQLite, checks that total sums match, and registers the SHA-256 hash.

### Workflow B: Business Operations & Inventory Reconciliation
1. **Source Data:** `data/operations/sales_2026_q1.csv` + `data/operations/inventory_2026_q1.json` + `data/policies/sop_inventory_audit.md`.
2. **Business Goal:** Cross-reconcile reported sales revenue against transactional line items and inventory stock changes to detect fraud, bookkeeping errors, and shrinkage.
3. **Execution Steps:**
   * **Step 1 (`search_company_policies`):** Retrieves `sop_inventory_audit.md` integrity criteria.
   * **Step 2 (`calculate_operations_summary`):**
     - Parses CSV and JSON deterministically.
     - Detects **Duplicate Order ID:** Flags `ORD-101` as duplicate.
     - Detects **Revenue Calculation Variance:** Line item `ORD-105` claims $1,100.00 revenue, but `8 units * $120.00 = $960.00` (Variance: $140.00).
     - Computes Closing Inventory Valuation ($19,110.00).
   * **Step 3 (`save_operations_report`):** Generates executive Markdown and JSON audit reports.
   * **Step 4 (`verify_artifact_content`):** Independently re-computes all totals from raw CSV/JSON files and verifies matching figures.

### Workflow C: Bounded Browser Internal Portal Verification
1. **Source Data / Portal:** Local authorized test portal (`http://127.0.0.1:8000/test-portal`).
2. **Business Goal:** Verify internal operations portal availability, submit automated batch audit forms, and record verifiable visual evidence.
3. **Execution Steps:**
   * **Step 1 (`browser_audit_portal`):**
     - Enforces strict domain whitelist (only `127.0.0.1` and `localhost` allowed; external navigation blocked for safety).
     - Runs Playwright in an **isolated thread pool** (preventing FastAPI event loop collisions).
     - Automates form fill, submits batch ID, verifies confirmation badge in the DOM, and captures a high-resolution screenshot PNG in `data/outputs/`.

---

## 5. The 3-Level Hybrid Architecture & Fallback Mechanism

One of the most important technical innovations in ProofLoop is the **Hybrid Planning Engine (`backend/engine/planner.py`)**.

### Why NOT call the LLM after each tool execution?
* **Common Interview Trap:** *"Why didn't you use an iterative ReAct agent loop (LLM $\to$ Tool $\to$ LLM $\to$ Tool)?"*
* **The Engineering Answer:** In corporate financial and operational workflows, **state transitions must be auditable and predictable**. Calling an LLM after every tool introduces:
  1. **Accumulated Drift / Hallucination:** Small stochastic variations cause the LLM to skip verification or re-run tools unnecessarily.
  2. **High Latency & Token Burn:** A 5-step task requires 6 LLM roundtrips (~20–40 seconds). ProofLoop completes in **1.8 seconds**.
  3. **Non-deterministic Arithmetic:** Asking an LLM to "read the tool output and add up the numbers" leads to mathematical errors. In ProofLoop, Python computes the math deterministically.

### How ProofLoop Solves This: Plan Upfront, Execute in Python
1. **Level 1 (LLM):** Gemini 3.8 Flash compiles the user request into a strictly typed Pydantic DAG (`ExecutionPlan`) with tool names, parameters, and expected dependencies.
2. **Level 2 (Python):** Python's state machine executes the DAG nodes deterministically.
3. **Level 3 (Fallback):** If the Gemini API returns HTTP 429 (quota exceeded), times out, or has an invalid key, the engine catches the exception and immediately invokes the matching **Predefined Workflow** (`WF-INV-001`, `WF-OPS-002`, `WF-BROWSER-003`).

```python
# From backend/engine/planner.py
try:
    gemini_plan = plan_with_gemini_llm(req_clean, task_id)
    if gemini_plan and gemini_plan.plan_valid:
        return gemini_plan
except Exception as e:
    llm_diag_msg = f"LLM did not respond ({str(e)[:80]})"

# Automatic Shift to Existing Workflow
for wf in PREDEFINED_WORKFLOWS:
    if any(k in req_lower for k in wf.keywords):
        fallback_plan = wf.builder(task_id, req_clean)
        fallback_plan.plan_source = "predefined_fallback"
        fallback_plan.fallback_reason = f"Shifted to Existing workflow ({llm_diag_msg})"
        return fallback_plan
```

---

## 6. Security & Safety Boundaries

Enterprise autonomous agents require defense-in-depth security:

1. **Path Traversal Protection (`resolve_safe_path`):**
   - Resolves all file paths to absolute paths and validates that they reside strictly within allowed roots (`./data`, `./data/outputs`, `./data/policies`, `./data/operations`).
   - Prevents `../../etc/passwd` or `C:\Windows\System32` escape attacks with strict `PermissionError` enforcement.
2. **Adversarial Prompt Injection Defense:**
   - Detects jailbreaks (`"ignore previous instructions"`, `"drop table"`, `"rm -rf"`, `"eval("`).
   - Rejects malicious requests at the planning layer and transitions the task to `failed` with safety notices.
3. **Financial Protection Safeguards:**
   - Detects unauthorized live transactions (`"wire real money"`, `"send live payment"`, `"transfer company funds"`).
   - The system is architecturally restricted to **auditing and preparing drafts**; live execution of funds is strictly prohibited.
4. **Browser Bounding:**
   - The Playwright tool enforces domain whitelist checks (`ALLOWED_BROWSER_DOMAINS = ["127.0.0.1", "localhost"]`).
   - Blocks navigation to external, unauthorized internet domains.

---

## 7. State Machine & Task Lifecycle

ProofLoop implements an explicit 9-state finite state machine (`backend/engine/state_machine.py`):

```
       [ PENDING ]
            │
            ▼
       [ PLANNING ] ──────► [ FAILED ] (Invalid/Ambiguous)
            │
            ▼
       [ RUNNING ] ◄─────────────────────────┐
            │                                │ (Approve)
            ├──► [ WAITING_FOR_APPROVAL ] ───┘
            │          │ (Reject)
            │          ▼
            │     [ FAILED ]
            ▼
      [ VERIFYING ]
            │
            ├──► [ COMPLETED ] (Verification Passed)
            └──► [ PARTIALLY_COMPLETED / FAILED ] (Verification Mismatch)
```

* **Terminal States:** `completed`, `failed`, `cancelled`, `partially_completed`. Once reached, no further transitions are allowed (enforced by unit tests).
* **Saved Output Reuse:** If a task restarts, already completed steps whose upstream dependencies haven't changed are reused instead of re-executed.

---

## 8. Frontend User Experience & Telemetry

The frontend (`React 18` + `Vite` + Vanilla CSS design tokens) was specifically designed to give human operators complete visibility and control:

1. **"Shifted to Existing workflow" Banner:**
   - When Gemini LLM is offline or rate-limited, the UI renders a prominent amber alert:
     > **⚠️ Shifted to Existing workflow**  
     > *LLM did not respond (HTTP 429 Quota Exceeded); ProofLoop automatically shifted to verified deterministic workflow.*
2. **LLM Understanding Card:**
   - Displays intended outcome, success criteria with checkmarks, cited SOP documents, and verification rules.
3. **Execution Node Pipeline DAG:**
   - Connected visual flow: `[ Node 1 ] ➔ [ Node 2 ] ➔ [ Node 3 ] ➔ [ Node 4 ] ➔ [ Node 5 ]`.
   - Node cards pulse when `running`, show checkmarks when `completed`, and highlight when `waiting_approval`.
4. **Every Node Result Displayed:**
   - **Financial Stats:** Overdue invoice counts, total dollar amount, disputed accounts.
   - **Operations Stats:** Reported revenue vs calculated revenue, revenue variance, duplicate order tags.
   - **Interactive Table Preview:** Displays top rows retrieved from the database.
   - **Live Screenshot Previews:** Thumbnail view of browser verification screenshots.
   - **Raw JSON Inspector:** Click to inspect full JSON output payloads.
5. **Human-in-the-Loop Modal:**
   - Approve / Reject buttons with customizable operator audit notes.

---

## 9. Top 15 Technical Interview Questions & Answers

### Q1: Why did you build a custom engine instead of using LangChain or CrewAI?
**Answer:** Frameworks like LangChain and CrewAI are generic wrappers designed for chatbots and open-ended exploration. In enterprise finance and operations, they suffer from **non-deterministic loops, high API costs, hallucinated calculations, and fragile error recovery**. ProofLoop uses an explicit Directed Acyclic Graph (DAG) state machine where the LLM plans the structure once, but execution, math, and database queries are handled deterministically in Python.

### Q2: Why don't you invoke the LLM after every tool step?
**Answer:** Invoking the LLM after every step introduces compounding latency (15–30 seconds per task) and creates non-deterministic drift. If step 2 outputs 10 invoice rows, having an LLM parse and sum them often introduces arithmetic hallucinations. In ProofLoop, step 3 is executed by a deterministic Python tool that calculates the exact sum (`$18,250.00`) with $0.00 error. The LLM is only invoked upfront for semantic planning and as a secondary diagnostic classifier if an unhandled failure occurs.

### Q3: How do you guarantee zero hallucinations in financial math?
**Answer:** By strictly separating **semantic planning** from **arithmetic calculation**. The LLM never computes financial numbers; it only specifies which tool to execute (e.g. `audit_invoices` with `reference_date="2026-10-10"`). The tool executes pure Python arithmetic (`sum(inv.amount for inv in overdue)`). Furthermore, Level 4 independent verification re-queries the SQLite database and compares computed sums against database ground truth.

### Q4: What happens if the Gemini LLM API goes down or hits a 429 quota limit?
**Answer:** ProofLoop implements a Level 3 **Predefined Workflow Registry**. If the LLM throws a 429, times out, or has an unconfigured API key, the planner catches the exception, maps the request to a registered workflow (`WF-INV-001`, `WF-OPS-002`, `WF-BROWSER-003`), and sets:
`fallback_reason = "Shifted to Existing workflow (LLM error: 429 Quota Exceeded)"`.
The task executes to completion with 100% reliability, and the UI displays the `Shifted to Existing workflow` banner.

### Q5: How do you prevent path traversal attacks in file operations?
**Answer:** We implemented `resolve_safe_path()` in `backend/config.py`. It converts any user-supplied or LLM-supplied path to an absolute path, resolves symlinks, and checks `path.parents` against an allowed roots whitelist (`./data`, `./data/outputs`, `./data/policies`, `./data/operations`). If any path attempts to escape (e.g., `../../etc/passwd`), a `PermissionError` is immediately raised before any OS file descriptor is opened.

### Q6: How does independent verification differ from LLM self-reflection?
**Answer:** Standard LLM "self-reflection" simply asks the same model: *"Did you do a good job?"* That creates confirmation bias and repeats hallucinations. ProofLoop's Level 4 verification is **programmatic and external**:
1. It re-reads the written artifact file from disk.
2. It re-queries the SQLite database ground truth.
3. It re-computes arithmetic sums in Python and checks for exact equality.
4. It calculates the SHA-256 cryptographic hash of the artifact and writes it to an immutable evidence ledger.

### Q7: Explain your DAG dependency resolution and saved output reuse mechanism.
**Answer:** Each step in `ExecutionPlan` specifies an array of `dependencies: list[int]`. In `backend/engine/executor.py`, before a step executes, `is_saved_output_reusable()` verifies whether that step previously completed with valid upstream inputs. If a task is resumed or re-run after human approval, already-completed independent steps are reused without redundant computation.

### Q8: How does the Human-in-the-Loop (HITL) approval gate work?
**Answer:** When `audit_invoices` encounters an invoice with `status == 'disputed'` or an amount exceeding the $5,000 threshold defined in `sop_invoice_collection.md`, the plan step sets `requires_approval = True`. The state machine pauses execution and enters `waiting_for_approval`. An `ApprovalModel` record is created in SQLite. Execution remains suspended until a human operator sends a `POST /api/tasks/{task_id}/approve` request, at which point the executor resumes the DAG.

### Q9: How did you solve Playwright sync API collisions with FastAPI's event loop?
**Answer:** Playwright's `sync_playwright()` raises an exception if invoked directly on a thread running an asyncio event loop (such as FastAPI). To solve this cleanly without forcing the entire engine to be async, we wrapped the Playwright automation in `concurrent.futures.ThreadPoolExecutor(max_workers=1)`. This runs browser automation in a pure synchronous OS thread completely isolated from asyncio.

### Q10: How is database concurrency and transaction isolation handled?
**Answer:** ProofLoop uses SQLAlchemy with SQLite in WAL mode (`Write-Ahead Logging`). Thread-safe sessions are managed through `SessionLocal()` scoped per request/operation with explicit `try / finally db.close()` blocks. State transitions are atomic: `transition_task()` updates task status, logs state change events, and commits in a single transaction.

### Q11: What testing strategy ensures the system doesn't break?
**Answer:** ProofLoop maintains an automated test suite across 7 test files:
* **Unit Tests (`test_unit_validation.py`, `test_unit_calculations.py`):** Tests path traversal, mathematical totals, reference date logic, state machine legal transitions, and terminal state enforcement.
* **Failure Injection (`test_failure_injection.py`):** Injects missing files, prompt injection strings, unauthorized browser destinations, and artifact hash tampering.
* **Integration Tests (`test_integration_workflows.py`):** End-to-end tests for all workflows and human approval pauses/resumptions.
* **Generalization Tests (`test_generalization.py`):** Tests 7 varied phrasing permutations to ensure the planner generalizes across different user prompts.
* **Hybrid Execution (`test_hybrid_execution.py`):** Tests tool validation, LLM fallback behavior, and failure diagnosis classifiers.

### Q12: How are tasks and artifacts indexed for observability?
**Answer:** Every execution generates records in:
1. `TaskModel` (metadata, normalized goal, plan JSON).
2. `TaskStepModel` (status, tool name, arguments, result JSON, attempt count, duration).
3. `EvidenceModel` (immutable audit trail of tool input/output summaries, references, and verification status).
4. `ArtifactModel` (filename, file path, artifact type, content SHA-256 hash).

### Q13: Why did you choose Google Gemini 3.8 Flash?
**Answer:** Gemini 3.8 Flash provides sub-second time-to-first-token, native JSON schema mode (`responseMimeType: "application/json"`), high context limits, and low cost per token. Furthermore, our planner includes fallback logic: if `gemini-3.8-flash` is unavailable, it automatically falls back to `gemini-flash-latest` or `gemini-2.5-pro`.

### Q14: How does ProofLoop handle ambiguous or hostile requests?
**Answer:** Before calling the LLM or executing workflows, the planner evaluates guardrails:
* **Hostile/Adversarial:** Prompts like `"ignore rules"`, `"drop tables"`, or `"eval()"` are flagged by `guardrail` and aborted with safety violation notices.
* **Ambiguous:** Prompts like `"help me"`, `"check files"`, or `"do something"` trigger `plan_type = "ambiguous"` and prompt the user with 3 concrete multiple-choice options (`A`, `B`, or `C`).

### Q15: What are the primary KPIs and benchmarks achieved?
**Answer:** In benchmark evaluations (`evaluation/run_eval.py`):
* **Task Completion Rate:** 100% (all supported workflows executed to terminal state).
* **Independent Verification Pass Rate:** 100% (zero artifact discrepancies).
* **Deterministic Math Error:** 0.00% (exact match against database totals).
* **Average Execution Latency:** <2.5 seconds per workflow.
* **Resilience Under Outage:** 100% uptime through Level 3 workflow shifting.

---

## 10. How to Run the Project Locally

### Prerequisites
* Windows 10/11, macOS, or Linux
* Python 3.10+ (tested on Python 3.13)
* Node.js v18+ and npm

### 1. Backend Server Setup
```bash
# Install Python dependencies
pip install -r requirements.txt
playwright install chromium

# Launch the FastAPI backend (Port 8000)
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Dashboard Setup
```bash
# Navigate to frontend and install dependencies
cd frontend
npm install

# Start the Vite development server (Port 5173)
npm run dev -- --host
```

### 3. Run Live Demonstration Script
```bash
# In the project root:
python run_demo.py
```

### 4. Run Automated Test Suite
```bash
# Run all tests with pytest
python -m pytest -v
```

### 5. Access Endpoints
* **Web UI Dashboard:** [http://localhost:5173/](http://localhost:5173/)
* **Backend API Health:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
* **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
