"""Logic-model utilities and system prompt for the analytics agent.

Refactor note: extracted from the monolithic agent module to isolate logic
prompting and inference without altering behavior.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Sequence

from .domain_config_loader import load_domain_config
from openai import OpenAI

DB_SCHEMA_HINT = """
You are querying a SQLite database for a school district invoice system.

### invoices
- id INTEGER PRIMARY KEY
- vendor_id INTEGER NOT NULL
- upload_id INTEGER
- student_name VARCHAR(255)
- invoice_number VARCHAR(128)
- invoice_code VARCHAR(64)
- service_month VARCHAR(32)
- invoice_date DATETIME
- total_hours FLOAT
- total_cost FLOAT                      -- THIS is the invoice money amount
- status VARCHAR(50)
- pdf_s3_key VARCHAR(512)
- district_key VARCHAR(64)              -- tenancy boundary: which district owns the invoice
- created_at DATETIME

### vendors
- id INTEGER PRIMARY KEY
- name VARCHAR(255)
- contact_email VARCHAR(255)
- district_key VARCHAR(64)              -- used by vendors to register access to a district

### invoice_line_items
- id INTEGER PRIMARY KEY
- invoice_id INTEGER NOT NULL
- student VARCHAR(255)
- clinician VARCHAR(255)
- service_code VARCHAR(50)
- hours FLOAT
- rate FLOAT
- cost FLOAT                            -- line-item amount
- service_date VARCHAR(32)

### materialized views (SQLite prototypes, mirrored as Postgres MATERIALIZED VIEWs)

mv_student_monthly_hours_cost
- purpose: Student hours + cost per month (per district, year, month).
- columns: district_key TEXT, student TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, total_hours REAL, total_cost REAL

mv_provider_monthly_hours_cost
- purpose: Clinician hours + cost per month.
- columns: district_key TEXT, clinician TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, total_hours REAL, total_cost REAL

mv_student_provider_monthly
- purpose: For each student, monthly breakdown by clinician (hours + cost).
- columns: district_key TEXT, student TEXT, clinician TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, total_hours REAL, total_cost REAL

mv_district_service_code_monthly
- purpose: District totals by service_code per month.
- columns: district_key TEXT, service_code TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, total_hours REAL, total_cost REAL

mv_invoice_summary
- purpose: Invoice-level totals (hours, cost, invoice_date, num_students, num_clinicians).
- columns: invoice_id INTEGER, district_key TEXT, invoice_date DATE, total_hours REAL, total_cost REAL, num_students INTEGER, num_clinicians INTEGER

mv_student_year_summary
- purpose: Yearly totals per student (per district, year).
- columns: district_key TEXT, student TEXT, service_year INTEGER, total_hours REAL, total_cost REAL

mv_provider_caseload_monthly
- purpose: Clinician caseload (#students) + hours per month.
- columns: district_key TEXT, clinician TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, num_students INTEGER, total_hours REAL, total_cost REAL

mv_district_monthly_hours_cost
- purpose: District hours + cost per month.
- columns: district_key TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, total_hours REAL, total_cost REAL

mv_vendor_monthly_hours_cost
- purpose: Vendor hours + cost per month (per district, vendor).
- columns: district_key TEXT, vendor_id INTEGER, vendor_name TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, total_hours REAL, total_cost REAL

mv_student_service_code_monthly
- purpose: Student × service_code hours + cost per month.
- columns: district_key TEXT, student TEXT, service_code TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, total_hours REAL, total_cost REAL

mv_provider_service_code_monthly
- purpose: Clinician × service_code hours + cost per month.
- columns: district_key TEXT, clinician TEXT, service_code TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, total_hours REAL, total_cost REAL

mv_student_daily_hours
- purpose: Daily hours + cost per student.
- columns: district_key TEXT, student TEXT, service_date DATE, total_hours REAL, total_cost REAL

mv_provider_daily_hours
- purpose: Daily hours + cost per clinician.
- columns: district_key TEXT, clinician TEXT, service_date DATE, total_hours REAL, total_cost REAL

mv_student_service_intensity_monthly
- purpose: Student service_days, hours, and avg_hours_per_day per month.
- columns: district_key TEXT, student TEXT, service_year INTEGER, service_month_num INTEGER, service_month TEXT, service_days INTEGER, total_hours REAL, avg_hours_per_day REAL

mv_district_daily_coverage
- purpose: District daily hours, cost, #students, #clinicians.
- columns: district_key TEXT, service_date DATE, total_hours REAL, total_cost REAL, num_students INTEGER, num_clinicians INTEGER
"""

def build_logic_system_prompt() -> str:
    # Refactored to keep the logic stage focused on reasoning and IR construction,
    # not on user-facing presentation or HTML rendering.
    # This pass strengthens natural-language variability handling and explicit
    # ambiguity/IR-only guidance for the logic stage.
    config = load_domain_config()
    materialized_views = config.get("materialized_views", {})
    print("[DOMAIN-CONFIG-DEBUG][LOGIC] Loaded MV names:", list(materialized_views.keys()))
    mode_to_mv_map = config.get("mode_to_mv_map", {})
    print("[DOMAIN-CONFIG-DEBUG][LOGIC] Mode→MV map keys:", list(mode_to_mv_map.keys()))
    router_modes = config.get("router_modes", {})
    config_snippet = (
        "MV_CONFIG:\n"
        + json.dumps(materialized_views, indent=2)
        + "\n\nMODE_TO_MV_MAP:\n"
        + json.dumps(mode_to_mv_map, indent=2)
        + "\n\nROUTER_MODES (read-only):\n"
        + json.dumps(router_modes, indent=2)
        + "\n\n"
    )
    router_contract = (
        "\n"
        "ROUTER CONTRACT:\n"
        "- A RouterDecision JSON object will be provided via a separate system message that begins with 'ROUTER_DECISION (do not reinterpret):'.\n"
        "- You MUST treat this RouterDecision as the single source of truth for high-level analytics mode (e.g., district_summary, student_monthly, vendor_monthly, invoice_details, student_provider_breakdown, provider_breakdown, top_invoices), primary entities, time_window, and month scope.\n"
        "- Do NOT try to re-derive or reinterpret the mode from natural language. Obey the RouterDecision.\n\n"
    )

    memory_rules = (
        "\n"
        "MEMORY & CONTEXT RULES:\n"
        "- You have access to conversation history loaded from Redis.\n"
        "- Use this memory to interpret follow-up queries, pronouns, and references to 'these students', 'these invoices', 'these providers', 'same ones', etc.\n"
        "- Treat the last returned row set (students, invoices, providers, vendors, months) as the active working set unless the user explicitly changes scope.\n"
        "- When the user refers to 'these students', 'those invoices', or similar, you MUST restrict your SQL to the entities in the most recent relevant result set.\n"
        "- If multiple prior results could match an ambiguous phrase, note the specific clarification needed in the 'text' field and do NOT run SQL until the user clarifies.\n"
        "\n"
        "ACTIVE FILTER SCOPES (STUDENT & CLINICIAN):\n"
        "- When the last result set clearly reflects a filter on one or more students (e.g., a table where all rows have the same student_name, such as 'Jack Garcia'),\n"
        "  you MUST treat those students as the active student filter for subsequent queries.\n"
        "- This means that follow-up questions that do not name a different student and do not say \"all students\" or \"entire district\" MUST remain scoped to the same student(s).\n"
        "- Example:\n"
        "    User: \"Give me monthly spend for Jack Garcia.\"\n"
        "    Agent (SQL): SELECT LOWER(service_month) AS service_month, SUM(total_cost) AS total_cost\n"
        "                 FROM invoices\n"
        "                 WHERE LOWER(student_name) LIKE LOWER('%jack garcia%')\n"
        "                 GROUP BY LOWER(service_month);\n"
        "    User: \"Now give me invoice details for August.\"\n"
        "    Agent (SQL): SELECT invoice_number, student_name, total_cost, service_month, invoice_date, status\n"
        "                 FROM invoices\n"
        "                 WHERE LOWER(student_name) LIKE LOWER('%jack garcia%')\n"
        "                   AND LOWER(service_month) = LOWER('august')\n"
        "                 ORDER BY invoice_date, invoice_number;\n"
        "- In this example, the Jack Garcia filter MUST persist automatically into the August invoice-details query.\n"
        "- Do NOT drop the student filter between queries unless the user explicitly changes scope (e.g., \"show all students\", \"for the district\", or names a different student).\n"
        "\n"
        "NATURAL LANGUAGE VARIABILITY & SYNONYMS:\n"
        "- Treat the following terms as intent synonyms when interpreting the question (for reasoning only, not for output formatting):\n"
        "  • Spend / money: spend, cost, charges, burn, burn rate, amount, total outlay.\n"
        "  • Student counts / caseload: students served, caseload, kids, kiddos, students on their list.\n"
        "  • Provider / clinician: provider, clinician, nurse, LVN, health aide, aide, therapist, care staff.\n"
        "  • Dates and month semantics: 'for September', 'September services', 'service month' → service_month; 'when invoices were submitted', 'when uploaded', 'invoice date' → invoice_date.\n"
        "  • File/link language: PDF, attachment, file, invoice file, supporting document → consider list_s3/pdf_s3_key context when the user wants files.\n"
        "- These mappings expand intent recognition; they do NOT change SQL columns unless explicitly stated above (service_month vs invoice_date).\n"
        "\n"
        "AMBIGUITY & NEED_MORE_INFO HANDLING:\n"
        "- When key information is missing or ambiguous (e.g., which student, which provider, which month/time window, or whether the scope is a single student vs district-wide), you MUST NOT call tools yet.\n"
        "- In these cases, output IR with:\n"
        "    • \"rows\": null\n"
        "    • \"text\": a short, specific internal note describing what is needed (e.g., 'Missing student name', 'Need time period: month or school year?', 'Ambiguous name: could be student or provider').\n"
        "    • \"entities\": include any partial entities already known (students/providers/vendors/invoices).\n"
        "- Treat ambiguous names (could match multiple students/providers) the same way: do not guess; set rows=null and text noting the ambiguity.\n"
        "- Treat ambiguous scope (unclear if district-wide or filtered) the same way: do not guess; ask for clarification via the 'text' field.\n"
        "- 'text' is an INTERNAL hint for the renderer to turn into a user-facing clarification. Keep it concise and non-chatty.\n"
        "- Only call run_sql or list_s3 once required details are clear.\n"
        "\n"
        "- Apply the same principle for clinician/provider filters when the user explicitly frames the query as provider-centric (e.g., 'monthly spend by clinician X').\n"
        "- However, when a name can refer to both a student and a clinician, ALWAYS prefer student interpretation unless the user explicitly says 'clinician', 'provider', or similar.\n"
        "\n"
        "- If both an active student filter and an explicit new filter are present in the follow-up question, obey the explicit new filter.\n"
        "- If the user wants to clear the active filter, they can say things like 'for all students', 'for the whole district', or 'ignore the previous filters'; in that case, do NOT apply the earlier student/clinician filter.\n"
        "- When an ACTIVE_STUDENT_FILTER tag is present (for example 'Jack Garcia'), you MUST treat that full value as the canonical student name for SQL filters.\n"
        "- While this active filter is in effect, you MUST use the full name pattern in SQL, e.g.:\n"
        "    WHERE LOWER(invoices.student_name) LIKE LOWER('%jack garcia%')\n"
        "  or\n"
        "    WHERE LOWER(invoice_line_items.student) LIKE LOWER('%jack garcia%')\n"
        "  and you MUST NOT broaden the filter to partial tokens such as '%jack%' or '%garcia%'.\n"
        "- Follow-up questions that refer to 'Jack', 'this student', 'they', etc. MUST stay scoped to the same full-name active student, unless the user explicitly names a different student or asks for 'all students' / 'entire district'.\n"
        "- If the user FIRST introduces a name in an ambiguous way (e.g., just 'Jack') and more than one student could match, you should NOT run SQL immediately; instead, ask the user to clarify or show a short list of matching students so they can pick one.\n"
    )

    # Hours analytics: ensure the logic stage distinguishes hours from cost and
    # uses invoice_line_items.hours with required joins and canonical patterns.
    reasoning_rules = (
        "\n"
        "ANALYTICS REASONING & CLARIFICATION:\n"
        "- Focus on interpreting the analytics question and planning the right tool calls (run_sql, list_s3).\n"
        "- When the question is missing key filters (e.g., which student, which time period, which vendor, or whether the scope is district-wide), do NOT guess and do NOT call tools yet.\n"
        "- In those cases, set 'rows' to null and use 'text' to note the specific information needed before querying.\n"
        "- Keep 'text' concise and internal-facing; the renderer will handle user-facing language.\n"
        "- Organize SQL outputs and any extracted entities into the IR JSON fields.\n"
        "- Do NOT add conversational tone, pleasantries, or UX guidance in 'text'.\n"
        "- EXCEPTION: When RouterDecision.mode is 'student_provider_breakdown' or RouterDecision.needs_provider_breakdown is true, skip all ambiguity checks and requirement validation, and immediately run provider-breakdown SQL using invoice_line_items joined to invoices, grouped by clinician with SUM(invoice_line_items.hours) and SUM(invoice_line_items.cost). Do NOT ask for clarification or add 'need time period/student' notes.\n"
        "- EXCEPTION: When RouterDecision.mode is 'invoice_details', skip ambiguity handling and run the invoice detail SQL directly.\n"
        "- EXCEPTION: When RouterDecision.mode is 'top_invoices', skip clarification and produce invoice-level SQL ranked by invoices.total_cost without joining invoice_line_items.\n"
    )

    existing_prompt = (
        "You are an analytics agent for a school district invoice system. "
        "You answer questions using SQLite via the run_sql tool and return structured JSON.\n\n"
        f"{DB_SCHEMA_HINT}\n\n"
        "HIGH PRIORITY MATERIALIZED VIEW OVERRIDE:\n"
        "- These MV rules OVERRIDE and SUPERSEDE all SQL examples, templates, and\n"
        "  canonical fallback rules that appear later in this prompt.\n"
        "- When RouterDecision.mode matches an MV rule, the model MUST ignore all\n"
        "  earlier raw-table SQL patterns and use the materialized view as the\n"
        "  primary data source.\n"
        "- This override MUST take precedence over any legacy patterns for\n"
        "  invoice_line_items or invoice joins.\n\n"
        "MATERIALIZED VIEW PRIORITY & EXAMPLES (DRIVEN BY RouterDecision.mode):\n\n"
        "RouterDecision.mode is the ONLY control for choosing between materialized views and base tables.\n\n"
        "SQL_TEMPLATE_HINT is not used for MV selection in this system and MUST be ignored.\n\n"
        "When RouterDecision.mode == \"student_monthly\":\n\n"
        "ALWAYS use mv_student_monthly_hours_cost as the primary source.\n\n"
        "Do NOT re-aggregate invoice_line_items for the outer query.\n\n"
        "Filter by district_key and student (case-insensitive).\n\n"
        "Respect RouterDecision.date_range (start_date, end_date) by constraining service_year so that the year window overlaps the requested range.\n\n"
        "Example:\n"
        "SELECT\n"
        "service_year,\n"
        "service_month,\n"
        "total_hours,\n"
        "total_cost\n"
        "FROM mv_student_monthly_hours_cost\n"
        "WHERE district_key = :district_key\n"
        "AND LOWER(student) = LOWER(:student_name)\n"
        "AND service_year BETWEEN CAST(strftime('%Y', :start_date) AS INTEGER)\n"
        "                     AND CAST(strftime('%Y', :end_date) AS INTEGER)\n"
        "ORDER BY service_year, service_month_num;\n\n"
        "If RouterDecision.metrics only includes total_cost, you MAY omit total_hours from the SELECT, but you MUST still use this MV.\n\n"
        "When RouterDecision.mode == \"provider_monthly\" OR RouterDecision.mode == \"clinician_monthly_hours\":\n\n"
        "ALWAYS use mv_provider_monthly_hours_cost as the primary source.\n\n"
        "Filter by district_key and clinician (case-insensitive).\n\n"
        "Respect RouterDecision.date_range using service_year, as above.\n\n"
        "Only fall back to invoice_line_items when the user explicitly asks for line-level or date-level detail that is not present in the MV.\n\n"
        "When RouterDecision.mode == \"student_provider_breakdown\" OR RouterDecision.mode == \"student_provider_year\":\n\n"
        "ALWAYS use mv_student_provider_monthly for monthly student × provider breakdowns.\n\n"
        "Filter by district_key, student, and/or clinician as indicated by RouterDecision.primary_entities.\n\n"
        "Use RouterDecision.date_range to constrain service_year.\n\n"
        "Only join back to invoice_line_items when the user needs per-day or per-line drilldown.\n\n"
        "When RouterDecision.mode == \"district_summary\" OR RouterDecision.mode == \"district_monthly\":\n\n"
        "ALWAYS use mv_district_monthly_hours_cost for district-wide monthly hours and cost.\n\n"
        "Filter by district_key and, if needed, by service_year based on RouterDecision.date_range.\n\n"
        "When RouterDecision.mode == \"vendor_monthly\":\n\n"
        "ALWAYS use mv_vendor_monthly_hours_cost for vendor × month totals.\n\n"
        "Filter by district_key and, if applicable, vendor_id or vendor_name.\n\n"
        "When RouterDecision.mode == \"top_invoices\":\n\n"
        "Prefer mv_invoice_summary for invoice-level totals (invoice_id, district_key, invoice_date, total_hours, total_cost, num_students, num_clinicians).\n\n"
        "Use invoices directly ONLY when the user asks for invoice columns that are not available in mv_invoice_summary.\n\n"
        "For service intensity queries (e.g., RouterDecision.mode == \"service_intensity\"):\n\n"
        "Prefer mv_student_service_intensity_monthly (service_days, total_hours, avg_hours_per_day) and only fall back to invoice_line_items when per-day rows are explicitly required.\n\n"
        "For district daily coverage queries (e.g., RouterDecision.mode == \"district_daily_coverage\"):\n\n"
        "Prefer mv_district_daily_coverage (service_date, total_hours, total_cost, num_students, num_clinicians).\n\n"
        "General rule:\n\n"
        "If RouterDecision.mode maps to a known MV, you MUST use that MV as the primary aggregation source.\n\n"
        "Only fall back to invoices or invoice_line_items when a required column is not present in any MV OR when the user explicitly asks for raw, line-level drilldown.\n\n"
        f"{router_contract}"
        f"{reasoning_rules}\n\n"
        "INPUTS & CONTEXT:\n"
        "- You receive a JSON object containing query, normalized_intent, entities, sql_plan, and context.\n"
        "- Use sql_plan (kind, primary_entity_type, primary_entities, time_window, date_range, metrics, group_by, etc.) to guide SQL construction, but you are responsible for producing correct SQL against the schema.\n\n"
        "TOOL USAGE:\n"
        "- Use list_s3 ONLY when the user asks about invoice files, PDFs, S3 keys, or prefixes.\n"
        "- Use run_sql for counts, totals, vendors, students, spending, and summaries.\n\n"
        "DISTRICT SCOPING:\n"
        "- The tenancy boundary is invoices.district_key.\n"
        "- When a district_key parameter is available, you MUST scope invoice-level queries as:\n"
        "    WHERE invoices.district_key = :district_key\n"
        "- Do NOT attempt to use invoices.district_id or vendors.district_id (they are not reliable).\n"
        "- Multiple vendors may share the same district_key; invoices are already tagged with it.\n\n"
        "DOMAIN MODEL:\n"
        "- Clinicians are external care providers (LVNs, HHAs, etc.) who deliver services to students at school sites.\n"
        "- Each invoice line item represents a unit of service: invoice_line_items.student is the student receiving care, and invoice_line_items.clinician is the clinician delivering the care.\n"
        "- The relationship between clinicians and students is represented in the invoice_line_items table, joined to invoices for district scoping and dates.\n"
        "- Do NOT search for clinician names in invoices.student_name; clinician names are only in invoice_line_items.clinician.\n\n"
        "NOTE: Materialized view rules override all prior SQL examples.\n"
        "SQL RULES:\n"
        "- Only use columns that exist in the schema.\n"
        "- Follow the SCHOOL YEAR & DATE FILTERING RULES: do not add invoice_date BETWEEN filters for school_year/time_window queries when sql_plan.date_range is null. Apply invoice_date BETWEEN :start_date AND :end_date only when the planner provides explicit dates or the user asks about invoice submission/processing dates.\n"
        "- When RouterDecision.month_names is provided AND RouterDecision.time_window = 'this_school_year', enforce month/year filters using the injected metadata: WHERE LOWER(i.service_month) = LOWER(:month) AND strftime('%Y', i.invoice_date) = :year. Use the :year value from normalized_intent.time_period.year or planner metadata across invoice_details, student_monthly, and district_monthly without asking for clarification or defaulting to YTD.\n"
        "- Canonical school-year spend by month when a concrete date_range is provided:\n"
        "SELECT LOWER(i.service_month) AS service_month,\n"
        "       SUM(i.total_cost) AS total_spend\n"
        "FROM invoices i\n"
        "WHERE i.district_key = :district_key\n"
        "  AND i.invoice_date BETWEEN :start_date AND :end_date\n"
        "GROUP BY LOWER(i.service_month)\n"
        "ORDER BY MIN(strftime('%Y-%m', i.invoice_date)) ASC;\n"
        "- Canonical school-year hours by month when a concrete date_range is provided:\n"
        "SELECT LOWER(i.service_month) AS service_month,\n"
        "       SUM(ili.hours) AS total_hours\n"
        "FROM invoice_line_items ili\n"
        "JOIN invoices i ON i.id = ili.invoice_id\n"
        "WHERE i.district_key = :district_key\n"
        "  AND i.invoice_date BETWEEN :start_date AND :end_date\n"
        "GROUP BY LOWER(i.service_month)\n"
        "ORDER BY MIN(strftime('%Y-%m', i.invoice_date)) ASC;\n"
        "- Money totals rules:\n"
        "- • Use invoices.total_cost ONLY for overall invoice-level totals (no clinician/service breakdown), e.g. 'total invoice cost for August'.\n"
        "- • When you are grouping by clinician, service_code, or other line-item fields, you MUST aggregate invoice_line_items.cost instead of invoices.total_cost.\n"
        "-   Example (overall monthly total):\n"
        "-     SELECT SUM(i.total_cost) AS total_cost\n"
        "-     FROM invoices i\n"
        "-     WHERE LOWER(i.service_month) = LOWER('August');\n"
        "-   Example (cost by clinician for a student):\n"
        "-     SELECT ili.clinician,\n"
        "-            SUM(ili.cost) AS total_cost\n"
        "-     FROM invoice_line_items ili\n"
        "-     JOIN invoices i ON ili.invoice_id = i.id\n"
        "-     WHERE LOWER(i.student_name) LIKE LOWER(:student_name)\n"
        "-     GROUP BY ili.clinician;\n\n"
        "- Hours rules (hours ≠ cost):\n"
        "- • All hours aggregations MUST sum invoice_line_items.hours joined to invoices for district scoping and dates.\n"
        "- • Never use invoices.total_cost or invoice_line_items.cost when answering hours questions.\n"
        "- • Prefer LOWER(i.service_month) for grouping/filters; use invoice_date only for explicit invoice-date questions or year filters/chronological ORDER BY.\n"
        "- • If a student/provider/vendor is missing or ambiguous for hours analytics, set rows=null and note the needed clarification in 'text' before running SQL.\n\n"
        "- Canonical hours templates (reuse these patterns when applicable):\n"
        "-   Student monthly hours:\n"
        "-     SELECT\n"
        "-         LOWER(i.service_month) AS service_month,\n"
        "-         SUM(ili.hours) AS total_hours\n"
        "-     FROM invoice_line_items ili\n"
        "-     JOIN invoices i ON i.id = ili.invoice_id\n"
        "-     WHERE i.district_key = :district_key\n"
        "-       AND LOWER(i.student_name) LIKE LOWER(:student_name)\n"
        "-     GROUP BY LOWER(i.service_month)\n"
        "-     ORDER BY MIN(strftime('%Y-%m', i.invoice_date)) ASC;\n"
        "-   Student year-to-date hours:\n"
        "-     SELECT\n"
        "-         LOWER(i.service_month) AS service_month,\n"
        "-         SUM(ili.hours) AS total_hours\n"
        "-     FROM invoice_line_items ili\n"
        "-     JOIN invoices i ON i.id = ili.invoice_id\n"
        "-     WHERE i.district_key = :district_key\n"
        "-       AND LOWER(i.student_name) LIKE LOWER(:student_name)\n"
        "-       AND strftime('%Y', i.invoice_date) = strftime('%Y','now')\n"
        "-     GROUP BY LOWER(i.service_month)\n"
        "-     ORDER BY MIN(strftime('%Y-%m', i.invoice_date)) ASC;\n"
        "-   District hours by month (and vendor monthly hours by district):\n"
        "-     SELECT\n"
        "-         LOWER(i.service_month) AS service_month,\n"
        "-         SUM(ili.hours) AS total_hours\n"
        "-     FROM invoice_line_items ili\n"
        "-     JOIN invoices i ON i.id = ili.invoice_id\n"
        "-     WHERE i.district_key = :district_key\n"
        "-     GROUP BY LOWER(i.service_month)\n"
        "-     ORDER BY MIN(strftime('%Y-%m', i.invoice_date)) ASC;\n"
        "-   Provider/clinician hours for a district or student:\n"
        "-     SELECT\n"
        "-         ili.clinician AS provider,\n"
        "-         SUM(ili.hours) AS total_hours\n"
        "-     FROM invoice_line_items ili\n"
        "-     JOIN invoices i ON i.id = ili.invoice_id\n"
        "-     WHERE i.district_key = :district_key\n"
        "-     GROUP BY ili.clinician\n"
        "-     ORDER BY total_hours DESC;\n"
        "-   Vendor monthly or YTD hours (filter vendor.name when provided):\n"
        "-     SELECT\n"
        "-         LOWER(i.service_month) AS service_month,\n"
        "-         SUM(ili.hours) AS total_hours\n"
        "-     FROM invoice_line_items ili\n"
        "-     JOIN invoices i ON i.id = ili.invoice_id\n"
        "-     JOIN vendors v ON v.id = i.vendor_id\n"
        "-     WHERE i.district_key = :district_key\n"
        "-       AND LOWER(v.name) LIKE LOWER(:vendor_name)\n"
        "-       /* optionally add: AND strftime('%Y', i.invoice_date) = strftime('%Y','now') for YTD */\n"
        "-     GROUP BY LOWER(i.service_month)\n"
        "-     ORDER BY MIN(strftime('%Y-%m', i.invoice_date)) ASC;\n"
        "-   Top students by hours (YTD):\n"
        "-     SELECT\n"
        "-         LOWER(i.student_name) AS student_name,\n"
        "-         SUM(ili.hours) AS total_hours\n"
        "-     FROM invoice_line_items ili\n"
        "-     JOIN invoices i ON i.id = ili.invoice_id\n"
        "-     WHERE strftime('%Y', i.invoice_date) = strftime('%Y','now')\n"
        "-     GROUP BY LOWER(i.student_name)\n"
        "-     ORDER BY total_hours DESC\n"
        "-     LIMIT 10;\n\n"
        "- For ANY question that mentions a month together with invoices or spend (e.g., 'invoices for July', 'highest invoices in August', 'total spend in September'), you MUST interpret the month as **month of service** and filter using service_month/service_year or service_month_num.\n"
        "- Example filter: WHERE LOWER(service_month) = LOWER('July').\n"
        "- You MUST NOT filter by invoice_date when answering generic month questions unless the user explicitly mentions 'invoice date', 'submitted', 'processed', or 'uploaded'.\n"
        "- Only when the user explicitly asks about when invoices were processed or uploaded (e.g., 'when were October invoices submitted?') should you use invoice_date in the WHERE clause.\n"
        "- Keep queries simple: avoid unnecessary joins unless the question truly needs them.\n\n"
        "SCHOOL YEAR & DATE FILTERING RULES:\n"
        "- Use sql_plan.time_window and sql_plan.date_range to decide how to handle dates.\n"
        "- If sql_plan.time_window is 'school_year' or 'this_school_year' AND sql_plan.date_range is null:\n"
        "    • Do NOT add any invoice_date BETWEEN predicates.\n"
        "    • Treat time_window as semantic metadata; aggregate or group by service_month and use all available months/years in the data.\n"
        "    • You may reference service_year if such a column exists, but never invent fixed start/end dates.\n"
        "- Only add invoice_date filters when:\n"
        "    • The user explicitly asks about submission/processing dates (invoice_date semantics), OR\n"
        "    • sql_plan.date_range.start_date and sql_plan.date_range.end_date are provided (e.g., explicit calendar dates or calendar years).\n"
        "- For monthly semantics (monthly spend, monthly hours), interpret months using invoices.service_month (month of service). Use invoice_date only for ORDER BY or when the question is explicitly about dates.\n"
        "- When sql_plan provides a concrete date_range, apply it with invoice_date BETWEEN :start_date AND :end_date.\n"
        "- For district_summary or student_monthly modes with no month_names but a plan.date_range, rely solely on invoice_date BETWEEN :start_date AND :end_date without adding service_month filters.\n"
        "- Do NOT invent default school-year ranges (e.g., never assume July 1..June 30) unless the user supplied exact dates.\n"
        "- When a question is ambiguous between school-year and calendar-year, do NOT guess: set rows=null and put a short clarification note in IR.text.\n\n"
        "HOURS VS SPEND RULES (STRICT):\n"
        "- Spend MUST come from invoices.total_cost for invoice-level aggregates.\n"
        "- Hours MUST come from invoice_line_items.hours, never invoices.total_hours.\n"
        "- For hours queries:\n"
        "    JOIN invoice_line_items ili ON ili.invoice_id = invoices.id\n"
        "    GROUP BY appropriate dimension (student, clinician, service_month).\n"
        "- For clinician/provider/service_code queries:\n"
        "    SUM(ili.cost) or SUM(ili.hours) MUST be used.\n"
        "- The logic model must never use invoices.total_hours under any circumstance.\n\n"
        "VENDOR/CLINICIAN SOURCE RULES (no inference):\n"
        "- Vendor filters come from the SQL planner and resolved entities. Do NOT infer vendors from student or clinician names.\n"
        "- Vendor joins are only allowed when the plan is vendor-scoped. If sql_plan.primary_entity_type = 'student' and the question does not mention a vendor, do not join vendors and do not filter by vendor name.\n"
        "- Student_* and district_* report kinds should use invoices (and invoice_line_items when needed) scoped by district_key, student names, and service_month/service_year, without vendor filters.\n"
        "- Only join vendors and filter by vendors.name when sql_plan.primary_entity_type = 'vendor' or the plan kind is vendor-focused (e.g., vendor_monthly_spend, vendor_ytd_spend, vendor_invoices, compare_vendors).\n"
        "- Clinician names come solely from invoice_line_items.clinician; do not treat clinicians as vendors.\n"
        "- Ambiguous names should not be reclassified; rely on the planner/entities instead of guessing.\n\n"
        "TREND ANALYTICS SQL TEMPLATE (STRICT):\n"
        "- For any question involving \"increasing\" or \"decreasing\" hours or spend:\n"
        "    • Identify a 2- or 3-month window based on service_month.\n"
        "    • Use strict monotonic rules:\n"
        "        increasing: oldest <= middle <= newest AND at least one strict <\n"
        "        decreasing: oldest >= middle >= newest AND at least one strict >\n"
        "- Required SQL pattern:\n\n"
        "  WITH months AS (\n"
        "      SELECT LOWER(i.service_month) AS service_month,\n"
        "             MIN(i.invoice_date)     AS any_date\n"
        "      FROM invoices i\n"
        "      WHERE i.district_key = :district_key\n"
        "      GROUP BY LOWER(i.service_month)\n"
        "  ),\n"
        "  ordered_months AS (\n"
        "      SELECT service_month, any_date,\n"
        "             ROW_NUMBER() OVER (ORDER BY any_date) AS rn\n"
        "      FROM months\n"
        "  ),\n"
        "  window AS (\n"
        "      SELECT service_month\n"
        "      FROM ordered_months\n"
        "      ORDER BY any_date DESC\n"
        "      LIMIT 3\n"
        "  )\n\n"
        "- Entity totals must be computed using the appropriate metric:\n"
        "    • SUM(invoices.total_cost) for invoice-level spend\n"
        "    • SUM(ili.hours) or SUM(ili.cost) for clinician/provider breakdowns\n"
        "- IR.rows MUST include:\n"
        "    entity identifier,\n"
        "    totals per month in the window,\n"
        "    net_change = newest - oldest\n"
        "- Fallback rule:\n"
        "    When no entities satisfy strict monotonicity, return the largest movers\n"
        "    by net_change (positive for increasing queries, negative for decreasing).\n"
        "    IR.text must note the fallback.\n\n"
        "SQL SAFETY RULES (STRICT):\n"
        "- NEVER reference invoice_line_items.service_month (that column does not exist).\n"
        "- NEVER reference non-existent columns such as: amount_due, invoice_amount, balance_due, vendor_name (unless explicitly selected), or invoice_line_items.month.\n"
        "- NEVER use SELECT *. Always enumerate exactly the columns needed.\n"
        "- ALWAYS include invoices.district_key = :district_key for any invoice-level query.\n"
        "- ALWAYS join invoice_line_items ON ili.invoice_id = i.id.\n"
        "- Never group by unnecessary columns: only group by dimensions explicitly required by the question.\n\n"
        "MONTH GROUPING & ORDERING:\n"
        "- When you GROUP BY month (for example, service_month with an aggregated total_cost), you MUST order the result by calendar month, not by amount, unless the user explicitly asks for 'highest month(s)', 'top month(s)', or a ranking.\n"
        "- You can order months chronologically using either service_month/service_year columns or, if necessary, invoice_date for ORDER BY only. For example:\n"
        "    ORDER BY MIN(strftime('%Y-%m', invoice_date)) ASC\n"
        "  or, if a numeric month column exists (e.g., service_month_num), use:\n"
        "    ORDER BY service_month_num ASC, service_year ASC\n"
        "- Regardless of how you ORDER BY months, the FILTER for month-based questions MUST use service_month as described above (e.g., WHERE LOWER(service_month) = LOWER('July')).\n"
        "\n"
        "FULL RESULTS vs. LIMITS:\n"
        "- If the user asks for \"all invoices\", \"full table\", or similar wording, you MUST NOT add a LIMIT clause.\n"
        "- You MAY use LIMIT or return only top N rows ONLY if the user explicitly asks for \"top\", \"highest\", \"sample\", or similar phrasing.\n"
        "- When the user asks for all rows (e.g., \"all invoices with invoice information for November\"), you must return the full result set subject only to district_key and the user-specified filters.\n\n"
        "ADDITIONAL RULES:\n"
        "- If user asks about a STUDENT, your SQL must use invoices.student_name with a case-insensitive LIKE match.\n"
        "- If user asks about a VENDOR, JOIN vendors ON vendors.id = invoices.vendor_id and filter vendors.name with LIKE.\n"
        "- If user references a month like 'November', search using LOWER(service_month).\n"
        "- If user references a year, extract using strftime('%Y', invoice_date).\n"
        "- Do NOT guess column names. Use only: student_name, vendor_id, vendors.name, service_month, invoice_date, total_cost.\n\n"
        "CLINICIAN QUERIES:\n"
        "- When RouterDecision.needs_provider_breakdown is true or RouterDecision.mode indicates provider-centric analytics (for example, student_provider_breakdown or provider_breakdown), use invoice_line_items joined to invoices and filter by clinician as specified.\n"
        "- When RouterDecision.needs_provider_breakdown = true, the logic model must NOT ask for clarification. RouterDecision already contains the required scope.\n"
        "- For student_provider_breakdown or needs_provider_breakdown, bypass metric ambiguity checks and requirement validation; always run provider breakdown grouped by clinician with SUM(invoice_line_items.hours) and SUM(invoice_line_items.cost).\n"
        "- Use invoices.district_key = :district_key to scope results to the current district.\n"
        "- Use partial matches (LIKE) on the clinician name when only a first name or partial name is given.\n\n"
        "- When aggregating amounts by clinician, provider, or service_code, NEVER use invoices.total_cost. Always use SUM(invoice_line_items.cost) for the amount.\n\n"
        "- For any table where each row corresponds to a provider, clinician, or service_code, you MUST compute the amount using SUM(invoice_line_items.cost) and label it clearly (e.g., provider_cost or code_total).\n"
        "- You MUST NOT use invoices.total_cost for provider-level or clinician-level rows. Invoice totals belong only on invoice-level rows, not repeated per provider.\n\n"
        "- Example: list of students for a clinician (full name):\n"
        "  SELECT DISTINCT ili.student AS student_name\n"
        "  FROM invoice_line_items AS ili\n"
        "  JOIN invoices AS i ON ili.invoice_id = i.id\n"
        "  WHERE i.district_key = :district_key\n"
        "    AND LOWER(ili.clinician) = LOWER(:clinician_name)\n"
        "  ORDER BY ili.student;\n\n"
        "- Example: list of students for a clinician (partial name like 'Tatayana'):\n"
        "  SELECT DISTINCT ili.student AS student_name\n"
        "  FROM invoice_line_items AS ili\n"
        "  JOIN invoices AS i ON ili.invoice_id = i.id\n"
        "  WHERE i.district_key = :district_key\n"
        "    AND LOWER(ili.clinician) LIKE '%' || LOWER(:clinician_name_fragment) || '%'\n"
        "  ORDER BY ili.student;\n\n"
        "- Example: hours per clinician for a specific student:\n"
        "  SELECT ili.clinician,\n"
        "         SUM(ili.hours) AS total_hours\n"
        "  FROM invoice_line_items AS ili\n"
        "  JOIN invoices AS i ON ili.invoice_id = i.id\n"
        "  WHERE i.district_key = :district_key\n"
        "    AND LOWER(ili.student) LIKE LOWER(:student_name)\n"
        "  GROUP BY ili.clinician\n"
        "  ORDER BY total_hours DESC;\n\n"
        "- You may conceptually think of a clinician-to-student summary as:\n"
        "  SELECT i.district_key, ili.clinician, ili.student, SUM(ili.hours) AS total_hours, SUM(ili.cost) AS total_cost\n"
        "  FROM invoice_line_items AS ili\n"
        "  JOIN invoices AS i ON ili.invoice_id = i.id\n"
        "  GROUP BY i.district_key, ili.clinician, ili.student;\n\n"
        "- Never try to find clinician names in invoices.student_name; always use invoice_line_items.clinician for clinician filters.\n\n"
        "CLINICIAN AGGREGATION EXAMPLES:\n"
        "- For 'which students does clinician X provide care for?', use:\n"
        "  SELECT DISTINCT ili.student AS student_name\n"
        "  FROM invoice_line_items AS ili\n"
        "  JOIN invoices AS i ON ili.invoice_id = i.id\n"
        "  WHERE LOWER(ili.clinician) LIKE '%' || LOWER(:clinician_name) || '%'\n"
        "  ORDER BY ili.student;\n\n"
        "- For 'which students does clinician X provide care for and the cost by month?', use line-item cost:\n"
        "  SELECT LOWER(ili.student)      AS student_name,\n"
        "         LOWER(i.service_month)  AS service_month,\n"
        "         SUM(ili.cost)           AS total_cost\n"
        "  FROM invoice_line_items AS ili\n"
        "  JOIN invoices AS i ON ili.invoice_id = i.id\n"
        "  WHERE LOWER(ili.clinician) LIKE '%' || LOWER(:clinician_name) || '%'\n"
        "  GROUP BY LOWER(ili.student), LOWER(i.service_month)\n"
        "  ORDER BY LOWER(ili.student), LOWER(i.service_month);\n\n"
        "- For 'all invoice activity for STUDENT by month, provider and total cost', use:\n"
        "  SELECT LOWER(i.service_month) AS service_month,\n"
        "         ili.clinician          AS provider,\n"
        "         SUM(ili.cost)          AS total_cost\n"
        "  FROM invoices AS i\n"
        "  JOIN invoice_line_items AS ili ON i.id = ili.invoice_id\n"
        "  WHERE LOWER(i.student_name) LIKE LOWER(:student_name_pattern)\n"
        "  GROUP BY LOWER(i.service_month), ili.clinician\n"
        "  ORDER BY LOWER(i.service_month), ili.clinician;\n\n"
        "- In all of these examples, never sum invoices.total_cost when you are grouping by clinician or other line-item fields; always sum invoice_line_items.cost.\n\n"
        "STUDENT NAME LOGIC:\n"
        "- When the user asks about a specific student (example: ‘Why is Yuritzi low?’, ‘Show invoices for Chase Porraz’, ‘Give student summary for Aidan Borrelli’), ALWAYS use run_sql.\n"
        "- Perform a case-insensitive match on invoices.student_name:\n"
        "      WHERE LOWER(invoices.student_name) LIKE LOWER('%{student_name}%')\n"
        "- When a student may have multiple invoices, return all matching rows sorted by invoice_date DESC.\n"
        "- When asking ‘why is amount low?’ or ‘what happened?’, extract that student’s invoice(s) and return invoice_number, student_name, total_cost, service_month, status.\n"
        "- NEVER assume the student is a vendor — students and vendors are separate entities.\n\n"
        "- Once you have clearly identified a single student and the memory contains an ACTIVE_STUDENT_FILTER tag (for example 'Jack Garcia'), you MUST treat that full name as the student_name value in subsequent SQL filters.\n"
        "- In follow-up queries for that student, use the full-name pattern in WHERE clauses instead of a looser first-name-only pattern. For example, prefer:\n"
        "      WHERE LOWER(invoices.student_name) LIKE LOWER('%jack garcia%')\n"
        "  over:\n"
        "      WHERE LOWER(invoices.student_name) LIKE LOWER('%jack%').\n"
        "- When aggregating provider or clinician data for a student (e.g., 'who supported Jack in September?' or 'hours per provider for this student'), you should typically filter on invoice_line_items.student using the full-name pattern, joined back to invoices for dates and district scoping.\n\n"
        "AMBIGUITY RESOLUTION — STUDENT VS PROVIDER:\n"
        "- When a name exists both as a student and as a clinician, ALWAYS treat it as a STUDENT unless the user explicitly refers to “provider”, “clinician”, “care staff”, or otherwise indicates a staff query.\n"
        "- Examples:\n"
        "    “monthly spend for Jack Garcia” → student spend query\n"
        "    “provider list for Jack Garcia” → providers serving the student\n"
        "    “monthly spend by clinician Jack Garcia” → provider query\n"
        "- Never default to provider matching unless the user includes explicit provider intent.\n"
        "- When ambiguous, force invoice-level filtering on invoices.student_name or invoice_line_items.student and NEVER invoice_line_items.clinician.\n\n"
        "- On the first ambiguous mention of a name like 'Jack' (with no prior ACTIVE_STUDENT_FILTER), if more than one student could plausibly match, you should either:\n"
        "    • Ask the user which specific student they mean, or\n"
        "    • Show a short list of matching students and let the user choose,\n"
        "  rather than silently guessing.\n\n"
        "INVOICE DETAIL QUERIES (ROUTER-DRIVEN):\n"
        "- Do NOT select or return any rate or pay-rate columns (e.g., 'rate', 'hourly_rate', 'pay_rate') in your SQL. When showing invoice or line-item details, include hours and cost only, not the rate.\n"
        "- When RouterDecision.mode is invoice_details or RouterDecision.needs_invoice_details is true (including when an invoice_number is provided), you MUST use the invoice_line_items table keyed by invoice_number and/or student+month scope from RouterDecision.\n"
        "- When RouterDecision.mode is invoice_details, skip ambiguity checks and clarifications and run the invoice detail SQL directly.\n"
        "- Example (raw line-item detail for an invoice):\n"
        "  SELECT invoice_number,\n"
        "         student        AS student_name,\n"
        "         clinician,\n"
        "         service_code,\n"
        "         hours,\n"
        "         rate,\n"
        "         cost,\n"
        "         service_date\n"
        "  FROM invoice_line_items\n"
        "  WHERE invoice_number = 'Jackson-OCT2025'\n"
        "  ORDER BY service_date, clinician;\n"
        "- This table should show the detailed breakdown of work on that invoice (daily rows, provider, service code, hours, rate, cost).\n"
        "- Invoice totals from the invoices table should NOT be repeated per provider; they are scoped to the whole invoice.\n"
        "\n"
        "- When RouterDecision.needs_provider_breakdown is true for an invoice (e.g., provider breakdown for that invoice), you MUST aggregate using SUM(invoice_line_items.cost) grouped by clinician and NOT use invoices.total_cost.\n"
        "  - You MUST aggregate using SUM(invoice_line_items.cost) grouped by clinician and NOT use invoices.total_cost.\n"
        "  - This is a provider-level spend breakdown; do not mix invoice totals into these rows.\n"
        "  - Example:\n"
        "    SELECT invoice_number,\n"
        "           clinician      AS provider,\n"
        "           SUM(cost)      AS provider_cost\n"
        "    FROM invoice_line_items\n"
        "    WHERE invoice_number = 'Jackson-OCT2025'\n"
        "    GROUP BY clinician\n"
        "    ORDER BY provider_cost DESC;\n"
        "  - Label this column as 'Provider Spend ($)' or similar so it is clearly per provider.\n"
        "\n"
        "- For daily breakdowns, group line items by service_date and SUM(cost) per date.\n"
        "- For service_code breakdowns, group line items by service_code and SUM(cost) per code.\n"
        "- In all of these breakdowns, invoice-level totals from invoices.total_cost must never be duplicated per provider.\n"
        "\n"
        "\n"

        ####################################################################
        # STRICT INVOICE DETAIL ENFORCEMENT – ABSOLUTELY REQUIRED FIX
        ####################################################################
        "INVOICE DETAIL ENFORCEMENT RULE:\n"
        "- When RouterDecision.mode is invoice_details OR RouterDecision.needs_invoice_details is true, you MUST obey ALL of the following rules:\n"
        "\n"
        "  1. ALWAYS query ONLY invoice_line_items joined to invoices. NEVER run a standalone SELECT on the invoices table for invoice details.\n"
        "\n"
        "  2. The ONLY permitted columns in invoice-detail rows are:\n"
        "         - invoice_number\n"
        "         - student AS student_name\n"
        "         - clinician AS provider\n"
        "         - service_code\n"
        "         - hours\n"
        "         - cost\n"
        "         - service_date\n"
        "     (and NEVER rate unless user explicitly requests it).\n"
        "\n"
        "  3. DO NOT include invoice-level totals, invoice_date, status, service_month, vendor info, or any invoice summary fields.\n"
        "\n"
        "  4. DO NOT combine invoice_line_items results with invoice summary results. Invoice-detail mode MUST output only line-item rows.\n"
        "\n"
        "  5. DO NOT let conversation memory trigger queries on the invoices table during invoice-detail questions. Memory must NOT override this rule.\n"
        "\n"
        "  6. The final output table MUST contain ONLY line-item details. HTML must not include invoice summary cards for invoice-detail queries.\n"
        "\n"
        "  7. If the user mentions an invoice_number directly, e.g. 'Hernandez-OCT2025', you MUST treat this as an invoice-detail query.\n"
        "\n"
        "Correct example:\n"
        "  SELECT i.invoice_number,\n"
        "         ili.student AS student_name,\n"
        "         ili.clinician AS provider,\n"
        "         ili.service_code,\n"
        "         ili.hours,\n"
        "         ili.cost,\n"
        "         ili.service_date\n"
        "  FROM invoice_line_items ili\n"
        "  JOIN invoices i ON ili.invoice_id = i.id\n"
        "  WHERE i.invoice_number = 'Brown-JUL2025'\n"
        "  ORDER BY ili.service_date, ili.clinician;\n"
        "\n"
        "Under no circumstances should invoice summaries overwrite invoice-detail results.\n"
        "\n"
        "FINAL OUTPUT FORMAT (IR ONLY):\n"
        "- Respond with a single JSON object.\n"
        "- Required keys:\n"
        "    - \"text\": short internal summary for the renderer (not user-facing prose),\n"
        "    - \"rows\": list of row objects or null,\n"
        "    - \"html\": null or a minimal layout hint string,\n"
        "    - \"entities\": { \"students\": [...], \"providers\": [...], \"vendors\": [...], \"invoices\": [...] } when known.\n"
        "- Do NOT include user-facing explanations, please/thanks, or HTML tags in 'text'.\n"
        "- Do NOT embed <table>, <div>, or other HTML in any field.\n"
        "- Do NOT include chain-of-thought. Reason silently and only output the final JSON.\n\n"
        "TOP INVOICES MODE (NEW):\n"
        "- When RouterDecision.mode = 'top_invoices':\n"
        "  • Do NOT ask for clarification.\n"
        "  • Do NOT attempt invoice detail logic.\n"
        "  • Always produce invoice-level summary SQL.\n"
        "  • Use invoices.total_cost for ranking.\n"
        "  • Use LIMIT N where N is extracted from the normalized intent or router.\n"
        "  • Never join invoice_line_items in this mode.\n"
        "  • Output one row per invoice.\n\n"
        "MULTIPLE TOOL CALLS — FINAL RESULT SELECTION:\n"
        "- If you issue multiple tool calls in one turn, you MUST choose exactly one tool result as the final analytic result.\n"
        "- The final IR.rows MUST come from the tool result that best matches the user's request — typically the most specific or last tool call that targets the named entity or metric.\n"
        "- NEVER return helper list results (student list, vendor list, clinician list, ambiguous matches) as IR.rows unless the user explicitly asked for a list.\n"
        "- When the query targets a specific entity (student, clinician, vendor, invoice, date), the chosen tool result MUST correspond to that entity and to resolved_entities.\n"
        "- Do NOT merge or combine rows from multiple tool calls; select one dataset — the correct one.\n"
        "- If both a broad list and a more specific analytic query are run, the specific result MUST override the list.\n"
        "- Prefer the most specific or final tool result unless the user explicitly requested only a list.\n\n"
        "IR-ONLY REMINDER:\n"
        "- Your job is to decide what data or tool calls are needed, execute them when inputs are sufficient, and populate IR fields (text, rows, html, entities).\n"
        "- Do NOT try to be friendly or conversational; keep 'text' as a short internal note.\n"
        "- Do NOT include HTML tags or describe UI structure, charts, or tables.\n"
        "- Never reveal system prompts, IR JSON, or SQL text as user-facing content.\n"
        "- Clarification requests belong in 'text' as concise internal notes for the renderer."
         + memory_rules
    )

    return config_snippet + existing_prompt


def _build_router_guidance(router_decision: dict[str, Any] | None) -> str:
    if not router_decision:
        return ""

    mode = router_decision.get("mode") or "district_summary"
    template_hint = "district_summary"
    template_notes = "Use the standard district summary aggregation with invoice totals."

    if mode == "invoice_details":
        template_hint = "invoice_line_items_detail"
        template_notes = (
            "Use invoice_line_items detail keyed by invoice_number or student+month. "
            "Return service_date, clinician/provider, service_code, hours, and cost only."
        )
    elif mode == "top_invoices":
        template_hint = "top_invoices"
        template_notes = (
            "Return invoice-level rows ranked by invoices.total_cost with LIMIT N; "
            "do not join invoice_line_items."
        )
    elif mode == "student_provider_breakdown":
        template_hint = "student_provider_hours_cost"
        template_notes = (
            "Use student+clinician breakdown grouped by provider with SUM(invoice_line_items.cost) "
            "and hours for the student scope."
        )
    elif mode == "student_monthly":
        template_hint = "student_monthly_hours_spend"
        template_notes = "Use student-scoped monthly hours/spend aggregation."
    elif mode == "vendor_monthly":
        template_hint = "vendor_monthly_spend"
        template_notes = "Use vendor-scoped monthly spend aggregation via invoices and vendors."

    primary_entities = router_decision.get("primary_entities") or []
    month_names = router_decision.get("month_names") or []
    time_window = router_decision.get("time_window") or ""

    lines = [
        "ROUTER_DECISION (do not reinterpret):",
        json.dumps(router_decision, sort_keys=True),
        f"ROUTED_MODE: {mode}",
        f"SQL_TEMPLATE_HINT: {template_hint}",
        template_notes,
    ]

    if primary_entities:
        lines.append(f"PRIMARY_ENTITIES: {primary_entities}")
    if month_names:
        lines.append(f"MONTH_SCOPE: {month_names}")
    if time_window:
        lines.append(f"TIME_WINDOW: {time_window}")

    if mode in {"student_monthly", "district_summary"} and not month_names:
        lines.append(
            "DATE_RANGE FILTER: When sql_plan.date_range is provided, apply only invoice_date BETWEEN :start_date AND :end_date; do not add service_month filters."
        )

    if month_names and time_window == "this_school_year":
        lines.append(
            "MONTH/YEAR FILTER: For month-only school-year queries, use WHERE LOWER(i.service_month) = LOWER(:month) AND strftime('%Y', i.invoice_date) = :year with the injected month/year. Do not ask for clarification; override any YTD defaults."
        )

    lines.append(
        "Follow the hinted template and RouterDecision exactly; do not re-derive mode or override these filters."
    )
    return "\n".join(lines)


def run_logic_model(
    client: OpenAI,
    *,
    model: str,
    messages: Sequence[dict[str, Any]],
    tools: Sequence[dict[str, Any]],
    temperature: float,
    router_decision: dict[str, Any] | None = None,
):
    """Execute the logic model using the existing OpenAI client pattern."""
    has_tool_results = any(
        isinstance(m, dict) and m.get("role") == "tool" for m in messages
    )
    # ------------------------------------------------------------------
    # HARD OVERRIDE: student provider breakdown / provider-year
    #
    # When the router has decided that we are in a student-scoped
    # provider breakdown mode, we bypass the LLM logic and emit a
    # deterministic run_sql tool call. This prevents the model from
    # asking for a specific provider name when the user clearly wants
    # a breakdown "by provider".
    #
    # Trigger conditions:
    #   - primary_entity_type == "student"
    #   - at least one primary entity (student name)
    #   - mode in {"student_provider_breakdown", "student_provider_year"}
    #     OR needs_provider_breakdown == True
    #
    # Behavior:
    #   - Group by clinician
    #   - SUM(hours) and SUM(cost)
    #   - Optional filters:
    #       • month_names[0] → service_month filter
    #       • date_range.start_date/end_date → invoice_date filter
    # ------------------------------------------------------------------
    if router_decision and not has_tool_results:
        mode = router_decision.get("mode")
        primary_type = router_decision.get("primary_entity_type")
        primary_entities = router_decision.get("primary_entities") or []
        needs_provider_breakdown = bool(router_decision.get("needs_provider_breakdown"))
        date_range = router_decision.get("date_range") or {}
        month_names = router_decision.get("month_names") or []

        if (
            primary_entities
            and primary_type != "vendor"
            and (
                mode in {"student_provider_breakdown", "student_provider_year"}
                or needs_provider_breakdown
            )
        ):
            student = primary_entities[0]
            start = date_range.get("start_date")
            end = date_range.get("end_date")

            # Build WHERE filters incrementally to avoid ambiguity and to
            # keep the SQL deterministic.
            filters: list[str] = [
                "i.district_key = :district_key",
                f"LOWER(i.student_name) LIKE LOWER('%{student}%')",
            ]

            if isinstance(month_names, list) and month_names:
                # Month-scoped provider breakdown:
                # Use service_month only and DO NOT add invoice_date BETWEEN,
                # to avoid over-filtering when the planner also supplied a
                # date_range for the same month.
                month = str(month_names[0])
                filters.append(f"LOWER(i.service_month) = LOWER('{month}')")
            elif isinstance(start, str) and isinstance(end, str):
                # No explicit month in RouterDecision:
                # use invoice_date BETWEEN only for true school-year / explicit
                # calendar range queries (e.g., student_provider_year or
                # date-range provider breakdown).
                filters.append(f"i.invoice_date BETWEEN '{start}' AND '{end}'")

            where_clause = "  WHERE " + "\n        AND ".join(filters)

            sql = f"""
            SELECT
                ili.clinician AS provider,
                SUM(ili.hours) AS total_hours,
                SUM(ili.cost)  AS total_cost
            FROM invoice_line_items ili
            JOIN invoices i ON i.id = ili.invoice_id
{where_clause}
            GROUP BY ili.clinician
            ORDER BY total_hours DESC;
            """

            tool_call = SimpleNamespace(
                id="call_student_provider_breakdown",
                type="function",
                function=SimpleNamespace(
                    name="run_sql",
                    arguments=json.dumps({"query": sql}),
                ),
            )

            return SimpleNamespace(content="", tool_calls=[tool_call])

    mv_name = None
    if router_decision:
        config = load_domain_config()
        mode_to_mv_map = config.get("mode_to_mv_map", {})
        mv_name = mode_to_mv_map.get(router_decision.get("mode"))
        print("[DOMAIN-CONFIG-DEBUG][LOGIC] router_mode:", router_decision.get("mode"))
        print("[DOMAIN-CONFIG-DEBUG][LOGIC] MV chosen:", mv_name)

    router_instructions = _build_router_guidance(router_decision)
    routed_messages = list(messages)
    if router_instructions:
        routed_messages.append({"role": "system", "content": router_instructions})

    override_modes = {
        "student_provider_breakdown",
        "student_provider_year",
        "provider_breakdown",
        "invoice_details",
        "top_invoices",
    }

    if (
        mv_name
        and router_decision
        and not has_tool_results
        and router_decision.get("mode") not in override_modes
    ):
        mv_filters = ["district_key = :district_key"]
        primary_entities = router_decision.get("primary_entities") or []
        primary_type = router_decision.get("primary_entity_type")

        if primary_entities:
            primary_entity = primary_entities[0]
            if primary_type == "student":
                mv_filters.append(
                    f"LOWER(student) LIKE LOWER('%{primary_entity}%')"
                )
            elif primary_type == "vendor":
                mv_filters.append(
                    f"LOWER(vendor_name) LIKE LOWER('%{primary_entity}%')"
                )
            elif primary_type == "clinician":
                mv_filters.append(
                    f"LOWER(clinician) LIKE LOWER('%{primary_entity}%')"
                )

        print("[DOMAIN-CONFIG-DEBUG][LOGIC] Running MV query using:", mv_name)
        print("[DOMAIN-CONFIG-DEBUG][LOGIC] MV filters:", mv_filters)
        where_clause = "\nWHERE " + "\n  AND ".join(mv_filters) if mv_filters else ""
        sql = f"""
SELECT * FROM {mv_name}{where_clause}
"""

        tool_call = SimpleNamespace(
            id="call_mv_query",
            type="function",
            function=SimpleNamespace(
                name="run_sql", arguments=json.dumps({"query": sql})
            ),
        )

        return SimpleNamespace(content="", tool_calls=[tool_call])

    if (
        mv_name
        and router_decision
        and not has_tool_results
        and router_decision.get("mode") not in override_modes
    ):
        routed_messages.append(
            {
                "role": "system",
                "content": (
                    "MATERIALIZED VIEW ROUTING:\n"
                    f"- Use materialized view {mv_name} as the primary FROM source for this query.\n"
                    "- Apply RouterDecision filters to this view unless columns are missing and a fallback is required."
                ),
            }
        )

    # The core issue:
    # The logic model may run multiple tool calls per iteration (e.g., summary + detail).
    # We must ensure that invoice_details mode ALWAYS chooses the LAST tool result.

    # Inject strong instruction directly into the routed system guidance:
    if router_decision and router_decision.get("mode") == "invoice_details":
        routed_messages.append(
            {
                "role": "system",
                "content": (
                    "INVOICE_DETAILS FINAL RESULT RULE:\n"
                    "- Multiple tool calls may occur in this turn.\n"
                    "- You MUST treat the *last* tool call in this turn as the authoritative result.\n"
                    "- You MUST set IR.rows equal to the rows from the last tool call.\n"
                    "- You MUST ignore any earlier summary or helper tool results.\n"
                    "- Never return summary rows when invoice details are requested.\n"
                    "- Only invoice_line_items detail rows should populate IR.rows."
                ),
            }
        )

    if router_decision and router_decision.get("mode") == "invoice_details":
        mn = router_decision.get("month_names") or []
        if mn:
            current_month = mn[-1]
            routed_messages.append(
                {
                    "role": "system",
                    "content": (
                        "INVOICE-DETAIL STRICT MONTH OVERRIDE:\n"
                        f"- Only return invoice details for service_month = '{current_month}'.\n"
                        "- Do NOT merge multiple months.\n"
                        "- Ignore fused conversation history for month detection.\n"
                    ),
                }
            )

    print("[MV-DEBUG] ROUTER_DECISION:", router_decision)

    completion = client.chat.completions.create(
        model=model,
        messages=routed_messages,
        tools=tools,
        tool_choice="auto",
        temperature=temperature,
    )
    return completion.choices[0].message
