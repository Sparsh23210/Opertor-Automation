import sqlite3
import json
import csv
from pathlib import Path
from backend.config import settings
from backend.database.session import init_system_db

def init_invoices_db():
    """Initializes the sample customer invoices SQLite database with realistic records."""
    db_path = settings.INVOICES_DB_PATH
    if db_path.exists():
        db_path.unlink()
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE invoices (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL, -- unpaid, paid, pending, disputed, cancelled, invalid
            notes TEXT
        )
    """)

    sample_invoices = [
        # (id, customer_id, customer_name, customer_email, issue_date, due_date, amount, currency, status, notes)
        ("INV-2026-001", "CUST-001", "Acme Corporation", "billing@acme.example.com", "2026-08-01", "2026-09-01", 4500.00, "USD", "unpaid", "Standard Net-30"),
        ("INV-2026-002", "CUST-002", "Globex Industries", "ap@globex.example.com", "2026-08-15", "2026-09-15", 8200.00, "USD", "unpaid", "Large enterprise contract - requires human approval if > $5000"),
        ("INV-2026-003", "CUST-003", "Stark Logistics", "finance@stark.example.com", "2026-09-01", "2026-10-01", 1250.00, "USD", "paid", "Paid on 2026-09-28 via Wire"),
        ("INV-2026-004", "CUST-004", "Wayne Enterprises", "accounts@wayne.example.com", "2026-09-20", "2026-10-20", 3100.00, "USD", "pending", "Due in future relative to 2026-10-10"),
        ("INV-2026-005", "CUST-005", "Cyberdyne Systems", "payables@cyberdyne.example.com", "2026-08-25", "2026-09-25", 2750.50, "USD", "unpaid", "Follow-up required"),
        ("INV-2026-006", "CUST-006", "Umbrella Pharmaceuticals", "audit@umbrella.example.com", "2026-07-15", "2026-08-15", 6400.00, "USD", "disputed", "Client disputes delivery confirmation. Review required."),
        ("INV-2026-007", "CUST-007", "Massive Dynamic", "invoices@massivedynamic.example.com", "2026-08-10", "2026-09-10", 1950.00, "USD", "cancelled", "Contract renegotiated"),
        ("INV-2026-008", "", "Initech LLC", "peter@initech.example.com", "2026-08-05", "2026-09-05", -500.00, "USD", "unpaid", "Malformed record: missing customer_id and negative amount"),
        ("INV-2026-009", "CUST-009", "Soylent Corp", "ap@soylent.example.com", "2026-08-30", "2026-09-30", 3800.00, "EUR", "unpaid", "Foreign currency Net-30"),
    ]

    cur.executemany("""
        INSERT INTO invoices (id, customer_id, customer_name, customer_email, issue_date, due_date, amount, currency, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_invoices)

    conn.commit()
    conn.close()

def init_policies():
    """Seeds standard operating procedures and company policies."""
    settings.POLICIES_DIR.mkdir(parents=True, exist_ok=True)
    
    invoice_sop = """# SOP-FIN-001: Credit Control & Invoice Collection Procedure

## 1. Scope and Objective
This Standard Operating Procedure governs the identification, validation, and reminder drafting for outstanding accounts receivable at the company.

## 2. Definitions and Overdue Rules
- Reference Date: Evaluated against reference date (default: 2026-10-10 unless specified).
- Overdue Status: An invoice is strictly overdue if and only if:
  1. Status is 'unpaid'
  2. Due date is earlier than the reference date
  3. The record passes data integrity validation (positive amount, non-empty customer ID).
- Inactive / Non-overdue: Invoices with status 'paid', 'pending', or 'cancelled' must NOT receive collection reminders.

## 3. Disputed Invoices & Human Review Safeguards
- Invoices marked as 'disputed' or with unresolved billing complaints MUST NEVER have automated reminder drafts issued without explicit Human Approval.
- Such invoices must be flagged in the audit report as 'Needs Human Review' with the stated reason.

## 4. High-Value Threshold Approval Policy
- Invoices exceeding $5,000.00 USD require explicit supervisor or human authorization before reminders or external notices are prepared.

## 5. Required Verification
- Any generated reminder drafts must be independently verified against the invoice database:
  - Customer name, invoice ID, and exact amount must match database records.
  - The calculated sum of overdue receivables must match the recomputed database total.
"""
    (settings.POLICIES_DIR / "sop_invoice_collection.md").write_text(invoice_sop, encoding="utf-8")

    inventory_sop = """# SOP-OPS-002: Sales and Inventory Audit Procedure

## 1. Purpose
Defines data validation, cross-reconciliation, and anomaly detection guidelines for quarterly business operations reports.

## 2. Schema and File Standards
- Sales transaction files must contain: order_id, date, sku, units_sold, unit_price, total_revenue.
- Inventory files must contain: sku, product_name, starting_stock, ending_stock, unit_cost.
- Formats supported: CSV and JSON within approved workspace boundaries.

## 3. Data Integrity & Discrepancy Checks
- Duplicate order_id entries must be flagged as integrity violations and isolated.
- Calculated revenue (units_sold * unit_price) must be compared deterministically with reported total_revenue. Any mismatch exceeding $0.01 must be flagged as a calculation discrepancy.
- Stock Reconciliation: Expected ending stock = starting_stock - units_sold. Any variance must be noted as inventory shrinkage or discrepancy.

## 4. Verification and Artifact Integrity
- Every generated operations report must contain clear source citations, calculation methodology, identified anomalies, and deterministic summary tables.
- Verification must reopen the written report artifact and confirm that reported numbers match deterministic recomputations.
"""
    (settings.POLICIES_DIR / "sop_inventory_audit.md").write_text(inventory_sop, encoding="utf-8")

def init_operations_data():
    """Seeds sample sales CSV and inventory JSON files for Workflow B."""
    settings.OPERATIONS_DIR.mkdir(parents=True, exist_ok=True)

    sales_csv_path = settings.OPERATIONS_DIR / "sales_2026_q1.csv"
    sales_rows = [
        ["order_id", "date", "sku", "units_sold", "unit_price", "total_revenue"],
        ["ORD-101", "2026-01-15", "SKU-ALPHA", "10", "150.00", "1500.00"],
        ["ORD-102", "2026-01-18", "SKU-BETA", "5", "300.00", "1500.00"],
        ["ORD-103", "2026-02-05", "SKU-GAMMA", "20", "45.00", "900.00"],
        ["ORD-104", "2026-02-20", "SKU-ALPHA", "15", "150.00", "2250.00"],
        ["ORD-105", "2026-03-02", "SKU-DELTA", "8", "120.00", "1100.00"], # Discrepancy: 8 * 120 = 960 != 1100
        ["ORD-106", "2026-03-14", "SKU-BETA", "12", "300.00", "3600.00"],
        ["ORD-101", "2026-03-25", "SKU-ALPHA", "2", "150.00", "300.00"],   # Duplicate order_id violation!
    ]
    with open(sales_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(sales_rows)

    inventory_json_path = settings.OPERATIONS_DIR / "inventory_2026_q1.json"
    inventory_data = [
        {"sku": "SKU-ALPHA", "product_name": "Alpha Enterprise Hub", "starting_stock": 100, "ending_stock": 73, "unit_cost": 90.00},
        {"sku": "SKU-BETA", "product_name": "Beta Cloud Gateway", "starting_stock": 50, "ending_stock": 33, "unit_cost": 180.00},
        {"sku": "SKU-GAMMA", "product_name": "Gamma Sensor Pod", "starting_stock": 200, "ending_stock": 180, "unit_cost": 25.00},
        {"sku": "SKU-DELTA", "product_name": "Delta Wireless Adapter", "starting_stock": 40, "ending_stock": 30, "unit_cost": 70.00}, # Starting 40 - 8 sold = 32 expected, ending is 30 -> 2 units variance!
    ]
    with open(inventory_json_path, mode="w", encoding="utf-8") as f:
        json.dump(inventory_data, f, indent=2)

def setup_all():
    init_system_db()
    init_invoices_db()
    init_policies()
    init_operations_data()
    print("Database and test workspace fixtures initialized successfully.")

if __name__ == "__main__":
    setup_all()
