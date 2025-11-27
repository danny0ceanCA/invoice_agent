# CareSpend Database Schema Reference
This document defines the structure, meaning, and relationships of all database tables used by the CareSpend Analytics Agent.  
It is intended for fine-tuning GPT-4.1 models to understand SCUSD invoice data and produce accurate SQL queries.

---

# ============================
# 1. TABLE: invoices
# ============================

Stores **one aggregated invoice per student per vendor per service month**.

## Columns:
- **id** (INTEGER, PK)  
  Unique identifier for each invoice.

- **district_key** (TEXT)  
  Required for filtering. All SQL queries **must** filter by district_key.

- **student_name** (TEXT)  
  The student billed for this invoice.  
  Normalized case-insensitive comparison is required.

- **vendor_id** (INTEGER, FK → vendors.id)  
  Vendor providing the services.

- **total_cost** (REAL)  
  Sum of all invoice_line_items.cost for this invoice.  
  Used for *student spend*, *vendor spend*, *district-wide cost*, etc.

- **total_hours** (REAL)  
  Sum of all invoice_line_items.hours for this invoice.  
  Used for *student hours*, *district hours*, *vendor hours*, etc.

- **service_month** (TEXT)  
  Billing period in “YYYY-MM” format.  
  Used in all month-based aggregations.

- **invoice_date** (TEXT / DATETIME)  
  Actual invoice processing date.  
  Used for:
  - Year-to-date (YTD) filters  
  - School-year windows  
  - Trend analysis

- **status** (TEXT, optional)  
  Typically indicates invoice processing status.

## When to use this table:
- Any query involving **total cost**  
- Any query involving **total hours** (aggregated by vendor or student)  
- District-wide monthly or YTD summaries  
- School-year cost or hours comparisons  
- Trend analysis over months  
- Ranking highest-cost or highest-hours students  
- Ranking vendors by spend or hours  
- Comparing two students (cost or hours)  
- Comparing two vendors (cost or hours)

---

# ============================
# 2. TABLE: invoice_line_items
# ============================

Stores **detailed service entries** for each invoice.

Each row represents a **single service provided on a single day**.

## Columns:
- **id** (INTEGER, PK)

- **invoice_id** (INTEGER, FK → invoices.id)

- **student** (TEXT)  
  Student served on this line item.  
  Often duplicated across line items.

- **clinician** (TEXT)  
  Role or name of the clinician providing the service (LVN, RN, HA, etc.).

- **service_code** (TEXT)  
  License / classification for clinician type (LVN, RN, HHA, CNA, etc.)

- **service_date** (TEXT / DATE)  
  Actual date the service was delivered.

- **hours** (REAL)  
  Hours billed for this service entry.

- **cost** (REAL)  
  Cost for this line item.

## When to use this table:
- Detailed invoice summaries  
- Day-by-day service review  
- Clinician-level analysis  
- Clinician-type cost or hours  
- Vendor line-item analysis  
- Student service breakdown for specific months  
- Temporal detail (service_date)  
- Anything involving individual entries, not aggregates

**Important:**  
To get aggregated hours or cost, join to invoices using:

```sql
invoice_line_items.invoice_id = invoices.id
