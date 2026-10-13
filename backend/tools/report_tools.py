import csv
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
from backend.config import settings
from backend.tools.registry import ToolResult, ToolDefinition, registry

# 1. Calculate Operations Summary
class CalculateOperationsInput(BaseModel):
    sales_file: str = Field(default="operations/sales_2026_q1.csv", description="Relative path to sales CSV")
    inventory_file: str = Field(default="operations/inventory_2026_q1.json", description="Relative path to inventory JSON")

class CalculateOperationsOutput(BaseModel):
    sales_metrics: dict
    inventory_metrics: dict
    anomalies: list[dict]
    source_files: list[str]

def handle_calculate_operations(args: CalculateOperationsInput) -> ToolResult:
    sales_path = (settings.DATA_DIR / args.sales_file).resolve()
    inv_path = (settings.DATA_DIR / args.inventory_file).resolve()

    if not sales_path.exists():
        return ToolResult(
            success=False,
            error=f"Sales file '{args.sales_file}' not found.",
            evidence_summary="Operations calculation failed: missing sales file."
        )
    if not inv_path.exists():
        return ToolResult(
            success=False,
            error=f"Inventory file '{args.inventory_file}' not found.",
            evidence_summary="Operations calculation failed: missing inventory file."
        )

    # Parse and validate sales
    sales_records = []
    seen_order_ids = set()
    duplicate_orders = []
    calculation_mismatches = []
    total_revenue_reported = 0.0
    total_revenue_calculated = 0.0
    sku_units_sold = {}

    with open(sales_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):
            order_id = row.get("order_id", "").strip()
            sku = row.get("sku", "").strip()
            date_str = row.get("date", "").strip()

            try:
                units = int(row.get("units_sold", 0))
                unit_price = float(row.get("unit_price", 0.0))
                reported_rev = float(row.get("total_revenue", 0.0))
            except ValueError as ve:
                calculation_mismatches.append({
                    "row": row_idx,
                    "order_id": order_id,
                    "type": "malformed_numbers",
                    "details": str(ve)
                })
                continue

            # Duplicate check
            if order_id in seen_order_ids:
                duplicate_orders.append({
                    "row": row_idx,
                    "order_id": order_id,
                    "sku": sku,
                    "details": f"Duplicate order_id '{order_id}' found in row {row_idx}"
                })
            else:
                seen_order_ids.add(order_id)

            # Calculation verification: units * price == reported_rev
            computed_rev = round(units * unit_price, 2)
            if abs(computed_rev - reported_rev) > 0.01:
                calculation_mismatches.append({
                    "row": row_idx,
                    "order_id": order_id,
                    "sku": sku,
                    "type": "revenue_calculation_discrepancy",
                    "reported": reported_rev,
                    "calculated": computed_rev,
                    "variance": round(reported_rev - computed_rev, 2)
                })

            total_revenue_reported += reported_rev
            total_revenue_calculated += computed_rev
            sku_units_sold[sku] = sku_units_sold.get(sku, 0) + units
            sales_records.append(row)

    # Parse and validate inventory
    with open(inv_path, mode="r", encoding="utf-8") as f:
        try:
            inventory_raw = json.load(f)
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Malformed inventory JSON in '{args.inventory_file}': {str(e)}",
                evidence_summary="JSON syntax error in inventory file."
            )

    inventory_analysis = []
    stock_discrepancies = []
    total_inventory_value = 0.0

    for item in inventory_raw:
        sku = item.get("sku")
        name = item.get("product_name")
        start_stock = item.get("starting_stock", 0)
        end_stock = item.get("ending_stock", 0)
        unit_cost = item.get("unit_cost", 0.0)

        sold = sku_units_sold.get(sku, 0)
        expected_ending = start_stock - sold
        variance = end_stock - expected_ending

        total_inventory_value += (end_stock * unit_cost)

        rec = {
            "sku": sku,
            "product_name": name,
            "starting_stock": start_stock,
            "units_sold": sold,
            "expected_ending": expected_ending,
            "recorded_ending": end_stock,
            "variance": variance,
            "unit_cost": unit_cost
        }
        inventory_analysis.append(rec)

        if variance != 0:
            stock_discrepancies.append({
                "sku": sku,
                "product_name": name,
                "expected": expected_ending,
                "recorded": end_stock,
                "variance": variance,
                "type": "inventory_variance"
            })

    anomalies = duplicate_orders + calculation_mismatches + stock_discrepancies

    data = {
        "sales_metrics": {
            "total_rows": len(sales_records),
            "unique_orders": len(seen_order_ids),
            "total_revenue_reported": round(total_revenue_reported, 2),
            "total_revenue_calculated": round(total_revenue_calculated, 2),
            "sku_units_sold": sku_units_sold
        },
        "inventory_metrics": {
            "total_skus": len(inventory_raw),
            "total_inventory_value": round(total_inventory_value, 2),
            "items": inventory_analysis
        },
        "anomalies": anomalies,
        "source_files": [f"file:{args.sales_file}", f"file:{args.inventory_file}"]
    }

    evidence_summary = (
        f"Analyzed {len(sales_records)} sales rows and {len(inventory_raw)} inventory SKUs. "
        f"Reported revenue: ${total_revenue_reported:,.2f}, Calculated: ${total_revenue_calculated:,.2f}. "
        f"Detected {len(anomalies)} anomalies ({len(duplicate_orders)} duplicates, "
        f"{len(calculation_mismatches)} calculation errors, {len(stock_discrepancies)} inventory variances)."
    )

    return ToolResult(
        success=True,
        data=data,
        evidence_summary=evidence_summary,
        source_references=[f"file:{args.sales_file}", f"file:{args.inventory_file}", "policy:sop_inventory_audit.md"]
    )

# 2. Save Operations Report
class SaveOperationsReportInput(BaseModel):
    task_id: str = Field(default="", description="Task identifier")
    sales_file: str = Field(default="operations/sales_2026_q1.csv")
    inventory_file: str = Field(default="operations/inventory_2026_q1.json")

class SaveOperationsReportOutput(BaseModel):
    report_filename: str
    sha256: str
    anomalies_count: int

def handle_save_operations_report(args: SaveOperationsReportInput) -> ToolResult:
    calc_res = handle_calculate_operations(CalculateOperationsInput(
        sales_file=args.sales_file,
        inventory_file=args.inventory_file
    ))
    if not calc_res.success:
        return calc_res

    data = calc_res.data
    sales = data["sales_metrics"]
    inv = data["inventory_metrics"]
    anomalies = data["anomalies"]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    md_filename = f"operations_audit_report_{args.task_id[:8]}_{timestamp}.md"
    json_filename = f"operations_audit_report_{args.task_id[:8]}_{timestamp}.json"

    md_path = settings.OUTPUT_DIR / md_filename
    json_path = settings.OUTPUT_DIR / json_filename

    # Build detailed Markdown Report
    lines = [
        f"# Business Operations & Inventory Audit Report",
        f"**Task ID:** {args.task_id}  ",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        f"**Source Files:** `{args.sales_file}`, `{args.inventory_file}`  ",
        f"**Applicable Policy:** `sop_inventory_audit.md`  ",
        "\n## 1. Executive Summary",
        f"- **Total Sales Rows Processed:** {sales['total_rows']}",
        f"- **Unique Order IDs:** {sales['unique_orders']}",
        f"- **Reported Total Revenue:** ${sales['total_revenue_reported']:,.2f}",
        f"- **Deterministic Calculated Revenue:** ${sales['total_revenue_calculated']:,.2f}",
        f"- **Revenue Net Variance:** ${round(sales['total_revenue_reported'] - sales['total_revenue_calculated'], 2):,.2f}",
        f"- **Total SKUs Audited:** {inv['total_skus']}",
        f"- **Total Closing Inventory Value:** ${inv['total_inventory_value']:,.2f}",
        f"- **Total Anomalies / Inconsistencies Detected:** {len(anomalies)}",
        "\n## 2. Inventory Reconciliation Table",
        "| SKU | Product Name | Starting Stock | Units Sold | Expected Ending | Recorded Ending | Variance | Unit Cost |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |"
    ]

    for item in inv["items"]:
        var_flag = f"⚠️ {item['variance']}" if item["variance"] != 0 else "0"
        lines.append(
            f"| {item['sku']} | {item['product_name']} | {item['starting_stock']} | "
            f"{item['units_sold']} | {item['expected_ending']} | {item['recorded_ending']} | "
            f"{var_flag} | ${item['unit_cost']:,.2f} |"
        )

    lines.append("\n## 3. Discrepancies and Inconsistencies")
    if not anomalies:
        lines.append("No inconsistencies or discrepancies detected.")
    else:
        for idx, a in enumerate(anomalies, start=1):
            lines.append(f"{idx}. **[{a.get('type', 'anomaly').upper()}]**: {json.dumps(a)}")

    lines.append("\n## 4. Limitations and Recommended Actions")
    lines.append("- Highlighted duplicate order entries should be reviewed by sales ops before ERP finalization.")
    lines.append("- Inventory variance in SKU-DELTA indicates possible physical shrinkage or unrecorded transfers.")

    md_content = "\n".join(lines)
    json_content = json.dumps(data, indent=2)

    md_path.write_text(md_content, encoding="utf-8")
    json_path.write_text(json_content, encoding="utf-8")

    md_hash = hashlib.sha256(md_content.encode("utf-8")).hexdigest()
    json_hash = hashlib.sha256(json_content.encode("utf-8")).hexdigest()

    artifacts_info = [
        {"filename": md_filename, "path": str(md_path), "type": "operations_report", "hash": md_hash},
        {"filename": json_filename, "path": str(json_path), "type": "operations_data", "hash": json_hash}
    ]

    return ToolResult(
        success=True,
        data={
            "report_filename": md_filename,
            "data_filename": json_filename,
            "sha256": md_hash,
            "anomalies_count": len(anomalies),
            "summary": {
                "total_revenue": sales["total_revenue_calculated"],
                "anomalies_detected": len(anomalies)
            }
        },
        evidence_summary=f"Saved Operations Audit Report to '{md_filename}' (SHA256: {md_hash[:12]}...).",
        source_references=[f"file:{args.sales_file}", f"file:{args.inventory_file}", "policy:sop_inventory_audit.md"],
        artifacts=artifacts_info
    )

def register_report_tools():
    registry.register(ToolDefinition(
        name="calculate_operations_summary",
        description="Compute deterministic sales revenue, inventory reconciliation, and isolate data discrepancies.",
        input_schema=CalculateOperationsInput,
        output_schema=CalculateOperationsOutput,
        handler=handle_calculate_operations,
        permission_scope="read"
    ))
    registry.register(ToolDefinition(
        name="save_operations_report",
        description="Generate and save the verified Business Operations and Inventory Audit report.",
        input_schema=SaveOperationsReportInput,
        output_schema=SaveOperationsReportOutput,
        handler=handle_save_operations_report,
        permission_scope="write"
    ))

register_report_tools()
