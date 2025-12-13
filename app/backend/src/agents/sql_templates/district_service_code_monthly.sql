-- Logic model will inject :district_key
SELECT
  ili.service_code,
  to_char(ili.service_date, 'YYYY-MM') AS service_month,
  SUM(ili.hours) AS total_hours,
  SUM(ili.cost) AS total_cost
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
WHERE i.district_key = :district_key
GROUP BY
  ili.service_code,
  to_char(ili.service_date, 'YYYY-MM')
ORDER BY service_month ASC, total_cost DESC;
