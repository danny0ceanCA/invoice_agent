CareSpend – How to Add New Report Types Safely

A repeatable procedure for integrating new analytics, MVs, and agent behavior.

Your agent pipeline has strict separation of responsibilities:

NLV → understands language

Entity Resolver → applies name matching

SQL Planner → semantic plan

SQL Router → selects analytic mode

Logic Model → writes SQL

Validator / Renderer / Insight Model → format + output

Because of this architecture, adding new reports is extremely safe—as long as you follow this procedure.

⭐ Step-by-Step Guide
STEP 1 — Decide the analytic type (mode)

Every new report belongs to a clear category:

Student-level

student_monthly

student_yearly

student_daily

student_service_code

student_intensity

student_gap_days

student_provider_breakdown

Provider-level

provider_monthly

provider_caseload

provider_service_code

provider_daily

provider_site_distribution (future)

provider_overtime_risk (future)

District-level

district_monthly

district_service_code

district_daily

district_spend_forecast (future)

Vendor-level

vendor_monthly

vendor_trend (future)

If the new report fits an existing category, you do NOT need to modify router/planner.

If it's truly new (e.g., student_gap_days), you may need to:

Add a new "kind" in the SQL Planner

Add a match in SQL Router to assign the new mode

Most new reports fit existing modes.

STEP 2 — Decide whether the report needs a new MV

Ask:

Is the report an AGGREGATION that will be reused often?

If yes, create an MV:

Examples:

student_gap_days_monthly

provider_site_hours_monthly

district_overtime_flag_daily

If no (detail-only or niche query), use raw tables.

STEP 3 — Create the MV (SQLite now, Postgres later)

Every MV should have:

DROP TABLE IF EXISTS mv_xxx;

CREATE TABLE mv_xxx AS
SELECT ...
FROM invoice_line_items ili
JOIN invoices i ON ...
GROUP BY ...
;

CREATE INDEX idx_mv_xxx_... ON mv_xxx (...);


Copy these into:

/db/sqlite/ (dev)

/db/postgres/ (prod future)

STEP 4 — Document the MV in your master MD file

In your markdown file:

## mv_student_gap_days_monthly
- Purpose: count days where student had 0 hours in a given month.
- Source: invoices, invoice_line_items
- Columns:
  - district_key
  - student
  - service_year
  - service_month_num
  - service_month
  - gap_days


This MD file is your source of truth.

STEP 5 — Add MV documentation to DB_SCHEMA_HINT in logic_model.py

Inside:

### materialized views


Add:

mv_student_gap_days_monthly
- purpose: ...
- columns: ...


This tells the LLM “This table exists.”

STEP 6 — Update MATERIALIZED VIEW PRIORITY block in logic_model.py

This determines when the agent uses your MV.

The golden rule:

Trigger MV selection off RouterDecision.mode (not SQL_TEMPLATE_HINT)

Add:

- When RouterDecision.mode == "student_gap_days":
    ALWAYS use mv_student_gap_days_monthly.


Then add a SQL template example:

SELECT service_year, service_month, gap_days
FROM mv_student_gap_days_monthly
WHERE district_key = :district_key
  AND LOWER(student) = LOWER(:student_name)
ORDER BY service_year, service_month_num;


This keeps the agent deterministic.

STEP 7 — (If needed) Update SQL Router to produce a new mode

Only necessary when a new analytic intent is added.

Example addition:

if "gap" in q_lower and primary_type == "student":
    mode = "student_gap_days"


This is usually 2–3 lines max.

If the report fits existing modes (e.g., new student monthly statistic), skip this.

STEP 8 — Test the new report

Ask the agent:

“Show me monthly gap days for Matthew Martin.”

Check the logs to ensure the SQL includes your MV:

FROM mv_student_gap_days_monthly


If raw tables appear instead, revisit Step 6.

STEP 9 — (Optional) Add an insight_model template

E.g., “Matthew had fewer gap days in September compared to August.”

Not required for correctness.

STEP 10 — (Optional) Add a renderer template

If the result is a timeseries, you may want to:

add a sparkline

color negatives/positives

format dates nicely

⭐ Summary of the Safe Workflow

Define report type (mode).

Create MV (if needed).

Document MV in MD file.

Document MV in DB_SCHEMA_HINT.

Add MV routing rule (using RouterDecision.mode).

Add SQL example template.

(Optional) Update SQL Router when adding brand-new mode.

Test and verify via logs.

⭐ Outcome

Using this process, you can add:

student monthly

student yearly

student weekly

student daily

student risk scoring

provider overtime

provider caseload trends

district service code drivers

vendor spend curves

etc.

WITHOUT EVER breaking any existing logic.

You have built a system that can grow indefinitely just by adding documentation + small prompt edits.