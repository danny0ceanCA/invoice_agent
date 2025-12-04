## VendorExample 0001
User: Show monthly spend for Healthcare Solutions LLC.
Assistant:
{
  "text": "Here are the monthly totals for Healthcare Solutions LLC.",
  "rows": [
    { "service_month": "september", "total_cost": 18250.75 },
    { "service_month": "october",   "total_cost": 17540.00 },
    { "service_month": "november",  "total_cost": 18925.20 }
  ],
  "html":
    "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Service Month</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>$18,250.75</td></tr><tr><td>October</td><td>$17,540.00</td></tr><tr><td>November</td><td>$18,925.20</td></tr></tbody></table></div>"
}

## VendorExample 0002
User: Show monthly hours for Healthcare Solutions LLC.
Assistant:
{
  "text": "Here are the total monthly hours for Healthcare Solutions LLC.",
  "rows": [
    { "service_month": "september", "total_hours": 152.5 },
    { "service_month": "october",   "total_hours": 165.0 },
    { "service_month": "november",  "total_hours": 159.25 }
  ],
  "html":
    "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Service Month</th><th>Total Hours</th></tr></thead><tbody><tr><td>September</td><td>152.5</td></tr><tr><td>October</td><td>165.0</td></tr><tr><td>November</td><td>159.25</td></tr></tbody></table></div>"
}

## VendorExample 0003
User: Show year-to-date spend for Healthcare Solutions LLC.
Assistant:
{
  "text": "Here is the year-to-date spend for Healthcare Solutions LLC.",
  "rows": [
    { "vendor_name": "healthcare solutions llc", "total_spend": 54715.95 }
  ],
  "html":
    "<div class='summary-cards'><div class='card'><div class='label'>Total YTD Spend</div><div class='value'>$54,715.95</div></div></div>"
}

## VendorExample 0004
User: Show all invoices for Healthcare Solutions LLC.
Assistant:
{
  "text": "Here are all invoices from Healthcare Solutions LLC.",
  "rows": [
    { "invoice_number": "HCS-SEP2025-01", "student_name": "Ava Johnson", "total_cost": 2140.00, "service_month": "september", "status": "Approved" },
    { "invoice_number": "HCS-SEP2025-02", "student_name": "Liam Martinez", "total_cost": 1985.50, "service_month": "september", "status": "Approved" },
    { "invoice_number": "HCS-OCT2025-01", "student_name": "Ava Johnson", "total_cost": 2050.25, "service_month": "october", "status": "Approved" }
  ],
  "html":
    "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Invoice #</th><th>Student</th><th>Total Cost</th><th>Month</th><th>Status</th></tr></thead><tbody><tr><td>HCS-SEP2025-01</td><td>Ava Johnson</td><td>$2,140.00</td><td>September</td><td>Approved</td></tr><tr><td>HCS-SEP2025-02</td><td>Liam Martinez</td><td>$1,985.50</td><td>September</td><td>Approved</td></tr><tr><td>HCS-OCT2025-01</td><td>Ava Johnson</td><td>$2,050.25</td><td>October</td><td>Approved</td></tr></tbody></table></div>"
}

## VendorExample 0005
User: Compare spend for Healthcare Solutions LLC and Sunrise Pediatric Care.
Assistant:
{
  "text": "Here is the monthly spend comparison for Healthcare Solutions LLC and Sunrise Pediatric Care.",
  "rows": [
    { "vendor_name": "healthcare solutions llc",   "service_month": "september", "total_cost": 18250.75 },
    { "vendor_name": "sunrise pediatric care",     "service_month": "september", "total_cost": 16410.00 },
    { "vendor_name": "healthcare solutions llc",   "service_month": "october",   "total_cost": 17540.00 },
    { "vendor_name": "sunrise pediatric care",     "service_month": "october",   "total_cost": 17100.50 }
  ],
  "html":
    "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Vendor</th><th>Month</th><th>Total Cost</th></tr></thead><tbody><tr><td>Healthcare Solutions LLC</td><td>September</td><td>$18,250.75</td></tr><tr><td>Sunrise Pediatric Care</td><td>September</td><td>$16,410.00</td></tr><tr><td>Healthcare Solutions LLC</td><td>October</td><td>$17,540.00</td></tr><tr><td>Sunrise Pediatric Care</td><td>October</td><td>$17,100.50</td></tr></tbody></table></div>"
}

## VendorExample 0006
User: Which clinicians provided the most hours for Healthcare Solutions LLC?
Assistant:
{
  "text": "Here are the clinicians delivering the most hours under Healthcare Solutions LLC.",
  "rows": [
    { "clinician": "Tatiana Ortiz", "total_hours": 82.5 },
    { "clinician": "Michael Reed",  "total_hours": 71.0 },
    { "clinician": "Samuel Kim",    "total_hours": 65.25 }
  ],
  "html":
    "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Clinician</th><th>Total Hours</th></tr></thead><tbody><tr><td>Tatiana Ortiz</td><td>82.5</td></tr><tr><td>Michael Reed</td><td>71.0</td></tr><tr><td>Samuel Kim</td><td>65.25</td></tr></tbody></table></div>"
}

## VendorExample 0007
User: Give me a pivot of monthly spend for Healthcare Solutions LLC.
Assistant:
{
  "text": "Here is a month-by-month spending pivot for Healthcare Solutions LLC.",
  "rows": [
    { "vendor_name": "healthcare solutions llc", "service_month": "september", "total_cost": 18250.75 },
    { "vendor_name": "healthcare solutions llc", "service_month": "october",   "total_cost": 17540.00 }
  ],
  "html":
    "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Vendor</th><th>September</th><th>October</th><th>Total Spend ($)</th></tr></thead><tbody><tr><td>Healthcare Solutions LLC</td><td>$18,250.75</td><td>$17,540.00</td><td>$35,790.75</td></tr></tbody></table></div>"
}
