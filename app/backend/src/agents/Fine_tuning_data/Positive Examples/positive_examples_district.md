 ## DistrictExample 0001

User: Show district-wide monthly spend.

Assistant:

{
  "text": "Here is the district-wide monthly spend.",
  "rows": [
    {"service_month": "september", "total_cost": 182450.25},
    {"service_month": "october", "total_cost": 194380.50},
    {"service_month": "november", "total_cost": 201540.75}
  ],
  "html": "<div class='summary-cards'><div class='card'><div class='label'>Highest Month</div><div class='value'>$201,540.75</div></div></div><div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>$182,450.25</td></tr><tr><td>October</td><td>$194,380.50</td></tr><tr><td>November</td><td>$201,540.75</td></tr></tbody></table></div>"
}

## DistrictExample 0002

User: Show district-wide monthly hours.

Assistant:

{
  "text": "Here are the district-wide monthly hours.",
  "rows": [
    {"service_month": "september", "total_hours": 1180.5},
    {"service_month": "october", "total_hours": 1235.75},
    {"service_month": "november", "total_hours": 1290.25}
  ],
  "html": "<div class='summary-cards'><div class='card'><div class='label'>Highest Hours</div><div class='value'>1,290.25</div></div></div><div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Total Hours</th></tr></thead><tbody><tr><td>September</td><td>1180.5</td></tr><tr><td>October</td><td>1235.75</td></tr><tr><td>November</td><td>1290.25</td></tr></tbody></table></div>"
}

## DistrictExample 0003

User: Show school-year district spend.

Assistant:

{
  "text": "Here is the district’s total spend for the school year.",
  "rows": [
    {"service_month": "september", "total_cost": 182450.25},
    {"service_month": "october", "total_cost": 194380.50},
    {"service_month": "november", "total_cost": 201540.75},
    {"service_month": "december", "total_cost": 188320.00}
  ],
  "html": "<div class='summary-cards'><div class='card'><div class='label'>School-Year Spend</div><div class='value'>$766,691.50</div></div></div><div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>$182,450.25</td></tr><tr><td>October</td><td>$194,380.50</td></tr><tr><td>November</td><td>$201,540.75</td></tr><tr><td>December</td><td>$188,320.00</td></tr></tbody></table></div>"
}

## DistrictExample 0004

User: Which month had the highest district spend this school year?

Assistant:

{
  "text": "Here is the highest-spend month for the district this school year.",
  "rows": [
    {"service_month": "november", "total_spend": 201540.75}
  ],
  "html": "<div class='summary-cards'><div class='card'><div class='label'>Highest Month</div><div class='value'>November ($201,540.75)</div></div></div>"
}

## DistrictExample 0005

User: Which month had the lowest district spend this school year?

Assistant:

{
  "text": "Here is the lowest-spend month for the district this school year.",
  "rows": [
    {"service_month": "september", "total_spend": 182450.25}
  ],
  "html": "<div class='summary-cards'><div class='card'><div class='label'>Lowest Month</div><div class='value'>September ($182,450.25)</div></div></div>"
}

## DistrictExample 0006

User: Show me a trend chart for district spend.

Assistant:

{
  "text": "Here is the district spend trend over the school year.",
  "rows": [
    {"service_month": "september", "total_cost": 182450.25},
    {"service_month": "october", "total_cost": 194380.50},
    {"service_month": "november", "total_cost": 201540.75}
  ],
  "html": "<div class='bar-chart'><div class='bar-row'><span class='label'>September</span><div class='bar' style='width: 90%'></div><span class='value'>$182,450.25</span></div><div class='bar-row'><span class='label'>October</span><div class='bar' style='width: 96%'></div><span class='value'>$194,380.50</span></div><div class='bar-row'><span class='label'>November</span><div class='bar' style='width: 100%'></div><span class='value'>$201,540.75</span></div></div><div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>$182,450.25</td></tr><tr><td>October</td><td>$194,380.50</td></tr><tr><td>November</td><td>$201,540.75</td></tr></tbody></table></div>"
}

## DistrictExample 0007

User: Show a pivot of district spend by month.

Assistant:

{
  "text": "Here is a pivot of district spend by month.",
  "rows": [
    {"service_month": "september", "total_cost": 182450.25},
    {"service_month": "october", "total_cost": 194380.50},
    {"service_month": "november", "total_cost": 201540.75}
  ],
  "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Total Spend</th></tr></thead><tbody><tr><td>September</td><td>$182,450.25</td></tr><tr><td>October</td><td>$194,380.50</td></tr><tr><td>November</td><td>$201,540.75</td></tr></tbody></table></div>"
}

## DistrictExample 0008

User: Compare district spend for September and October.

Assistant:

{
  "text": "Here is the district spend comparison for September and October.",
  "rows": [
    {"service_month": "september", "total_cost": 182450.25},
    {"service_month": "october", "total_cost": 194380.50}
  ],
  "html": "<div class='table-wrapper'><table class='analytics-table'><thead><tr><th>Month</th><th>Total Cost</th></tr></thead><tbody><tr><td>September</td><td>$182,450.25</td></tr><tr><td>October</td><td>$194,380.50</td></tr></tbody></table></div>"
}

## DistrictExample 0009

User: Show the district’s average monthly spend this school year.

Assistant:

{
  "text": "Here is the average monthly district spend for the school year.",
  "rows": [
    {"average_monthly_spend": 192790.50}
  ],
  "html": "<div class='summary-cards'><div class='card'><div class='label'>Average Monthly Spend</div><div class='value'>$192,790.50</div></div></div>"
}

## DistrictExample 0010

User: Show the district's total spend for November.

Assistant:

{
  "text": "Here is the district's total spend for November.",
  "rows": [
    {"service_month": "november", "total_cost": 201540.75}
  ],
  "html": "<div class='summary-cards'><div class='card'><div class='label'>November Spend</div><div class='value'>$201,540.75</div></div></div>"
}
