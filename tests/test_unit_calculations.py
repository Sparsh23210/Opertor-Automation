import pytest
from backend.tools.report_tools import handle_calculate_operations, CalculateOperationsInput
from backend.tools.invoice_tools import handle_audit_invoices, AuditInvoicesInput

def test_deterministic_sales_and_inventory_calculations():
    res = handle_calculate_operations(CalculateOperationsInput(
        sales_file="operations/sales_2026_q1.csv",
        inventory_file="operations/inventory_2026_q1.json"
    ))
    assert res.success
    sales = res.data["sales_metrics"]
    inv = res.data["inventory_metrics"]
    anomalies = res.data["anomalies"]

    # Verify calculated vs reported revenue
    assert sales["total_revenue_reported"] == 11150.00
    assert sales["total_revenue_calculated"] == 11010.00
    # Discrepancy detected
    assert len(anomalies) >= 3

    # Check that duplicate order ORD-101 was isolated
    dup_anomalies = [a for a in anomalies if "duplicate" in a.get("details", "").lower()]
    assert len(dup_anomalies) == 1
    assert dup_anomalies[0]["order_id"] == "ORD-101"

    # Check revenue calculation discrepancy in ORD-105 (8 * 120 = 960 != 1100)
    rev_anomalies = [a for a in anomalies if a.get("type") == "revenue_calculation_discrepancy"]
    assert len(rev_anomalies) == 1
    assert rev_anomalies[0]["order_id"] == "ORD-105"
    assert rev_anomalies[0]["variance"] == 140.00

    # Check inventory variance in SKU-DELTA (shrinkage)
    inv_anomalies = [a for a in anomalies if a.get("type") == "inventory_variance"]
    assert len(inv_anomalies) == 1
    assert inv_anomalies[0]["sku"] == "SKU-DELTA"
    assert inv_anomalies[0]["variance"] == -2

def test_invoice_total_overdue_deterministic_sum():
    res = handle_audit_invoices(AuditInvoicesInput(reference_date="2026-10-10"))
    assert res.success
    overdue_invoices = res.data["overdue_invoices"]
    expected_sum = sum(inv["amount"] for inv in overdue_invoices)
    assert res.data["summary"]["total_overdue_amount"] == round(expected_sum, 2)
    assert res.data["summary"]["total_overdue_amount"] == 19250.50
