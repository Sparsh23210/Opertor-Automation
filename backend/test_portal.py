from fastapi import APIRouter
from fastapi.responses import HTMLResponse

portal_router = APIRouter()

PORTAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Company Internal Operations & Audit Portal</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }
    .container { max-width: 800px; margin: 0 auto; background: #1e293b; border-radius: 8px; padding: 2rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }
    h1 { color: #38bdf8; font-size: 1.5rem; margin-top: 0; }
    p { color: #94a3b8; }
    .form-group { margin-bottom: 1.25rem; }
    label { display: block; font-weight: 500; margin-bottom: 0.5rem; color: #cbd5e1; }
    input[type="text"] { width: 100%; padding: 0.5rem; background: #0f172a; border: 1px solid #334155; border-radius: 4px; color: #fff; box-sizing: border-box; }
    .checkbox-group { display: flex; align-items: center; gap: 0.5rem; }
    button { background: #0284c7; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 4px; cursor: pointer; font-weight: 600; }
    button:hover { background: #0369a1; }
    #confirmation-alert { display: none; margin-top: 1.5rem; padding: 1rem; background: #064e3b; border: 1px solid #059669; border-radius: 6px; color: #a7f3d0; }
    #audit-log-badge { font-family: monospace; font-weight: bold; }
  </style>
</head>
<body>
  <div class="container">
    <h1 id="portal-title">Company Internal Operations & Audit Portal</h1>
    <p>Authorized Operator Verification Interface. Domain restricted to localhost/127.0.0.1.</p>
    
    <div id="confirmation-alert">
      <strong>Status: Verification Confirmed!</strong>
      <p id="confirmation-message">Audit record <span id="audit-log-badge"></span> successfully verified and committed to ledger.</p>
    </div>

    <form id="audit-form" onsubmit="event.preventDefault(); submitAudit();">
      <div class="form-group">
        <label for="auditor-id">Auditor / Operator Identifier:</label>
        <input type="text" id="auditor-id" name="auditor_id" value="OPERATOR-AUTONOMOUS-01" required />
      </div>
      <div class="form-group">
        <label for="audit-batch">Audit Reference / Batch ID:</label>
        <input type="text" id="audit-batch" name="audit_batch" placeholder="BATCH-2026-Q1" required />
      </div>
      <div class="form-group checkbox-group">
        <input type="checkbox" id="verify-checksum" name="verify_checksum" checked required />
        <label for="verify-checksum">I confirm that all financial and inventory artifacts have been verified.</label>
      </div>
      <button type="submit" id="btn-submit-audit">Submit & Record Verification</button>
    </form>
  </div>

  <script>
    function submitAudit() {
      const batch = document.getElementById('audit-batch').value;
      const auditor = document.getElementById('auditor-id').value;
      const alertBox = document.getElementById('confirmation-alert');
      const badge = document.getElementById('audit-log-badge');
      
      badge.textContent = batch + " (by " + auditor + ")";
      alertBox.style.display = 'block';
      document.getElementById('btn-submit-audit').disabled = true;
      document.getElementById('btn-submit-audit').textContent = "Recorded in Portal";
    }
  </script>
</body>
</html>
"""

@portal_router.get("/test-portal", response_class=HTMLResponse)
def get_test_portal():
    return HTMLResponse(content=PORTAL_HTML)
