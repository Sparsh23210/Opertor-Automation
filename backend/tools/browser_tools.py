import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from backend.config import settings
from backend.tools.registry import ToolResult, ToolDefinition, registry

class BrowserAuditInput(BaseModel):
    portal_url: str = Field(default="http://127.0.0.1:8000/test-portal", description="URL of authorized audit portal")
    audit_batch_id: str = Field(default="BATCH-AUDIT-2026", description="Batch identifier to record in portal")
    auditor_id: str = Field(default="OPERATOR-AUTONOMOUS-01", description="Auditor identity")
    task_id: str = Field(default="browser_task", description="Task identifier for screenshot naming")

class BrowserAuditOutput(BaseModel):
    url: str
    verified: bool
    confirmation_text: str
    screenshot_file: str

def handle_browser_audit(args: BrowserAuditInput) -> ToolResult:
    # 1. Domain security restriction
    parsed = urlparse(args.portal_url)
    hostname = (parsed.hostname or "").lower()
    if hostname not in settings.ALLOWED_BROWSER_DOMAINS:
        return ToolResult(
            success=False,
            error=f"Security Violation: Target host '{hostname}' is not in permitted domains list: {settings.ALLOWED_BROWSER_DOMAINS}",
            evidence_summary=f"Blocked unauthorized browser navigation attempt to '{args.portal_url}'."
        )

    screenshot_filename = f"browser_audit_{args.task_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.png"
    screenshot_path = settings.OUTPUT_DIR / screenshot_filename

    def _run_in_thread():
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                page = context.new_page()

                # Bounded navigation with timeout
                try:
                    page.goto(args.portal_url, timeout=10000, wait_until="networkidle")
                except Exception as nav_err:
                    browser.close()
                    return ToolResult(
                        success=False,
                        error=f"Navigation failure to '{args.portal_url}': {str(nav_err)}",
                        evidence_summary=f"Browser failed to load '{args.portal_url}'."
                    )

                # Inspect page state
                title = page.title()
                header_text = page.locator("#portal-title").inner_text()
                if "Operations & Audit Portal" not in header_text:
                    browser.close()
                    return ToolResult(
                        success=False,
                        error=f"Unexpected page layout: portal title mismatch '{header_text}'.",
                        evidence_summary="Browser observed unknown page layout."
                    )

                # Fill form
                page.fill("#auditor-id", args.auditor_id)
                page.fill("#audit-batch", args.audit_batch_id)

                # Execute interaction
                page.click("#btn-submit-audit")

                # Observe resulting state and verify confirmation
                page.wait_for_selector("#confirmation-alert", state="visible", timeout=5000)
                confirmation_msg = page.locator("#confirmation-message").inner_text()
                badge_text = page.locator("#audit-log-badge").inner_text()

                # Independent verification check on visible DOM state
                if args.audit_batch_id not in badge_text:
                    browser.close()
                    return ToolResult(
                        success=False,
                        error=f"Verification failed: DOM confirmation '{badge_text}' does not contain expected batch '{args.audit_batch_id}'.",
                        evidence_summary="Browser interaction did not result in expected state transition."
                    )

                # Take screenshot evidence
                page.screenshot(path=str(screenshot_path))
                browser.close()

                img_bytes = screenshot_path.read_bytes()
                img_hash = hashlib.sha256(img_bytes).hexdigest()

                return ToolResult(
                    success=True,
                    data={
                        "url": args.portal_url,
                        "verified": True,
                        "confirmation_text": confirmation_msg,
                        "badge_text": badge_text,
                        "screenshot_file": screenshot_filename,
                        "sha256": img_hash
                    },
                    evidence_summary=(
                        f"Successfully performed bounded browser interaction on '{args.portal_url}'. "
                        f"Verified confirmation '{badge_text}'. Captured screenshot '{screenshot_filename}'."
                    ),
                    source_references=[f"web:{args.portal_url}"],
                    artifacts=[{
                        "filename": screenshot_filename,
                        "path": str(screenshot_path),
                        "type": "browser_screenshot",
                        "hash": img_hash
                    }]
                )

        except PlaywrightTimeoutError as te:
            return ToolResult(
                success=False,
                error=f"Browser action timed out: {str(te)}",
                evidence_summary="Playwright timeout during form interaction or verification."
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Browser automation error: {repr(e)}",
                evidence_summary=f"Playwright unexpected error: {repr(e)}"
            )

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_in_thread)
        return future.result()

def register_browser_tools():
    registry.register(ToolDefinition(
        name="browser_audit_portal",
        description="Navigate to authorized local internal audit portal, submit batch verification, and verify page state.",
        input_schema=BrowserAuditInput,
        output_schema=BrowserAuditOutput,
        handler=handle_browser_audit,
        permission_scope="execute"
    ))

register_browser_tools()
