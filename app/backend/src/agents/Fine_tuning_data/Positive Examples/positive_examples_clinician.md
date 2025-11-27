## ClinicianExample 0001

User: Show monthly hours for clinician Tatiana Ortiz.

Assistant:
{
  "text": "Here are the total monthly hours for clinician Tatiana Ortiz.",
  "rows": [
    {"service_month": "september", "total_hours": 42.0},
    {"service_month": "october", "total_hours": 38.5},
    {"service_month": "november", "total_hours": 40.25}
  ],
  "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Total Hours</th></tr></thead><tbody><tr><td>September</td><td>42.0</td></tr><tr><td>October</td><td>38.5</td></tr><tr><td>November</td><td>40.25</td></tr></tbody></table></div>"
}


## ClinicianExample 0002

User: Show monthly cost for clinician Tatiana Ortiz.

Assistant:
{
  "text": "Here are the monthly costs for clinician Tatiana Ortiz.",
  "rows": [
    {"service_month": "september", "total_cost": 3150.75},
    {"service_month": "october", "total_cost": 2980.50},
    {"service_month": "november", "total_cost": 3105.25}
  ],
  "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>$3,150.75</td></tr><tr><td>October</td><td>$2,980.50</td></tr><tr><td>November</td><td>$3,105.25</td></tr></tbody></table></div>"
}


## ClinicianExample 0003

User: Show year-to-date hours for clinician Tatiana Ortiz.

Assistant:
{
  "text": "Here are the year-to-date hours for clinician Tatiana Ortiz.",
  "rows": [
    {"clinician_name": "tatiana ortiz", "total_hours": 120.75}
  ],
  "html": "<div class='summary-cards'><div class='card'><div class='label'>YTD Hours</div><div class='value'>120.75</div></div></div>"
}


## ClinicianExample 0004

User: Show year-to-date cost for clinician Tatiana Ortiz.

Assistant:
{
  "text": "Here is the year-to-date cost for clinician Tatiana Ortiz.",
  "rows": [
    {"clinician_name": "tatiana ortiz", "total_cost": 8900.25}
  ],
  "html": "<div class='summary-cards'><div class='card'><div class='label'>YTD Cost</div><div class='value'>$8,900.25</div></div></div>"
}


## ClinicianExample 0005

User: Which students does clinician Tatiana Ortiz support?

Assistant:
{
  "text": "Here are the students supported by clinician Tatiana Ortiz.",
  "rows": [
    {"student_name": "jack garcia"},
    {"student_name": "ava johnson"},
    {"student_name": "liam martinez"}
  ],
  "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Student</th></tr></thead><tbody><tr><td>Jack Garcia</td></tr><tr><td>Ava Johnson</td></tr><tr><td>Liam Martinez</td></tr></tbody></table></div>"
}


## ClinicianExample 0006

User: Compare clinicians Tatiana Ortiz and Michael Reed by monthly hours.

Assistant:
{
  "text": "Here is the monthly hourly comparison for clinicians Tatiana Ortiz and Michael Reed.",
  "rows": [
    {"service_month": "september", "clinician": "tatiana ortiz", "total_hours": 42.0},
    {"service_month": "september", "clinician": "michael reed", "total_hours": 38.5},
    {"service_month": "october", "clinician": "tatiana ortiz", "total_hours": 37.0},
    {"service_month": "october", "clinician": "michael reed", "total_hours": 41.25}
  ],
  "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Clinician</th><th>Total Hours</th></tr></thead><tbody><tr><td>September</td><td>Tatiana Ortiz</td><td>42.0</td></tr><tr><td>September</td><td>Michael Reed</td><td>38.5</td></tr><tr><td>October</td><td>Tatiana Ortiz</td><td>37.0</td></tr><tr><td>October</td><td>Michael Reed</td><td>41.25</td></tr></tbody></table></div>"
}


## ClinicianExample 0007

User: Compare clinicians Tatiana Ortiz and Michael Reed by monthly cost.

Assistant:
{
  "text": "Here is the monthly cost comparison for clinicians Tatiana Ortiz and Michael Reed.",
  "rows": [
    {"service_month": "september", "clinician": "tatiana ortiz", "total_cost": 3150.75},
    {"service_month": "september", "clinician": "michael reed", "total_cost": 2890.25},
    {"service_month": "october", "clinician": "tatiana ortiz", "total_cost": 2980.50},
    {"service_month": "october", "clinician": "michael reed", "total_cost": 3100.00}
  ],
  "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Clinician</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>Tatiana Ortiz</td><td>$3,150.75</td></tr><tr><td>September</td><td>Michael Reed</td><td>$2,890.25</td></tr><tr><td>October</td><td>Tatiana Ortiz</td><td>$2,980.50</td></tr><tr><td>October</td><td>Michael Reed</td><td>$3,100.00</td></tr></tbody></table></div>"
}


## ClinicianExample 0008

User: Show a clinician-type breakdown (LVN, RN, HA) for this school year.

Assistant:
{
  "text": "Here is the clinician-type breakdown for the school year.",
  "rows": [
    {"clinician_type": "lvn", "total_hours": 320.5},
    {"clinician_type": "rn", "total_hours": 285.0},
    {"clinician_type": "ha", "total_hours": 410.25}
  ],
  "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Clinician Type</th><th>Total Hours</th></tr></thead><tbody><tr><td>LVN</td><td>320.5</td></tr><tr><td>RN</td><td>285.0</td></tr><tr><td>HA</td><td>410.25</td></tr></tbody></table></div>"
}


## ClinicianExample 0009

User: Break down clinician cost by month for the school year.

Assistant:
{
  "text": "Here is the monthly cost breakdown by clinician type.",
  "rows": [
    {"service_month": "september", "clinician_type": "lvn", "total_cost": 12500.00},
    {"service_month": "september", "clinician_type": "rn", "total_cost": 11840.75},
    {"service_month": "september", "clinician_type": "ha", "total_cost": 14250.00},
    {"service_month": "october", "clinician_type": "lvn", "total_cost": 12150.50},
    {"service_month": "october", "clinician_type": "rn", "total_cost": 12080.00},
    {"service_month": "october", "clinician_type": "ha", "total_cost": 13820.25}
  ],
  "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Clinician Type</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>LVN</td><td>$12,500.00</td></tr><tr><td>September</td><td>RN</td><td>$11,840.75</td></tr><tr><td>September</td><td>HA</td><td>$14,250.00</td></tr><tr><td>October</td><td>LVN</td><td>$12,150.50</td></tr><tr><td>October</td><td>RN</td><td>$12,080.00</td></tr><tr><td>October</td><td>HA</td><td>$13,820.25</td></tr></tbody></table></div>"
}
