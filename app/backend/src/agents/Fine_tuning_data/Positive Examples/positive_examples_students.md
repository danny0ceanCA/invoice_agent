### StudentExample 0001
User: Show monthly spend for Jack Garcia.

Assistant:
{"text": "Here are the monthly totals for Jack Garcia.", 
 "rows": [
   {"service_month": "september", "total_cost": 2150.50},
   {"service_month": "october", "total_cost": 1875.00},
   {"service_month": "november", "total_cost": 2040.25}
 ],
 "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Service Month</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>$2,150.50</td></tr><tr><td>October</td><td>$1,875.00</td></tr><tr><td>November</td><td>$2,040.25</td></tr></tbody></table></div>"
}

### StudentExample 0002
User: Show monthly hours for Jack Garcia.

Assistant:
{"text": "Here are the monthly hours for Jack Garcia.", 
 "rows": [
   {"service_month": "september", "total_hours": 18.5},
   {"service_month": "october", "total_hours": 21.0}
 ],
 "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Service Month</th><th>Total Hours</th></tr></thead><tbody><tr><td>September</td><td>18.5</td></tr><tr><td>October</td><td>21.0</td></tr></tbody></table></div>"
}

### StudentExample 0003
User: Show year-to-date invoices for Jack Garcia.

Assistant:
{"text": "Here are Jack Garcia’s year-to-date invoices.", 
 "rows": [
   {"invoice_number": "Garcia-SEP2025", "student_name": "Jack Garcia", "total_cost": 2150.50, "service_month": "september", "status": "Approved"},
   {"invoice_number": "Garcia-OCT2025", "student_name": "Jack Garcia", "total_cost": 1875.00, "service_month": "october", "status": "Approved"}
 ],
 "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Invoice Number</th><th>Student</th><th>Total Cost</th><th>Service Month</th><th>Status</th></tr></thead><tbody><tr><td>Garcia-SEP2025</td><td>Jack Garcia</td><td>$2,150.50</td><td>September</td><td>Approved</td></tr><tr><td>Garcia-OCT2025</td><td>Jack Garcia</td><td>$1,875.00</td><td>October</td><td>Approved</td></tr></tbody></table></div>"
}

### StudentExample 0004
User: Give me a pivot of monthly spend for Jack Garcia.

Assistant:
{"text": "Here is a month-by-month spending pivot for Jack Garcia.",
 "rows": [
   {"student_name": "jack garcia", "service_month": "september", "total_cost": 2150.50},
   {"student_name": "jack garcia", "service_month": "october", "total_cost": 1875.00}
 ],
 "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Student</th><th>September</th><th>October</th><th>Total Spend ($)</th></tr></thead><tbody><tr><td>Jack Garcia</td><td>$2,150.50</td><td>$1,875.00</td><td>$4,025.50</td></tr></tbody></table></div>"
}

### StudentExample 0005
User: Show me which clinicians supported Jack Garcia and how many hours they provided.

Assistant:
{"text": "Here are the clinicians who supported Jack Garcia and their total hours.",
 "rows": [
   {"clinician": "Tatiana Ortiz", "total_hours": 14.0},
   {"clinician": "Michael Reed", "total_hours": 10.5}
 ],
 "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Clinician</th><th>Total Hours</th></tr></thead><tbody><tr><td>Tatiana Ortiz</td><td>14.0</td></tr><tr><td>Michael Reed</td><td>10.5</td></tr></tbody></table></div>"
}

### StudentExample 0006
User: Break down Jack Garcia’s monthly spend by clinician.

Assistant:
{"text": "Here is the monthly cost for Jack Garcia broken down by clinician.",
 "rows": [
   {"service_month": "september", "clinician": "Tatiana Ortiz", "total_cost": 1200.00},
   {"service_month": "september", "clinician": "Michael Reed", "total_cost": 950.50},
   {"service_month": "october", "clinician": "Tatiana Ortiz", "total_cost": 875.00},
   {"service_month": "october", "clinician": "Michael Reed", "total_cost": 1000.00}
 ],
 "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Clinician</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>Tatiana Ortiz</td><td>$1,200.00</td></tr><tr><td>September</td><td>Michael Reed</td><td>$950.50</td></tr><tr><td>October</td><td>Tatiana Ortiz</td><td>$875.00</td></tr><tr><td>October</td><td>Michael Reed</td><td>$1,000.00</td></tr></tbody></table></div>"
}

### StudentExample 0007
User: Give me a summary of spending for Jack Garcia.

Assistant:
{"text": "Here is Jack Garcia’s spending summary.",
 "rows": [
   {"service_month": "september", "total_cost": 2150.50},
   {"service_month": "october", "total_cost": 1875.00},
   {"service_month": "november", "total_cost": 2040.25}
 ],
 "html": "<div class='summary-cards'><div class='card'><div class='label'>Total Spend</div><div class='value'>$6,065.75</div></div></div><div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>$2,150.50</td></tr><td>October</td><td>$1,875.00</td></tr><tr><td>November</td><td>$2,040.25</td></tr></tbody></table></div>"
}

