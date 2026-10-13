# SOP-FIN-001: Credit Control & Invoice Collection Procedure

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
