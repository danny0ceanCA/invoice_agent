1. mv_student_monthly_hours_cost
Description

Source: invoices, invoice_line_items

Purpose: Student hours + cost per month (per district, year, month).

SQLite
DROP TABLE IF EXISTS mv_student_monthly_hours_cost;

CREATE TABLE mv_student_monthly_hours_cost AS
SELECT
    i.district_key                             AS district_key,
    LOWER(ili.student)                         AS student,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_smhc_dk_year_month;
DROP INDEX IF EXISTS idx_mv_smhc_lower_student;

CREATE INDEX idx_mv_smhc_dk_year_month
    ON mv_student_monthly_hours_cost (district_key, service_year, service_month_num);

CREATE INDEX idx_mv_smhc_lower_student
    ON mv_student_monthly_hours_cost (student);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_student_monthly_hours_cost;

CREATE MATERIALIZED VIEW mv_student_monthly_hours_cost AS
SELECT
    i.district_key                                  AS district_key,
    LOWER(ili.student)                              AS student,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_smhc_dk_year_month
    ON mv_student_monthly_hours_cost (district_key, service_year, service_month_num);

CREATE INDEX IF NOT EXISTS idx_mv_smhc_lower_student
    ON mv_student_monthly_hours_cost (student);

-- Refresh
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_student_monthly_hours_cost;

2. mv_provider_monthly_hours_cost
Description

Source: invoices, invoice_line_items

Purpose: Clinician hours + cost per month.

SQLite
DROP TABLE IF EXISTS mv_provider_monthly_hours_cost;

CREATE TABLE mv_provider_monthly_hours_cost AS
SELECT
    i.district_key                             AS district_key,
    LOWER(ili.clinician)                       AS clinician,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.clinician),
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_pmhc_dk_year_month;
DROP INDEX IF EXISTS idx_mv_pmhc_lower_clinician;

CREATE INDEX idx_mv_pmhc_dk_year_month
    ON mv_provider_monthly_hours_cost (district_key, service_year, service_month_num);

CREATE INDEX idx_mv_pmhc_lower_clinician
    ON mv_provider_monthly_hours_cost (clinician);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_provider_monthly_hours_cost;

CREATE MATERIALIZED VIEW mv_provider_monthly_hours_cost AS
SELECT
    i.district_key                                  AS district_key,
    LOWER(ili.clinician)                            AS clinician,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.clinician),
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_pmhc_dk_year_month
    ON mv_provider_monthly_hours_cost (district_key, service_year, service_month_num);

CREATE INDEX IF NOT EXISTS idx_mv_pmhc_lower_clinician
    ON mv_provider_monthly_hours_cost (clinician);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_provider_monthly_hours_cost;

3. mv_student_provider_monthly
Description

Source: invoices, invoice_line_items

Purpose: For each student, monthly breakdown by clinician (hours + cost).

SQLite
DROP TABLE IF EXISTS mv_student_provider_monthly;

CREATE TABLE mv_student_provider_monthly AS
SELECT
    i.district_key                             AS district_key,
    LOWER(ili.student)                         AS student,
    LOWER(ili.clinician)                       AS clinician,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    LOWER(ili.clinician),
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_spm_dk_year_month;
DROP INDEX IF EXISTS idx_mv_spm_lower_student;
DROP INDEX IF EXISTS idx_mv_spm_lower_clinician;

CREATE INDEX idx_mv_spm_dk_year_month
    ON mv_student_provider_monthly (district_key, service_year, service_month_num);

CREATE INDEX idx_mv_spm_lower_student
    ON mv_student_provider_monthly (student);

CREATE INDEX idx_mv_spm_lower_clinician
    ON mv_student_provider_monthly (clinician);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_student_provider_monthly;

CREATE MATERIALIZED VIEW mv_student_provider_monthly AS
SELECT
    i.district_key                                  AS district_key,
    LOWER(ili.student)                              AS student,
    LOWER(ili.clinician)                            AS clinician,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    LOWER(ili.clinician),
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_spm_dk_year_month
    ON mv_student_provider_monthly (district_key, service_year, service_month_num);

CREATE INDEX IF NOT EXISTS idx_mv_spm_lower_student
    ON mv_student_provider_monthly (student);

CREATE INDEX IF NOT EXISTS idx_mv_spm_lower_clinician
    ON mv_student_provider_monthly (clinician);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_student_provider_monthly;

4. mv_district_service_code_monthly
Description

Source: invoices, invoice_line_items

Purpose: District totals by service_code per month.

SQLite
DROP TABLE IF EXISTS mv_district_service_code_monthly;

CREATE TABLE mv_district_service_code_monthly AS
SELECT
    i.district_key                             AS district_key,
    ili.service_code                           AS service_code,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    ili.service_code,
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_dscm_dk_year_month;
DROP INDEX IF EXISTS idx_mv_dscm_service_code;

CREATE INDEX idx_mv_dscm_dk_year_month
    ON mv_district_service_code_monthly (district_key, service_year, service_month_num);

CREATE INDEX idx_mv_dscm_service_code
    ON mv_district_service_code_monthly (service_code);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_district_service_code_monthly;

CREATE MATERIALIZED VIEW mv_district_service_code_monthly AS
SELECT
    i.district_key                                  AS district_key,
    ili.service_code                                AS service_code,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    ili.service_code,
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_dscm_dk_year_month
    ON mv_district_service_code_monthly (district_key, service_year, service_month_num);

CREATE INDEX IF NOT EXISTS idx_mv_dscm_service_code
    ON mv_district_service_code_monthly (service_code);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_district_service_code_monthly;

5. mv_invoice_summary
Description

Source: invoices, invoice_line_items

Purpose: Invoice-level totals (hours, cost, invoice_date).

SQLite
DROP TABLE IF EXISTS mv_invoice_summary;

CREATE TABLE mv_invoice_summary AS
SELECT
    i.id                     AS invoice_id,
    i.district_key           AS district_key,
    i.invoice_date           AS invoice_date,
    SUM(ili.hours)           AS total_hours,
    SUM(ili.cost)            AS total_cost,
    COUNT(DISTINCT LOWER(ili.student))   AS num_students,
    COUNT(DISTINCT LOWER(ili.clinician)) AS num_clinicians
FROM invoices i
LEFT JOIN invoice_line_items ili ON ili.invoice_id = i.id
GROUP BY
    i.id,
    i.district_key,
    i.invoice_date;
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_is_dk_invoice_date;
DROP INDEX IF EXISTS idx_mv_is_invoice_id;

CREATE INDEX idx_mv_is_dk_invoice_date
    ON mv_invoice_summary (district_key, invoice_date);

CREATE INDEX idx_mv_is_invoice_id
    ON mv_invoice_summary (invoice_id);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_invoice_summary;

CREATE MATERIALIZED VIEW mv_invoice_summary AS
SELECT
    i.id                     AS invoice_id,
    i.district_key           AS district_key,
    i.invoice_date           AS invoice_date,
    SUM(ili.hours)           AS total_hours,
    SUM(ili.cost)            AS total_cost,
    COUNT(DISTINCT LOWER(ili.student))   AS num_students,
    COUNT(DISTINCT LOWER(ili.clinician)) AS num_clinicians
FROM invoices i
LEFT JOIN invoice_line_items ili ON ili.invoice_id = i.id
GROUP BY
    i.id,
    i.district_key,
    i.invoice_date;
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_is_dk_invoice_date
    ON mv_invoice_summary (district_key, invoice_date);

CREATE INDEX IF NOT EXISTS idx_mv_is_invoice_id
    ON mv_invoice_summary (invoice_id);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_invoice_summary;

6. mv_student_year_summary
Description

Source: invoices, invoice_line_items

Purpose: Yearly totals per student (district, year).

SQLite
DROP TABLE IF EXISTS mv_student_year_summary;

CREATE TABLE mv_student_year_summary AS
SELECT
    i.district_key                             AS district_key,
    LOWER(ili.student)                         AS student,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    CAST(strftime('%Y', ili.service_date) AS INT);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_sys_dk_year;
DROP INDEX IF EXISTS idx_mv_sys_lower_student;

CREATE INDEX idx_mv_sys_dk_year
    ON mv_student_year_summary (district_key, service_year);

CREATE INDEX idx_mv_sys_lower_student
    ON mv_student_year_summary (student);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_student_year_summary;

CREATE MATERIALIZED VIEW mv_student_year_summary AS
SELECT
    i.district_key                                  AS district_key,
    LOWER(ili.student)                              AS student,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    EXTRACT(YEAR FROM ili.service_date)::int;
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_sys_dk_year
    ON mv_student_year_summary (district_key, service_year);

CREATE INDEX IF NOT EXISTS idx_mv_sys_lower_student
    ON mv_student_year_summary (student);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_student_year_summary;

7. mv_provider_caseload_monthly
Description

Source: invoices, invoice_line_items

Purpose: Clinician caseload (#students) + hours per month.

SQLite
DROP TABLE IF EXISTS mv_provider_caseload_monthly;

CREATE TABLE mv_provider_caseload_monthly AS
SELECT
    i.district_key                             AS district_key,
    LOWER(ili.clinician)                       AS clinician,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    COUNT(DISTINCT LOWER(ili.student))         AS num_students,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.clinician),
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_pcm_dk_year_month;
DROP INDEX IF EXISTS idx_mv_pcm_lower_clinician;

CREATE INDEX idx_mv_pcm_dk_year_month
    ON mv_provider_caseload_monthly (district_key, service_year, service_month_num);

CREATE INDEX idx_mv_pcm_lower_clinician
    ON mv_provider_caseload_monthly (clinician);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_provider_caseload_monthly;

CREATE MATERIALIZED VIEW mv_provider_caseload_monthly AS
SELECT
    i.district_key                                  AS district_key,
    LOWER(ili.clinician)                            AS clinician,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    COUNT(DISTINCT LOWER(ili.student))              AS num_students,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.clinician),
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_pcm_dk_year_month
    ON mv_provider_caseload_monthly (district_key, service_year, service_month_num);

CREATE INDEX IF NOT EXISTS idx_mv_pcm_lower_clinician
    ON mv_provider_caseload_monthly (clinician);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_provider_caseload_monthly;

8. mv_district_monthly_hours_cost
Description

Source: invoices, invoice_line_items

Purpose: District hours + cost per month.

SQLite
DROP TABLE IF EXISTS mv_district_monthly_hours_cost;

CREATE TABLE mv_district_monthly_hours_cost AS
SELECT
    i.district_key                             AS district_key,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_dmhc_dk_year_month;

CREATE INDEX idx_mv_dmhc_dk_year_month
    ON mv_district_monthly_hours_cost (district_key, service_year, service_month_num);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_district_monthly_hours_cost;

CREATE MATERIALIZED VIEW mv_district_monthly_hours_cost AS
SELECT
    i.district_key                                  AS district_key,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_dmhc_dk_year_month
    ON mv_district_monthly_hours_cost (district_key, service_year, service_month_num);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_district_monthly_hours_cost;

9. mv_vendor_monthly_hours_cost
Description

Source: invoices, invoice_line_items, vendors

Purpose: Vendor hours + cost per month (per district, vendor).

SQLite
DROP TABLE IF EXISTS mv_vendor_monthly_hours_cost;

CREATE TABLE mv_vendor_monthly_hours_cost AS
SELECT
    i.district_key                             AS district_key,
    v.id                                       AS vendor_id,
    v.name                                     AS vendor_name,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
JOIN invoice_line_items ili ON ili.invoice_id = i.id
GROUP BY
    i.district_key,
    v.id,
    v.name,
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_vmhc_dk_year_month_vendor;
DROP INDEX IF EXISTS idx_mv_vmhc_vendor;

CREATE INDEX idx_mv_vmhc_dk_year_month_vendor
    ON mv_vendor_monthly_hours_cost (district_key, service_year, service_month_num, vendor_id);

CREATE INDEX idx_mv_vmhc_vendor
    ON mv_vendor_monthly_hours_cost (vendor_id);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_vendor_monthly_hours_cost;

CREATE MATERIALIZED VIEW mv_vendor_monthly_hours_cost AS
SELECT
    i.district_key                                  AS district_key,
    v.id                                            AS vendor_id,
    v.name                                          AS vendor_name,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
JOIN invoice_line_items ili ON ili.invoice_id = i.id
GROUP BY
    i.district_key,
    v.id,
    v.name,
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_vmhc_dk_year_month_vendor
    ON mv_vendor_monthly_hours_cost (district_key, service_year, service_month_num, vendor_id);

CREATE INDEX IF NOT EXISTS idx_mv_vmhc_vendor
    ON mv_vendor_monthly_hours_cost (vendor_id);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_vendor_monthly_hours_cost;

10. mv_student_service_code_monthly
Description

Source: invoices, invoice_line_items

Purpose: Student × service_code hours + cost per month.

SQLite
DROP TABLE IF EXISTS mv_student_service_code_monthly;

CREATE TABLE mv_student_service_code_monthly AS
SELECT
    i.district_key                             AS district_key,
    LOWER(ili.student)                         AS student,
    ili.service_code                           AS service_code,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    ili.service_code,
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_sscm_dk_year_month;
DROP INDEX IF EXISTS idx_mv_sscm_lower_student;
DROP INDEX IF EXISTS idx_mv_sscm_service_code;

CREATE INDEX idx_mv_sscm_dk_year_month
    ON mv_student_service_code_monthly (district_key, service_year, service_month_num);

CREATE INDEX idx_mv_sscm_lower_student
    ON mv_student_service_code_monthly (student);

CREATE INDEX idx_mv_sscm_service_code
    ON mv_student_service_code_monthly (service_code);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_student_service_code_monthly;

CREATE MATERIALIZED VIEW mv_student_service_code_monthly AS
SELECT
    i.district_key                                  AS district_key,
    LOWER(ili.student)                              AS student,
    ili.service_code                                AS service_code,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    ili.service_code,
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_sscm_dk_year_month
    ON mv_student_service_code_monthly (district_key, service_year, service_month_num);

CREATE INDEX IF NOT EXISTS idx_mv_sscm_lower_student
    ON mv_student_service_code_monthly (student);

CREATE INDEX IF NOT EXISTS idx_mv_sscm_service_code
    ON mv_student_service_code_monthly (service_code);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_student_service_code_monthly;

11. mv_provider_service_code_monthly
Description

Source: invoices, invoice_line_items

Purpose: Clinician × service_code hours + cost per month.

SQLite
DROP TABLE IF EXISTS mv_provider_service_code_monthly;

CREATE TABLE mv_provider_service_code_monthly AS
SELECT
    i.district_key                             AS district_key,
    LOWER(ili.clinician)                       AS clinician,
    ili.service_code                           AS service_code,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    SUM(ili.hours)                             AS total_hours,
    SUM(ili.cost)                              AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.clinician),
    ili.service_code,
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_pscm_dk_year_month;
DROP INDEX IF EXISTS idx_mv_pscm_lower_clinician;
DROP INDEX IF EXISTS idx_mv_pscm_service_code;

CREATE INDEX idx_mv_pscm_dk_year_month
    ON mv_provider_service_code_monthly (district_key, service_year, service_month_num);

CREATE INDEX idx_mv_pscm_lower_clinician
    ON mv_provider_service_code_monthly (clinician);

CREATE INDEX idx_mv_pscm_service_code
    ON mv_provider_service_code_monthly (service_code);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_provider_service_code_monthly;

CREATE MATERIALIZED VIEW mv_provider_service_code_monthly AS
SELECT
    i.district_key                                  AS district_key,
    LOWER(ili.clinician)                            AS clinician,
    ili.service_code                                AS service_code,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    SUM(ili.hours)                                  AS total_hours,
    SUM(ili.cost)                                   AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.clinician),
    ili.service_code,
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_pscm_dk_year_month
    ON mv_provider_service_code_monthly (district_key, service_year, service_month_num);

CREATE INDEX IF NOT EXISTS idx_mv_pscm_lower_clinician
    ON mv_provider_service_code_monthly (clinician);

CREATE INDEX IF NOT EXISTS idx_mv_pscm_service_code
    ON mv_provider_service_code_monthly (service_code);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_provider_service_code_monthly;

12. mv_student_daily_hours
Description

Source: invoices, invoice_line_items

Purpose: Daily hours + cost per student.

SQLite
DROP TABLE IF EXISTS mv_student_daily_hours;

CREATE TABLE mv_student_daily_hours AS
SELECT
    i.district_key                 AS district_key,
    LOWER(ili.student)             AS student,
    DATE(ili.service_date)         AS service_date,
    SUM(ili.hours)                 AS total_hours,
    SUM(ili.cost)                  AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    DATE(ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_sdh_dk_date;
DROP INDEX IF EXISTS idx_mv_sdh_lower_student;

CREATE INDEX idx_mv_sdh_dk_date
    ON mv_student_daily_hours (district_key, service_date);

CREATE INDEX idx_mv_sdh_lower_student
    ON mv_student_daily_hours (student);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_student_daily_hours;

CREATE MATERIALIZED VIEW mv_student_daily_hours AS
SELECT
    i.district_key                    AS district_key,
    LOWER(ili.student)                AS student,
    ili.service_date::date            AS service_date,
    SUM(ili.hours)                    AS total_hours,
    SUM(ili.cost)                     AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    ili.service_date::date;
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_sdh_dk_date
    ON mv_student_daily_hours (district_key, service_date);

CREATE INDEX IF NOT EXISTS idx_mv_sdh_lower_student
    ON mv_student_daily_hours (student);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_student_daily_hours;

13. mv_provider_daily_hours
Description

Source: invoices, invoice_line_items

Purpose: Daily hours + cost per clinician.

SQLite
DROP TABLE IF EXISTS mv_provider_daily_hours;

CREATE TABLE mv_provider_daily_hours AS
SELECT
    i.district_key                 AS district_key,
    LOWER(ili.clinician)           AS clinician,
    DATE(ili.service_date)         AS service_date,
    SUM(ili.hours)                 AS total_hours,
    SUM(ili.cost)                  AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.clinician),
    DATE(ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_pdh_dk_date;
DROP INDEX IF EXISTS idx_mv_pdh_lower_clinician;

CREATE INDEX idx_mv_pdh_dk_date
    ON mv_provider_daily_hours (district_key, service_date);

CREATE INDEX idx_mv_pdh_lower_clinician
    ON mv_provider_daily_hours (clinician);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_provider_daily_hours;

CREATE MATERIALIZED VIEW mv_provider_daily_hours AS
SELECT
    i.district_key                    AS district_key,
    LOWER(ili.clinician)              AS clinician,
    ili.service_date::date            AS service_date,
    SUM(ili.hours)                    AS total_hours,
    SUM(ili.cost)                     AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.clinician),
    ili.service_date::date;
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_pdh_dk_date
    ON mv_provider_daily_hours (district_key, service_date);

CREATE INDEX IF NOT EXISTS idx_mv_pdh_lower_clinician
    ON mv_provider_daily_hours (clinician);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_provider_daily_hours;

14. mv_student_service_intensity_monthly
Description

Source: invoices, invoice_line_items

Purpose: Student service_days, hours, and avg_hours_per_day per month.

SQLite
DROP TABLE IF EXISTS mv_student_service_intensity_monthly;

CREATE TABLE mv_student_service_intensity_monthly AS
SELECT
    i.district_key                             AS district_key,
    LOWER(ili.student)                         AS student,
    CAST(strftime('%Y', ili.service_date) AS INT) AS service_year,
    CAST(strftime('%m', ili.service_date) AS INT) AS service_month_num,
    strftime('%Y-%m', ili.service_date)        AS service_month,
    COUNT(DISTINCT DATE(ili.service_date))     AS service_days,
    SUM(ili.hours)                             AS total_hours,
    CASE
        WHEN COUNT(DISTINCT DATE(ili.service_date)) = 0
            THEN NULL
        ELSE 1.0 * SUM(ili.hours) / COUNT(DISTINCT DATE(ili.service_date))
    END                                        AS avg_hours_per_day
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    CAST(strftime('%Y', ili.service_date) AS INT),
    CAST(strftime('%m', ili.service_date) AS INT),
    strftime('%Y-%m', ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_ssim_dk_year_month;
DROP INDEX IF EXISTS idx_mv_ssim_lower_student;

CREATE INDEX idx_mv_ssim_dk_year_month
    ON mv_student_service_intensity_monthly (district_key, service_year, service_month_num);

CREATE INDEX idx_mv_ssim_lower_student
    ON mv_student_service_intensity_monthly (student);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_student_service_intensity_monthly;

CREATE MATERIALIZED VIEW mv_student_service_intensity_monthly AS
SELECT
    i.district_key                                  AS district_key,
    LOWER(ili.student)                              AS student,
    EXTRACT(YEAR FROM ili.service_date)::int        AS service_year,
    EXTRACT(MONTH FROM ili.service_date)::int       AS service_month_num,
    to_char(ili.service_date, 'YYYY-MM')           AS service_month,
    COUNT(DISTINCT ili.service_date::date)          AS service_days,
    SUM(ili.hours)                                  AS total_hours,
    CASE
        WHEN COUNT(DISTINCT ili.service_date::date) = 0
            THEN NULL
        ELSE SUM(ili.hours)::numeric / COUNT(DISTINCT ili.service_date::date)
    END                                             AS avg_hours_per_day
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    LOWER(ili.student),
    EXTRACT(YEAR FROM ili.service_date)::int,
    EXTRACT(MONTH FROM ili.service_date)::int,
    to_char(ili.service_date, 'YYYY-MM');
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_ssim_dk_year_month
    ON mv_student_service_intensity_monthly (district_key, service_year, service_month_num);

CREATE INDEX IF NOT EXISTS idx_mv_ssim_lower_student
    ON mv_student_service_intensity_monthly (student);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_student_service_intensity_monthly;

15. mv_district_daily_coverage
Description

Source: invoices, invoice_line_items

Purpose: District daily hours, cost, #students, #clinicians.

SQLite
DROP TABLE IF EXISTS mv_district_daily_coverage;

CREATE TABLE mv_district_daily_coverage AS
SELECT
    i.district_key                         AS district_key,
    DATE(ili.service_date)                 AS service_date,
    SUM(ili.hours)                         AS total_hours,
    SUM(ili.cost)                          AS total_cost,
    COUNT(DISTINCT LOWER(ili.student))     AS num_students,
    COUNT(DISTINCT LOWER(ili.clinician))   AS num_clinicians
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    DATE(ili.service_date);
;

-- Indexes
DROP INDEX IF EXISTS idx_mv_ddc_dk_date;

CREATE INDEX idx_mv_ddc_dk_date
    ON mv_district_daily_coverage (district_key, service_date);

Postgres
DROP MATERIALIZED VIEW IF EXISTS mv_district_daily_coverage;

CREATE MATERIALIZED VIEW mv_district_daily_coverage AS
SELECT
    i.district_key                          AS district_key,
    ili.service_date::date                  AS service_date,
    SUM(ili.hours)                          AS total_hours,
    SUM(ili.cost)                           AS total_cost,
    COUNT(DISTINCT LOWER(ili.student))      AS num_students,
    COUNT(DISTINCT LOWER(ili.clinician))    AS num_clinicians
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
GROUP BY
    i.district_key,
    ili.service_date::date;
;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mv_ddc_dk_date
    ON mv_district_daily_coverage (district_key, service_date);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_district_daily_coverage;