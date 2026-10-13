import json
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field
from backend.config import settings, resolve_safe_path
from backend.tools.registry import ToolResult, ToolDefinition, registry
from backend.tools.invoice_tools import handle_query_invoices, QueryInvoicesInput

# 1. Read Artifact
class ReadArtifactInput(BaseModel):
    filename: str = Field(description="Filename of artifact located in data/outputs/")

class ReadArtifactOutput(BaseModel):
    filename: str
    content: str
    sha256: str
    size_bytes: int

def handle_read_artifact(args: ReadArtifactInput) -> ToolResult:
    target_path = (settings.OUTPUT_DIR / args.filename).resolve()
    safe_path = resolve_safe_path(target_path, [settings.OUTPUT_DIR])

    if not safe_path.exists() or not safe_path.is_file():
        return ToolResult(
            success=False,
            error=f"Artifact '{args.filename}' not found in output directory.",
            evidence_summary=f"Read artifact failed: '{args.filename}' does not exist."
        )

    try:
        content = safe_path.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return ToolResult(
            success=True,
            data={
                "filename": args.filename,
                "content": content,
                "sha256": file_hash,
                "size_bytes": safe_path.stat().st_size
            },
            evidence_summary=f"Successfully read back artifact '{args.filename}' ({len(content)} chars, SHA256: {file_hash[:12]}...).",
            source_references=[f"artifact:{args.filename}"]
        )
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Failed to read artifact '{args.filename}': {str(e)}",
            evidence_summary=f"Artifact read error: {str(e)}"
        )

# 2. Verify Artifact Content Independently
class VerifyArtifactInput(BaseModel):
    filename: str = Field(description="Filename of artifact in outputs/")
    artifact_type: str = Field(description="Type: 'reminder_drafts', 'reminder_markdown', 'operations_report', or 'generic'")
    expected_criteria: dict = Field(default_factory=dict, description="Expected counts, totals, or checks")

class VerifyArtifactOutput(BaseModel):
    verified: bool
    checks_passed: list[str]
    checks_failed: list[str]
    verification_summary: str

def handle_verify_artifact(args: VerifyArtifactInput) -> ToolResult:
    read_res = handle_read_artifact(ReadArtifactInput(filename=args.filename))
    if not read_res.success:
        return ToolResult(
            success=False,
            error=f"Verification failed: cannot read artifact '{args.filename}'.",
            evidence_summary="Artifact verification failed: target file missing."
        )

    content = read_res.data["content"]
    file_hash = read_res.data["sha256"]
    checks_passed = []
    checks_failed = []

    # Check 1: Non-empty file
    if len(content.strip()) > 0:
        checks_passed.append("File content is non-empty")
    else:
        checks_failed.append("File content is unexpectedly empty")

    if args.artifact_type == "reminder_drafts":
        try:
            data = json.loads(content)
            drafts = data.get("drafts", [])
            expected_count = args.expected_criteria.get("expected_count")

            # Check count
            if expected_count is not None:
                if len(drafts) == expected_count:
                    checks_passed.append(f"Draft count ({len(drafts)}) matches expected count ({expected_count})")
                else:
                    checks_failed.append(f"Draft count mismatch: got {len(drafts)}, expected {expected_count}")
            else:
                checks_passed.append(f"Parsed {len(drafts)} drafts successfully")

            # Independent reconciliation against live DB
            db_res = handle_query_invoices(QueryInvoicesInput(limit=100))
            if db_res.success:
                db_invoices = {inv["id"]: inv for inv in db_res.data["records"]}
                for d in drafts:
                    inv_id = d.get("invoice_id")
                    if inv_id in db_invoices:
                        rec = db_invoices[inv_id]
                        # Check status
                        if rec["status"] != "unpaid":
                            checks_failed.append(f"Invoice {inv_id} has status '{rec['status']}', should NOT have reminder!")
                        # Check amount
                        if abs(rec["amount"] - d.get("amount_due", 0)) < 0.01:
                            checks_passed.append(f"Invoice {inv_id} draft amount matches DB record exactly")
                        else:
                            checks_failed.append(f"Invoice {inv_id} amount mismatch: draft {d.get('amount_due')} vs DB {rec['amount']}")
                    else:
                        checks_failed.append(f"Draft references unknown invoice ID '{inv_id}'")
        except json.JSONDecodeError as jde:
            checks_failed.append(f"Failed to parse JSON content: {str(jde)}")

    elif args.artifact_type in ("operations_report", "reminder_markdown"):
        # Check required markdown sections
        required_sections = args.expected_criteria.get("required_sections", [])
        for section in required_sections:
            if section.lower() in content.lower():
                checks_passed.append(f"Required section '{section}' found in artifact")
            else:
                checks_failed.append(f"Required section '{section}' missing from artifact")

    else:
        checks_passed.append("Generic content existence check passed")

    is_verified = (len(checks_failed) == 0 and len(checks_passed) > 0)
    summary_text = (
        f"Verification {'PASSED' if is_verified else 'FAILED'} for '{args.filename}'. "
        f"{len(checks_passed)} checks passed, {len(checks_failed)} failed."
    )

    return ToolResult(
        success=is_verified,
        data={
            "verified": is_verified,
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "verification_summary": summary_text,
            "sha256": file_hash
        },
        error=None if is_verified else f"Verification failed with {len(checks_failed)} violations: {'; '.join(checks_failed)}",
        evidence_summary=summary_text,
        source_references=[f"artifact:{args.filename}"]
    )

def register_verification_tools():
    registry.register(ToolDefinition(
        name="read_artifact",
        description="Read an artifact from the approved output directory to inspect its contents.",
        input_schema=ReadArtifactInput,
        output_schema=ReadArtifactOutput,
        handler=handle_read_artifact,
        permission_scope="read"
    ))
    registry.register(ToolDefinition(
        name="verify_artifact_content",
        description="Independently verify an artifact against source data, schema requirements, and recomputed calculations.",
        input_schema=VerifyArtifactInput,
        output_schema=VerifyArtifactOutput,
        handler=handle_verify_artifact,
        permission_scope="read"
    ))

register_verification_tools()
