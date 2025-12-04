## Canonical 0001

SELECT LOWER(service_month) AS service_month,
SUM(total_cost) AS total_cost
FROM invoices
WHERE district_key = :district_key
AND LOWER(student_name) = LOWER(:student_name)
GROUP BY LOWER(service_month)

## Canonical 0002

SELECT LOWER(i.service_month) AS service_month,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(ili.student) = LOWER(:student_name)
GROUP BY LOWER(i.service_month)

## Canonical 0003

SELECT invoice_number,
student_name,
total_cost,
service_month,
status
FROM invoices
WHERE district_key = :district_key
AND LOWER(student_name) = LOWER(:student_name)
AND strftime('%Y', invoice_date) = strftime('%Y','now')
ORDER BY invoice_date DESC

## Canonical 0004

SELECT invoice_number,
student_name,
total_hours,
service_month,
status
FROM invoices
WHERE district_key = :district_key
AND LOWER(student_name) = LOWER(:student_name)
AND strftime('%Y', invoice_date) = strftime('%Y','now')
ORDER BY invoice_date DESC

## Canonical 0005

WITH sy AS (
SELECT date(strftime('%Y','now')||'-07-01') AS start,
date(strftime('%Y','now')||'-06-30','+1 year') AS end
)
SELECT LOWER(i.student_name) AS student_name,
SUM(i.total_cost) AS total_spend
FROM invoices i, sy
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN sy.start AND sy.end
GROUP BY LOWER(i.student_name)
ORDER BY total_spend DESC
LIMIT 5

## Canonical 0006

WITH sy AS (
SELECT date(strftime('%Y','now')||'-07-01') AS start,
date(strftime('%Y','now')||'-06-30','+1 year') AS end
)
SELECT LOWER(i.student_name) AS student_name,
SUM(i.total_hours) AS total_hours
FROM invoices i, sy
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN sy.start AND sy.end
GROUP BY LOWER(i.student_name)
ORDER BY total_hours DESC
LIMIT 5

## Canonical 0009

WITH first_invoice AS (
SELECT LOWER(student_name) AS student_name,
MIN(date(invoice_date)) AS first_date
FROM invoices
WHERE district_key = :district_key
GROUP BY LOWER(student_name)
), sy AS (
SELECT date(strftime('%Y','now')||'-07-01') AS start,
date(strftime('%Y','now')||'-06-30','+1 year') AS end
)
SELECT student_name, first_date
FROM first_invoice, sy
WHERE first_date BETWEEN sy.start AND sy.end
ORDER BY first_date

## Canonical 0011

SELECT LOWER(service_month) AS service_month,
SUM(total_cost) AS total_cost
FROM invoices
WHERE district_key = :district_key
GROUP BY LOWER(service_month)

## Canonical 0013

SELECT LOWER(student_name) AS student_name,
LOWER(service_month) AS service_month,
SUM(total_cost) AS total_cost
FROM invoices
WHERE district_key = :district_key
AND LOWER(student_name) IN (:student_a, :student_b)
GROUP BY LOWER(student_name), LOWER(service_month)

## Canonical 0014

SELECT LOWER(ili.student) AS student_name,
LOWER(i.service_month) AS service_month,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(ili.student) IN (:student_a, :student_b)
GROUP BY LOWER(ili.student), LOWER(i.service_month)

## Canonical 0015

SELECT invoice_number,
student_name,
total_cost,
service_month,
status
FROM invoices
WHERE district_key = :district_key
AND LOWER(student_name) = LOWER(:student_name)
ORDER BY invoice_date DESC

## Canonical 0016

-- Services delivered to a student over a date range
SELECT i.invoice_number,
i.student_name,
i.total_cost,
i.service_month,
i.status,
ili.service_date
FROM invoices i
JOIN invoice_line_items ili ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(i.student_name) = LOWER(:student_name)
AND date(ili.service_date) BETWEEN date(:start_date) AND date(:end_date)
ORDER BY ili.service_date

## Canonical 0017

SELECT LOWER(i.service_month) AS service_month,
SUM(i.total_cost) AS total_cost
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
AND LOWER(v.name) = LOWER(:vendor_name)
GROUP BY LOWER(i.service_month)

## Canonical 0018

SELECT LOWER(i.service_month) AS service_month,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
AND LOWER(v.name) = LOWER(:vendor_name)
GROUP BY LOWER(i.service_month)

## Canonical 0019

SELECT v.name AS vendor_name,
SUM(i.total_cost) AS total_spend
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
AND LOWER(v.name) = LOWER(:vendor_name)
AND strftime('%Y', i.invoice_date) = strftime('%Y','now')
GROUP BY v.name

## Canonical 0021

WITH sy AS (
SELECT date(strftime('%Y','now')||'-07-01') AS start,
date(strftime('%Y','now')||'-06-30','+1 year') AS end
)
SELECT v.name AS vendor_name,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
JOIN vendors v ON v.id = i.vendor_id, sy
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN sy.start AND sy.end
GROUP BY v.name
ORDER BY total_hours DESC
LIMIT 5

## Canonical 0022

SELECT LOWER(v.name) AS vendor_name,
LOWER(i.service_month) AS service_month,
SUM(i.total_cost) AS total_cost
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
AND LOWER(v.name) IN (:vendor_a, :vendor_b)
GROUP BY LOWER(v.name), LOWER(i.service_month)

## Canonical 0023

SELECT LOWER(i.service_month) AS service_month,
LOWER(v.name) AS vendor_name,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
AND LOWER(v.name) IN (:vendor_a, :vendor_b)
GROUP BY LOWER(i.service_month), LOWER(v.name)

## Canonical 0024

-- Vendors with increasing spend over last 3 months
WITH monthly_vendor AS (
SELECT v.name AS vendor_name,
strftime('%Y-%m', i.invoice_date) AS year_month,
SUM(i.total_cost) AS total_spend
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
GROUP BY v.name, year_month
), ranked AS (
SELECT vendor_name,
year_month,
total_spend,
LAG(total_spend) OVER (PARTITION BY vendor_name ORDER BY year_month) AS prev_month,
LAG(total_spend,2) OVER (PARTITION BY vendor_name ORDER BY year_month) AS prev_prev_month
FROM monthly_vendor
)
SELECT vendor_name, prev_prev_month, prev_month, total_spend
FROM ranked
WHERE prev_prev_month IS NOT NULL
AND prev_month IS NOT NULL
AND total_spend > prev_month
AND prev_month > prev_prev_month
ORDER BY total_spend DESC

## Canonical 0025

-- Vendors with decreasing spend over last 3 months
WITH monthly_vendor AS (
SELECT v.name AS vendor_name,
strftime('%Y-%m', i.invoice_date) AS year_month,
SUM(i.total_cost) AS total_spend
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
GROUP BY v.name, year_month
), ranked AS (
SELECT vendor_name,
year_month,
total_spend,
LAG(total_spend) OVER (PARTITION BY vendor_name ORDER BY year_month) AS prev_month,
LAG(total_spend,2) OVER (PARTITION BY vendor_name ORDER BY year_month) AS prev_prev_month
FROM monthly_vendor
)
SELECT vendor_name, prev_prev_month, prev_month, total_spend
FROM ranked
WHERE prev_prev_month IS NOT NULL
AND prev_month IS NOT NULL
AND total_spend < prev_month
AND prev_month < prev_prev_month
ORDER BY total_spend ASC

## Canonical 0026

SELECT i.invoice_number,
i.student_name,
i.total_cost,
i.service_month,
i.status
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
AND LOWER(v.name) = LOWER(:vendor_name)
ORDER BY i.invoice_date DESC

## Canonical 0027

-- Invoice details for a vendor (line-item detail only)
SELECT i.invoice_number,
i.service_month,
ili.service_date,
ili.student AS student_name,
ili.clinician AS provider,
ili.service_code,
ili.hours,
ili.cost
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
AND LOWER(v.name) = LOWER(:vendor_name)
ORDER BY i.invoice_date DESC,
i.invoice_number,
ili.service_date

## Canonical 0028

SELECT v.name AS vendor_name,
COUNT(DISTINCT i.student_name) AS students_served
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
GROUP BY v.name
ORDER BY students_served DESC
LIMIT 5

## Canonical 0029

SELECT v.name AS vendor_name,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
GROUP BY v.name
ORDER BY total_hours DESC
LIMIT 5

## Canonical 0030

SELECT LOWER(i.service_month) AS service_month,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(ili.clinician) = LOWER(:clinician_name)
GROUP BY LOWER(i.service_month)

## Canonical 0031

SELECT LOWER(i.service_month) AS service_month,
SUM(ili.cost) AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(ili.clinician) = LOWER(:clinician_name)
GROUP BY LOWER(i.service_month)

## Canonical 0032

SELECT LOWER(ili.clinician) AS clinician_name,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(ili.clinician) = LOWER(:clinician_name)
AND strftime('%Y', i.invoice_date) = strftime('%Y','now')
GROUP BY LOWER(ili.clinician)

## Canonical 0033

SELECT LOWER(ili.clinician) AS clinician_name,
SUM(ili.cost) AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(ili.clinician) = LOWER(:clinician_name)
AND strftime('%Y', i.invoice_date) = strftime('%Y','now')
GROUP BY LOWER(ili.clinician)

## Canonical 0034

WITH sy AS (
SELECT date(strftime('%Y','now')||'-07-01') AS start,
date(strftime('%Y','now')||'-06-30','+1 year') AS end
)
SELECT LOWER(ili.clinician) AS clinician,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id, sy
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN sy.start AND sy.end
GROUP BY LOWER(ili.clinician)
ORDER BY total_hours DESC
LIMIT 5

## Canonical 0035

WITH sy AS (
SELECT date(strftime('%Y','now')||'-07-01') AS start,
date(strftime('%Y','now')||'-06-30','+1 year') AS end
)
SELECT LOWER(ili.clinician) AS clinician,
SUM(ili.cost) AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id, sy
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN sy.start AND sy.end
GROUP BY LOWER(ili.clinician)
ORDER BY total_cost DESC
LIMIT 5

## Canonical 0036

SELECT ili.service_code AS clinician_type,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY ili.service_code
ORDER BY total_hours DESC

## Canonical 0037

SELECT ili.service_code AS clinician_type,
SUM(ili.cost) AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY ili.service_code
ORDER BY total_cost DESC

## Canonical 0038

SELECT LOWER(i.service_month) AS service_month,
ili.service_code AS clinician_type,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
GROUP BY LOWER(i.service_month), ili.service_code
ORDER BY LOWER(i.service_month), total_hours DESC

## Canonical 0039

SELECT ili.service_code AS clinician_type,
LOWER(i.service_month) AS service_month,
SUM(ili.cost) AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
GROUP BY ili.service_code, LOWER(i.service_month)
ORDER BY LOWER(i.service_month), ili.service_code

## Canonical 0040

SELECT LOWER(i.service_month) AS service_month,
LOWER(ili.clinician) AS clinician,
SUM(ili.hours) AS total_hours
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(ili.clinician) IN (LOWER(:clinician_a), LOWER(:clinician_b))
GROUP BY LOWER(i.service_month), LOWER(ili.clinician)
ORDER BY clinician, service_month

## Canonical 0041

SELECT LOWER(i.service_month) AS service_month,
LOWER(ili.clinician) AS clinician,
SUM(ili.cost) AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(ili.clinician) IN (LOWER(:clinician_a), LOWER(:clinician_b))
GROUP BY LOWER(i.service_month), LOWER(ili.clinician)
ORDER BY clinician, service_month

## Canonical 0045

SELECT LOWER(i.service_month) AS service_month,
SUM(i.total_cost) AS total_cost
FROM invoices i
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY LOWER(i.service_month)

## Canonical 0046

SELECT LOWER(i.service_month) AS service_month,
SUM(i.total_hours) AS total_hours
FROM invoices i
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY LOWER(i.service_month)

## Canonical 0047

SELECT SUM(total_cost) AS total_spend
FROM invoices
WHERE district_key = :district_key
AND strftime('%Y', invoice_date) = strftime('%Y','now')

## Canonical 0048

SELECT SUM(total_hours) AS total_hours
FROM invoices
WHERE district_key = :district_key
AND strftime('%Y', invoice_date) = strftime('%Y','now')

## Canonical 0049

SELECT LOWER(i.service_month) AS service_month,
SUM(i.total_cost) AS total_cost
FROM invoices i
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY LOWER(i.service_month)

## Canonical 0050

SELECT LOWER(i.service_month) AS service_month,
SUM(i.total_hours) AS total_hours
FROM invoices i
WHERE i.district_key = :district_key
AND date(i.invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY LOWER(i.service_month)

## Canonical 0051

SELECT LOWER(service_month) AS service_month,
SUM(total_cost) AS total_spend
FROM invoices
WHERE district_key = :district_key
AND date(invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY LOWER(service_month)
ORDER BY total_spend DESC
LIMIT 1

## Canonical 0052

SELECT LOWER(service_month) AS service_month,
SUM(total_cost) AS total_spend
FROM invoices
WHERE district_key = :district_key
AND date(invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY LOWER(service_month)
ORDER BY total_spend ASC
LIMIT 1

## Canonical 0053

WITH mt AS (
SELECT LOWER(service_month) AS service_month,
SUM(total_cost) AS total_cost
FROM invoices
WHERE district_key = :district_key
AND date(invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY LOWER(service_month)
)
SELECT ROUND(AVG(total_cost), 2) AS average_monthly_spend
FROM mt

## Canonical 0054

WITH mt AS (
SELECT LOWER(service_month) AS service_month,
SUM(total_hours) AS total_hours
FROM invoices
WHERE district_key = :district_key
AND date(invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY LOWER(service_month)
)
SELECT ROUND(AVG(total_hours), 2) AS average_monthly_hours
FROM mt

## Canonical 0055

SELECT LOWER(service_month) AS service_month,
SUM(total_cost) AS total_cost
FROM invoices
WHERE district_key = :district_key
AND LOWER(service_month) IN (LOWER(:month_a), LOWER(:month_b))
GROUP BY LOWER(service_month)

## Canonical 0056

SELECT LOWER(service_month) AS service_month,
SUM(total_hours) AS total_hours
FROM invoices
WHERE district_key = :district_key
AND LOWER(service_month) IN (LOWER(:month_a), LOWER(:month_b))
GROUP BY LOWER(service_month)

## Canonical 0057

SELECT SUM(total_cost) AS total_spend
FROM invoices
WHERE district_key = :district_key
AND LOWER(service_month) = LOWER(:month)

## Canonical 0058

SELECT SUM(total_hours) AS total_hours
FROM invoices
WHERE district_key = :district_key
AND LOWER(service_month) = LOWER(:month)

## Canonical 0059

SELECT LOWER(service_month) AS service_month,
SUM(total_cost) AS total_cost
FROM invoices
WHERE district_key = :district_key
AND date(invoice_date) BETWEEN
date(strftime('%Y','now')||'-07-01') AND
date(strftime('%Y','now')||'-06-30','+1 year')
GROUP BY LOWER(service_month)

## Canonical 0060

SELECT i.invoice_number,
i.service_month,
ili.service_date,
ili.student,
ili.clinician,
ili.service_code,
ili.hours,
ili.cost
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE i.district_key = :district_key
AND LOWER(ili.student) = LOWER(:student_name)
AND LOWER(i.service_month) = LOWER(:service_month)
ORDER BY ili.service_date, i.invoice_number

## Canonical 0061

SELECT i.invoice_number,
i.service_month,
ili.service_date,
ili.student,
ili.clinician,
ili.service_code,
ili.hours,
ili.cost
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
AND LOWER(v.name) = LOWER(:vendor_name)
AND LOWER(ili.student) = LOWER(:student_name)
AND LOWER(i.service_month) = LOWER(:service_month)
ORDER BY ili.service_date, i.invoice_number