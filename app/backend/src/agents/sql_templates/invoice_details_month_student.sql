SELECT
    i.invoice_number,
    ili.student AS student_name,
    ili.clinician AS provider,
    ili.service_code,
    ili.hours,
    ili.cost,
    ili.service_date
FROM invoice_line_items ili
JOIN invoices i ON ili.invoice_id = i.id
WHERE LOWER(ili.student) LIKE LOWER('%{{ student_name }}%')
  AND LOWER(i.service_month) = LOWER('{{ month }}')
  AND i.invoice_date BETWEEN '{{ start_date }}' AND '{{ end_date }}'
ORDER BY ili.service_date ASC, ili.clinician ASC;
