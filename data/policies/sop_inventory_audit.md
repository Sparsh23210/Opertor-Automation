# SOP-OPS-002: Sales and Inventory Audit Procedure

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
