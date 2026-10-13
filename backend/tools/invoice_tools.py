import sqlite3
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
from backend.config import settings
from backend.tools.registry import ToolResult, ToolDefinition, registry

# 1. Query Invoice Records
class QueryInvoicesInput(BaseModel):
    status_filter: str | None = Field(default=None, description="Optional filter by status (unpaid, paid, etc.)")
    limit: int = Field(default=100, description="Max records to return")

class QueryInvoicesOutput(BaseModel):
    records: list[dict]
    total_count: int

def handle_query_invoices(args: QueryInvoicesInput) -> ToolResult:
    db_path = settings.INVOICES_DB_PATH
    if not db_path.exists():
        return ToolResult(
            success=False,
            error=f"Invoice database not found at '{db_path}'.",
            evidence_summary="Database connection failed: invoices.db does not exist."
        )

    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if args.status_filter:
            cur.execute(
                "SELECT id, customer_id, customer_name, customer_email, issue_date, due_date, amount, currency, status, notes FROM invoices WHERE status = ? LIMIT ?",
                (args.status_filter, args.limit)
            )
        else:
            cur.execute(
                "SELECT id, customer_id, customer_name, customer_email, issue_date, due_date, amount, currency, status, notes FROM invoices LIMIT ?",
                (args.limit,)
            )

        rows = cur.fetchall()
        records = [dict(r) for r in rows]
        conn.close()

        return ToolResult(
            success=True,
            data={"records": records, "total_count": len(records)},
            evidence_summary=f"Queried {len(records)} invoice records from invoices.db (filter='{args.status_filter or 'none'}').",
            source_references=["sqlite:invoices.db"]
        )
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Invoice query failed: {str(e)}",
            evidence_summary=f"Database query error: {str(e)}"
        )

# 2. Audit Invoices
class AuditInvoicesInput(BaseModel):
    reference_date: str = Field(default=settings.REFERENCE_DATE, description="Reference date for overdue evaluation (YYYY-MM-DD)")

class AuditInvoicesOutput(BaseModel):
    summary: dict
    overdue_invoices: list[dict]
    review_required: list[dict]

def handle_audit_invoices(args: AuditInvoicesInput) -> ToolResult:
    # First fetch all invoice records
    query_res = handle_query_invoices(QueryInvoicesInput(limit=500))
    if not query_res.success:
        return query_res

    records = query_res.data["records"]
    ref_date_str = args.reference_date

    try:
        ref_dt = datetime.strptime(ref_date_str, "%Y-%m-%d").date()
    except ValueError:
        return ToolResult(
            success=False,
            error=f"Invalid reference date format '{ref_date_str}'. Expected YYYY-MM-DD.",
            evidence_summary="Date validation error: malformed reference_date."
        )

    overdue_unpaid = []
    paid_records = []
    pending_records = []
    disputed_records = []
    cancelled_records = []
    invalid_records = []
    needs_approval_high_value = []

    total_overdue_amount = 0.0

    for inv in records:
        # Schema validation
        inv_id = inv.get("id") or ""
        cust_id = inv.get("customer_id") or ""
        amount = inv.get("amount")
        status = inv.get("status") or "unknown"
        due_date_str = inv.get("due_date") or ""

        # Validate basic record integrity
        if not cust_id or amount is None or amount <= 0:
            invalid_records.append({
                "invoice": inv,
                "reason": "Missing customer identifier or non-positive amount"
            })
            continue

        try:
            due_dt = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            invalid_records.append({
                "invoice": inv,
                "reason": f"Malformed due_date '{due_date_str}'"
            })
            continue

        # Categorize by status and due date
        if status == "disputed":
            disputed_records.append({
                "invoice": inv,
                "reason": "Invoice disputed by customer; legal/human review required"
            })
        elif status == "cancelled":
            cancelled_records.append(inv)
        elif status == "paid":
            paid_records.append(inv)
        elif status == "unpaid":
            if due_dt < ref_dt:
                overdue_unpaid.append(inv)
                total_overdue_amount += amount
                if amount > 5000.0:
                    needs_approval_high_value.append({
                        "invoice": inv,
                        "reason": f"Amount ${amount:,.2f} exceeds $5,000 SOP approval threshold"
                    })
            else:
                pending_records.append(inv)
        elif status == "pending":
            pending_records.append(inv)
        else:
            invalid_records.append({
                "invoice": inv,
                "reason": f"Unrecognized invoice status '{status}'"
            })

    audit_summary = {
        "reference_date": ref_date_str,
        "total_audited": len(records),
        "overdue_unpaid_count": len(overdue_unpaid),
        "total_overdue_amount": round(total_overdue_amount, 2),
        "paid_count": len(paid_records),
        "pending_count": len(pending_records),
        "disputed_count": len(disputed_records),
        "cancelled_count": len(cancelled_records),
        "invalid_count": len(invalid_records),
        "high_value_approval_count": len(needs_approval_high_value)
    }

    return ToolResult(
        success=True,
        data={
            "summary": audit_summary,
            "overdue_invoices": overdue_unpaid,
            "review_required": disputed_records + invalid_records + needs_approval_high_value
        },
        evidence_summary=(
            f"Audited {len(records)} invoices as of {ref_date_str}: "
            f"{len(overdue_unpaid)} overdue unpaid (${total_overdue_amount:,.2f}), "
            f"{len(disputed_records)} disputed, {len(invalid_records)} invalid, "
            f"{len(needs_approval_high_value)} requiring supervisor authorization."
        ),
        source_references=["sqlite:invoices.db", "policy:sop_invoice_collection.md"]
    )

# 3. Save Reminder Drafts
class SaveReminderDraftsInput(BaseModel):
    task_id: str = Field(default="", description="Associated task ID")
    reference_date: str = Field(default=settings.REFERENCE_DATE)

class SaveReminderDraftsOutput(BaseModel):
    drafts_count: int
    output_files: list[str]
    sha256: str

def handle_save_reminder_drafts(args: SaveReminderDraftsInput) -> ToolResult:
    audit_res = handle_audit_invoices(AuditInvoicesInput(reference_date=args.reference_date))
    if not audit_res.success:
        return audit_res

    overdue_invoices = audit_res.data["overdue_invoices"]
    if not overdue_invoices:
        return ToolResult(
            success=True,
            data={"drafts_count": 0, "output_files": [], "sha256": ""},
            evidence_summary="No overdue invoices found; 0 reminder drafts created."
        )

    drafts = []
    for inv in overdue_invoices:
        draft = {
            "invoice_id": inv["id"],
            "customer_id": inv["customer_id"],
            "customer_name": inv["customer_name"],
            "recipient_email": inv["customer_email"],
            "amount_due": inv["amount"],
            "currency": inv["currency"],
            "due_date": inv["due_date"],
            "days_overdue": (datetime.strptime(args.reference_date, "%Y-%m-%d").date() - datetime.strptime(inv["due_date"], "%Y-%m-%d").date()).days,
            "requires_approval": inv["amount"] > 5000.0,
            "email_subject": f"Friendly Reminder: Outstanding Invoice {inv['id']} for {inv['customer_name']}",
            "email_body": (
                f"Dear {inv['customer_name']} Accounts Team,\n\n"
                f"We hope this note finds you well. Our records indicate that invoice {inv['id']} "
                f"for the amount of {inv['currency']} {inv['amount']:,.2f}, issued on {inv['issue_date']}, "
                f"was due on {inv['due_date']}.\n\n"
                f"If payment has already been initiated, please accept our thanks and disregard this reminder. "
                f"Otherwise, please remit payment at your earliest convenience.\n\n"
                f"Best regards,\nAccounts Receivable Operations"
            )
        }
        drafts.append(draft)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_filename = f"reminder_drafts_{args.task_id[:8]}_{timestamp}.json"
    md_filename = f"reminder_drafts_{args.task_id[:8]}_{timestamp}.md"

    json_path = settings.OUTPUT_DIR / json_filename
    md_path = settings.OUTPUT_DIR / md_filename

    # Write structured JSON
    content_json = json.dumps({"reference_date": args.reference_date, "total_drafts": len(drafts), "drafts": drafts}, indent=2)
    json_path.write_text(content_json, encoding="utf-8")

    # Write human-readable Markdown
    md_lines = [
        f"# Accounts Receivable Reminder Drafts",
        f"**Task ID:** {args.task_id}  ",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        f"**Reference Date:** {args.reference_date}  ",
        f"**Total Drafts Prepared:** {len(drafts)}\n",
        "---",
    ]
    for d in drafts:
        approval_badge = "⚠️ **REQUIRES HUMAN APPROVAL (High Value > $5,000)**" if d["requires_approval"] else "✅ Standard Draft"
        md_lines.append(f"\n### Invoice: {d['invoice_id']} - {d['customer_name']} ({approval_badge})")
        md_lines.append(f"- **To:** {d['recipient_email']}")
        md_lines.append(f"- **Amount:** {d['currency']} {d['amount_due']:,.2f} (Due: {d['due_date']} - {d['days_overdue']} days overdue)")
        md_lines.append(f"- **Subject:** {d['email_subject']}")
        md_lines.append(f"\n```text\n{d['email_body']}\n```\n")

    md_content = "\n".join(md_lines)
    md_path.write_text(md_content, encoding="utf-8")

    file_hash = hashlib.sha256(content_json.encode("utf-8")).hexdigest()

    artifacts_info = [
        {"filename": json_filename, "path": str(json_path), "type": "reminder_drafts", "hash": file_hash},
        {"filename": md_filename, "path": str(md_path), "type": "reminder_markdown", "hash": hashlib.sha256(md_content.encode("utf-8")).hexdigest()}
    ]

    return ToolResult(
        success=True,
        data={
            "drafts_count": len(drafts),
            "output_files": [json_filename, md_filename],
            "sha256": file_hash,
            "drafts": drafts
        },
        evidence_summary=f"Saved {len(drafts)} reminder drafts to '{json_filename}' and '{md_filename}' (SHA256: {file_hash[:12]}...).",
        source_references=["sqlite:invoices.db"],
        artifacts=artifacts_info
    )

def register_invoice_tools():
    registry.register(ToolDefinition(
        name="query_invoice_records",
        description="Query customer invoices from the local SQLite database.",
        input_schema=QueryInvoicesInput,
        output_schema=QueryInvoicesOutput,
        handler=handle_query_invoices,
        permission_scope="read"
    ))
    registry.register(ToolDefinition(
        name="audit_invoices",
        description="Audit invoice records against business rules and reference date to identify overdue, paid, disputed, and invalid records.",
        input_schema=AuditInvoicesInput,
        output_schema=AuditInvoicesOutput,
        handler=handle_audit_invoices,
        permission_scope="read"
    ))
    registry.register(ToolDefinition(
        name="save_reminder_drafts",
        description="Generate and save verified payment reminder drafts for overdue invoices.",
        input_schema=SaveReminderDraftsInput,
        output_schema=SaveReminderDraftsOutput,
        handler=handle_save_reminder_drafts,
        permission_scope="write"
    ))

register_invoice_tools()
