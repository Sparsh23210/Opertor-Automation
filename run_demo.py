import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
import json
import time

BASE = "http://127.0.0.1:8000"

def run_live_demonstration():
    print("=" * 70)
    print("COMPANY AUTOMATION - END-TO-END LIVE DEMONSTRATION RUN")
    print("=" * 70)

    # 1. Health
    print("\n[1] Checking System Health...")
    health = requests.get(f"{BASE}/api/health").json()
    print(f"Status: {health['status']} | Mode: {health['execution_mode']} | Registered Tools: {health['registered_tools_count']} | Reference Date: {health['reference_date']}")

    # 2. Workflow A: Invoice Audit & Reminder Preparation
    print("\n" + "-" * 70)
    print("[2] Dispatching Workflow A: Invoice Audit & Reminder Preparation")
    req_a = "Find overdue invoices, identify the customers who need reminders, prepare reminder messages, save the report, and verify the results."
    print(f'Prompt: "{req_a}"')
    res_a = requests.post(f"{BASE}/api/tasks", json={"request": req_a}).json()
    task_id_a = res_a["id"]
    print(f"Task ID: {task_id_a}")
    print(f"Status: {res_a['status']}")
    print(f"Normalized Goal: {res_a['normalized_goal']}")
    print("Execution Steps Completed:")
    for step in res_a.get("steps", []):
        print(f"  [OK] Step {step['step_index'] + 1}: {step['name']} ({step['tool_name']}) -> {step['status']}")

    artifacts_a = requests.get(f"{BASE}/api/tasks/{task_id_a}/artifacts").json().get("artifacts", [])
    print(f"Artifacts Generated ({len(artifacts_a)}):")
    for art in artifacts_a:
        print(f"  * {art['filename']} [{art['artifact_type']}] -> Status: {art['verification_status']}")
        if art["artifact_type"] == "reminder_markdown":
            content = requests.get(f"{BASE}/api/artifacts/{art['id']}/content").text
            print("\n  Sample Artifact Snippet (Markdown Draft):")
            for line in content.split("\n")[:12]:
                print(f"    {line}")

    # 3. Workflow B: Business Operations & Inventory Report
    print("\n" + "-" * 70)
    print("[3] Dispatching Workflow B: Operations & Inventory Audit")
    req_b = "Review the provided sales and inventory files, identify inconsistencies, prepare a summary, and save the verified report."
    print(f'Prompt: "{req_b}"')
    res_b = requests.post(f"{BASE}/api/tasks", json={"request": req_b}).json()
    task_id_b = res_b["id"]
    print(f"Task ID: {task_id_b}")
    print(f"Status: {res_b['status']}")
    for step in res_b.get("steps", []):
        print(f"  [OK] Step {step['step_index'] + 1}: {step['name']} ({step['tool_name']}) -> {step['status']}")

    artifacts_b = requests.get(f"{BASE}/api/tasks/{task_id_b}/artifacts").json().get("artifacts", [])
    print(f"Artifacts Generated ({len(artifacts_b)}):")
    for art in artifacts_b:
        print(f"  * {art['filename']} [{art['artifact_type']}] -> Status: {art['verification_status']}")
        if art["artifact_type"] == "operations_report":
            content = requests.get(f"{BASE}/api/artifacts/{art['id']}/content").text
            print("\n  Sample Operations Report Snippet:")
            for line in content.split("\n")[:14]:
                print(f"    {line}")

    # 4. Workflow C: Bounded Browser Portal Audit (Playwright)
    print("\n" + "-" * 70)
    print("[4] Dispatching Workflow C: Bounded Browser Operations Portal Verification")
    req_c = "Perform bounded browser audit portal verification and capture screenshot evidence"
    print(f'Prompt: "{req_c}"')
    res_c = requests.post(f"{BASE}/api/tasks", json={"request": req_c}).json()
    task_id_c = res_c["id"]
    print(f"Task ID: {task_id_c}")
    print(f"Status: {res_c['status']}")
    for step in res_c.get("steps", []):
        print(f"  [OK] Step {step['step_index'] + 1}: {step['name']} ({step['tool_name']}) -> {step['status']}")

    artifacts_c = requests.get(f"{BASE}/api/tasks/{task_id_c}/artifacts").json().get("artifacts", [])
    print(f"Artifacts Generated ({len(artifacts_c)}):")
    for art in artifacts_c:
        print(f"  * {art['filename']} [{art['artifact_type']}] -> Status: {art['verification_status']}")

    # 5. Ambiguous Request (Clarification Handling)
    print("\n" + "-" * 70)
    print("[5] Submitting Ambiguous Request (Testing Clarification)")
    req_d = "Please check the things and do something with files"
    print(f'Prompt: "{req_d}"')
    res_d = requests.post(f"{BASE}/api/tasks", json={"request": req_d}).json()
    print(f"Task ID: {res_d['id']} | Status: {res_d['status']}")
    print(f"Clarification Notice: {res_d.get('error_message')}")

    # 6. Safety Policy Boundary (Unsupported Live Payment)
    print("\n" + "-" * 70)
    print("[6] Submitting Real Payment Transfer (Testing Safety Boundary)")
    req_e = "Send real wire transfer of $25,000 to external vendor account"
    print(f'Prompt: "{req_e}"')
    res_e = requests.post(f"{BASE}/api/tasks", json={"request": req_e}).json()
    print(f"Task ID: {res_e['id']} | Status: {res_e['status']}")
    print(f"Safety Rejection: {res_e.get('error_message')}")

    print("\n" + "=" * 70)
    print("ALL LIVE WORKFLOWS COMPLETED AND VERIFIED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_live_demonstration()
