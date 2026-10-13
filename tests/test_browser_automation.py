import uuid
import time
import threading
import pytest
import uvicorn
from backend.app import app
from backend.database.session import SessionLocal
from backend.database.models import TaskModel, TaskStepModel
from backend.engine.executor import run_task_execution
from backend.tools.browser_tools import handle_browser_audit, BrowserAuditInput

@pytest.fixture(scope="module")
def local_portal_server():
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(1.0)
    yield "http://127.0.0.1:8001"
    server.should_exit = True

def test_browser_audit_portal_direct_execution(local_portal_server):
    portal_url = f"{local_portal_server}/test-portal"
    res = handle_browser_audit(BrowserAuditInput(
        portal_url=portal_url,
        audit_batch_id="BATCH-TEST-2026",
        auditor_id="TEST-OPERATOR",
        task_id="test_browser_direct"
    ))
    assert res.success, res.error
    assert res.data["verified"] is True
    assert "BATCH-TEST-2026" in res.data["badge_text"]
    assert res.data["screenshot_file"] is not None
    assert len(res.artifacts) == 1

def test_browser_workflow_end_to_end_state_machine(local_portal_server):
    task_id = str(uuid.uuid4())
    db = SessionLocal()
    task = TaskModel(
        id=task_id,
        original_request="Perform bounded browser audit portal verification and capture screenshot evidence",
        normalized_goal="",
        status="running"
    )
    db.add(task)
    db.commit()

    # Step targeting the active test fixture port
    step = TaskStepModel(
        id=str(uuid.uuid4()),
        task_id=task_id,
        step_index=0,
        name="Execute Bounded Portal Verification in Headless Browser",
        tool_name="browser_audit_portal",
        tool_args_json=f'{{"portal_url": "{local_portal_server}/test-portal", "audit_batch_id": "BATCH-E2E-2026", "task_id": "{task_id}"}}',
        status="pending",
        requires_approval=False,
        approval_status="none"
    )
    db.add(step)
    db.commit()
    db.close()

    result = run_task_execution(task_id)
    assert result["status"] == "completed"
