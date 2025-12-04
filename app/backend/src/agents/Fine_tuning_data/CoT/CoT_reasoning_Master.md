# CareSpend – Chain-of-Thought Reasoning Templates

Each section defines the hidden reasoning the model should use for a given canonical query.
Your fine-tuning script will:
- Look up the CoT by Canonical_ID
- Insert it into the `{"type": "thinking"}` field of the assistant message
- Pair it with the canonical SQL output JSON

---

## Canonical 0001 – Show monthly spend for {student}

The user is asking how much a specific student costs over time, so we need a month‑by‑month cost breakdown at the student level. Costs live on the `invoices` table as `total_cost`, so we can work entirely at the invoice level. We first filter invoices by `district_key` to keep results scoped to the district in question. We then match `student_name` case‑insensitively to the requested student, since user input may differ in capitalization. To show spend over time, we group by `service_month` (normalized to lower case for consistency) and sum `total_cost` in each group. The result is one row per service month with the total spend for that student in that month.

---

## Canonical 0002 – Show monthly hours for {student}

These questions are about hours of care, not cost, for a single student over time. Hours are recorded at the service line level in `invoice_line_items.hours`, so we need to join `invoice_line_items` to `invoices` to access both hours and the associated `service_month`. We filter by `district_key` on the invoices side and by the student name via `ili.student`, matching case‑insensitively to the supplied student name. To roll this up by month, we group by `i.service_month` (lowercased) and sum `ili.hours` within each month. The result is a month‑by‑month view of total hours delivered to that student.

---

## Canonical 0003 – Show year-to-date spend for {student}

Here the user wants to know how much they’ve spent on a student so far this year, which is a year‑to‑date view at the invoice level. We use the `invoices` table because it already has `total_cost` per invoice and student-level fields such as `student_name`, `service_month`, and `status`. We filter by `district_key` and match `student_name` case‑insensitively to the requested student. To make this year‑to‑date, we restrict `invoice_date` so that its year matches the current year, effectively limiting the results to invoices from January 1 through today. Instead of aggregating to a single number, we return invoice‑level details (invoice_number, student_name, total_cost, service_month, status) ordered by `invoice_date` descending so the user sees the full YTD invoice history behind the total.

---

## Canonical 0004 – Show year-to-date hours for {student}

These queries ask for the total hours a student has received this year, so we focus on year‑to‑date service hours at the invoice level. The `invoices` table carries `total_hours` per invoice, which we can use directly without aggregating line items. We filter invoices to the relevant district via `district_key` and match `student_name` case‑insensitively to the requested student. To enforce the YTD window, we compare the year of `invoice_date` to the current year so that only invoices from this calendar year are included. We return invoice_number, student_name, total_hours, service_month, and status, sorted by `invoice_date` descending so the most recent hours appear first. This gives a detailed picture of all hours billed for that student so far this year.

---

## Canonical 0005 – Which students have the highest total spend this school year?

These questions are about the most expensive students in the current school year, so we need to rank students by school‑year spending. The `invoices` table has `total_cost` at the student‑invoice level, which is sufficient for this aggregation. We use a school‑year CTE (sy) to compute a start date of July 1 of the current year and an end date of June 30 of the following year, then filter `invoice_date` so only invoices between `sy.start` and `sy.end` are considered. Within that window, we filter by `district_key` to scope to a single district. We group by `student_name` (normalized to lower case for consistency) and compute `SUM(total_cost)` as each student’s total school‑year spend. Finally, we order the results by total_spend in descending order and limit to a small number of top students, surfacing those with the highest costs.

---

## Canonical 0006 – Which students have the highest total hours this school year?

Here the user wants to see which students receive the most service hours across the school year, not the highest costs. We again treat the school year as a July‑through‑June date range using a CTE. We work from the `invoices` table, which includes `total_hours` per student invoice. After filtering to the correct district via `district_key` and restricting `invoice_date` between `sy.start` and `sy.end`, we group by `student_name` (lowercasing for consistency) and calculate `SUM(total_hours)` as the total hours per student. The results are then ordered by total_hours in descending order and limited to the top few students. This surfaces the students who are receiving the greatest number of billed hours during the current school year.

---

## Canonical 0009 – Which students started receiving services this school year?

These questions are about “new” students, meaning students whose services began in the current school year. To determine that, we first find, for each student, the earliest invoice date in the dataset for that district. We compute this in a subquery or CTE that groups by `LOWER(student_name)` and uses `MIN(invoice_date)` as `first_date`. Next, we compute the current school‑year start and end dates (July 1 to June 30 of the following year) in a CTE named `sy`. We join or cross‑join `first_invoice` with `sy` and filter on `first_date BETWEEN sy.start AND sy.end` so that we keep only students whose first invoice falls inside the current school year. The final result is a list of students whose services began this school year, along with the date their first invoice appeared.

---

## Canonical 0011 – Show total spend for all students by month

These prompts ask for a districtwide monthly spending breakdown across all students. We use the `invoices` table, where total cost for each student invoice is stored in `total_cost` along with a `service_month` attribute that represents the billing month. We filter rows by `district_key` to restrict the view to a single district. There is no need to filter by student because the user wants totals for all students combined. We then group by `service_month` (normalized to lower case) and calculate `SUM(total_cost)` for each group. The result is a simple month‑by‑month summary of total student-service spending for the entire district.

---

## Canonical 0013 – Compare two students by monthly spend

These questions all involve comparing the monthly spend for two named students. We again use the `invoices` table because student‑level cost is available there as `total_cost` with a corresponding `service_month`. We filter by `district_key` to scope to the right district and then restrict `student_name` to be one of the two target students (`student_a`, `student_b`), using case‑insensitive matching. To support a side‑by‑side comparison, we group by both `student_name` and `service_month` so each row represents one student’s total cost in a given month. Within each group, we compute `SUM(total_cost)` to capture the full monthly spend for that student. The final result is a monthly cost breakdown for each of the two students that can be used to compare their spending patterns.

---

## Canonical 0014 – Compare two students by monthly hours

Here the user wants to compare service hours, not cost, for two students across months. Because hours are recorded per service line, we use `invoice_line_items` joined to `invoices` so we can see both hours and the `service_month`. We filter invoices by `district_key` and then restrict `ili.student` to be in the set of the two requested student names, matched case‑insensitively. To get monthly totals per student, we group by the student name and the `service_month` from the joined invoices. We then sum `ili.hours` within each group to get total hours per student per month. This produces a month‑by‑month hours comparison for the two students, showing how their service hours differ over time.

---

## Canonical 0015 – Show all invoices for {student}

These queries ask for the full invoice history for a specific student, without aggregation. We use the `invoices` table, where each row represents a distinct invoice and includes fields like `invoice_number`, `student_name`, `total_cost`, `service_month`, and `status`. We filter by `district_key` to make sure we only show invoices for the relevant district. We then match `student_name` case‑insensitively to the requested student. Because the user wants “all invoices,” we do not group or aggregate; instead we return each matching invoice as‑is. We order results by `invoice_date` descending so the most recent invoices appear first, giving a clear chronological billing history for the student.

---

## Canonical 0016 – Show services delivered to {student} over a date range

These questions are about listing services for a specific student within a specified date range. Conceptually, we want invoice‑level or service‑level records that fall between the start and end dates provided by the user. We filter data by `district_key` so the query stays scoped to the correct district, then match `student_name` (or the appropriate student field) case‑insensitively to the target student. To respect the date range, we constrain `invoice_date` (or service_date, depending on the final design) to fall between the provided start and end. The result should show each invoice or service entry that meets those criteria, including fields like invoice_number, service_month, total_cost, and status, giving a detailed view of everything delivered to that student in the chosen time window.

---

## Canonical 0017 – Show monthly spend for {vendor}

Here the user is asking about total cost per month for a single vendor. We query the `invoices` table joined to the `vendors` table so we can filter by vendor name while still accessing `service_month` and `total_cost`. We restrict invoices to the relevant district using `i.district_key`. We then match `v.name` case‑insensitively to the requested vendor name, because the user’s spelling or capitalization may differ from the stored value. To compute monthly totals, we group by `i.service_month` (lowercased for consistency) and sum `i.total_cost` within each month. The final result is a month‑by‑month summary of how much the district spent with that vendor.

---

## Canonical 0018 – Show monthly hours for {vendor}

These questions ask for total hours per month provided by a vendor. Hours live at the line item level in `invoice_line_items`, so we join `invoice_line_items` to `invoices` and then to `vendors`. We filter by `i.district_key` to limit to the correct district, and we match `v.name` case‑insensitively to the requested vendor. To roll up by month, we group by the `service_month` coming from `invoices`. Within each (vendor, month) group, we sum `ili.hours` to get the total hours delivered that month. The output shows, for each month, how many hours of services the vendor provided.

---

## Canonical 0019 – Show year-to-date spend for {vendor}

Here the user wants the total amount spent with a specific vendor so far this year. We use the `invoices` table joined to `vendors` so we can group by the vendor name while aggregating invoice‑level `total_cost`. We filter by `i.district_key` to scope to the correct district and match `v.name` case‑insensitively to the vendor of interest. To enforce the year‑to‑date window, we restrict `i.invoice_date` so that its year matches the current year, effectively including invoices from January 1 through today. We then compute `SUM(i.total_cost)` grouped by the vendor name to get a single YTD spend number for that vendor. The result is a straightforward year‑to‑date total cost for the selected vendor.

---

## Canonical 0021 – Which vendors have the highest total hours this school year?

These questions ask for vendors ranked by the total hours they have delivered in the current school year. We need service‑line hours, so we work from `invoice_line_items` joined to `invoices` and `vendors`. A school‑year CTE defines `sy.start` and `sy.end` as July 1 through June 30 of the following year. We filter by `i.district_key` and constrain `i.invoice_date` to fall within this school‑year window. We group by `v.name` and compute `SUM(ili.hours)` as each vendor’s total hours in the school year. Finally, we order the results by total_hours in descending order and limit to the top vendors, giving a ranked list of vendors with the most billed hours.

---

## Canonical 0022 – Compare {vendor_a} and {vendor_b} by monthly spend

Here we want to compare two vendors’ costs by month. We read from `invoices` joined to `vendors`, since `invoices.total_cost` holds cost information and `service_month` describes the billing month. We filter by `i.district_key` and restrict `v.name` to be one of `vendor_a` or `vendor_b`, using case‑insensitive comparisons. To show monthly totals for each vendor, we group by both `v.name` and `i.service_month`, normalizing them as needed (e.g., lowercasing). Inside each group, we sum `i.total_cost` to get the total monthly spend for that vendor. The result lets us compare the two vendors’ monthly spending patterns side by side.

---

## Canonical 0023 – Compare {vendor_a} and {vendor_b} by monthly hours

These prompts are similar to 0022 but focus on hours instead of cost. We use `invoice_line_items` joined to `invoices` and `vendors` so we have access to hours, vendor names, and billing months. We filter by `i.district_key` and restrict `v.name` to the two vendors being compared, using case‑insensitive matching. To compute total hours per month per vendor, we group by `i.service_month` and `v.name`. Within each group, we sum `ili.hours` to get the total hours delivered by that vendor in that month. The output makes it easy to compare how many hours each vendor provided month by month.

---

## Canonical 0024 – Show vendors with increasing spend over the last three months

These questions ask for vendors whose spending has been rising over successive months. We first compute monthly totals per vendor by aggregating `invoices.total_cost` grouped by `v.name` and a `year_month` value derived from `invoice_date`. This monthly_vendor CTE gives one row per vendor and month with a `total_spend`. Next, we use window functions (such as `LAG`) partitioned by vendor_name to look back at the previous month and the month before that. In the ranked CTE, we compare `total_spend` to `prev_month` and `prev_prev_month` and keep rows where both are not null and `total_spend > prev_month > prev_prev_month`. After filtering, we return the vendors whose last three months show strictly increasing spend, optionally ordering by the latest spend to highlight the most rapidly growing vendors.

---

## Canonical 0025 – Show vendors with decreasing spend over the last three months

This is the opposite of 0024: we want vendors whose spending has been declining over three consecutive months. We again compute a monthly_vendor CTE that aggregates `invoices.total_cost` per vendor and `year_month`. In the ranked CTE, we use window functions such as `LAG` to retrieve the spend for the previous two months for each vendor. We then filter for rows where the current `total_spend` is less than `prev_month`, and `prev_month` is less than `prev_prev_month`, and all three values are present. This ensures a strictly decreasing pattern over three months. The final query returns vendors whose monthly spend is trending down, optionally ordered by total_spend or by magnitude of decrease.

---

## Canonical 0026 – Show all invoices for {vendor}

These queries request invoice‑level history for a given vendor. We join `invoices` to `vendors` because invoices know the vendor via `vendor_id`, and vendor names come from the `vendors` table. We filter by `i.district_key` to keep the scope to one district and match `v.name` case‑insensitively to the requested vendor. We then return invoice_number, student_name, total_cost, service_month, and status for each matching invoice. There is no aggregation or grouping here because the user wants to see every invoice rather than a summary. We order by `i.invoice_date` descending so that the most recent vendor invoices appear at the top of the list.

---

## Canonical 0027 – Show invoice details for {vendor}

Here the user wants service‑line detail (line items) for a specific vendor’s invoices, rather than just invoice headers. We use `invoice_line_items` joined to `invoices` and `vendors` so we can access vendor name, invoice metadata, and individual service lines. We filter by `i.district_key` and match `v.name` case‑insensitively to the vendor of interest. We then select detailed fields such as invoice_number, service_month, service_date, student, clinician, service_code, hours, and cost. We order results by invoice_date, then invoice_number, then service_date so that the line items are grouped and sequenced in a human‑friendly billing order. This gives a granular breakdown of everything a vendor has billed.

---

## Canonical 0028 – Which vendors are serving the most students?

These questions focus on vendor reach, measured by how many distinct students each vendor serves. We work from `invoices` joined to `vendors` because `invoices.student_name` tells us which student a vendor served on a given invoice. We filter by `i.district_key` to stay within the current district. We group by `v.name` and compute `COUNT(DISTINCT i.student_name)` as the number of distinct students served by that vendor. After computing this metric, we order the results by students_served in descending order and limit to the top vendors so the report highlights vendors with the largest student caseloads.

---

## Canonical 0029 – Which vendors are providing the most hours?

Here the user is asking which vendors deliver the highest total number of service hours. We use `invoice_line_items` joined to `invoices` and `vendors` because hours live at the line-item level as `ili.hours`. We filter by `i.district_key` so we only consider the current district’s records. We group by `v.name` and aggregate `SUM(ili.hours)` as total_hours for each vendor. Finally, we order by total_hours in descending order and limit to the top few rows to see which vendors are providing the most hours overall.

---

## Canonical 0030 – Show monthly hours for clinician {clinician}

These questions concern how many hours an individual clinician has provided each month. Because hours are tracked per service line, we use `invoice_line_items` joined to `invoices`. We filter invoices by `i.district_key` and then match `ili.clinician` case‑insensitively to the requested clinician name. To see how hours vary over time, we group by `i.service_month` (lowercased) and compute `SUM(ili.hours)` within each month. The result is a month‑by‑month summary of the hours worked by that clinician.

---

## Canonical 0031 – Show monthly cost for clinician {clinician}

These prompts shift focus to cost per clinician rather than hours. We again join `invoice_line_items` to `invoices` because line items store `ili.cost` at the service level. We filter by `i.district_key` and by clinician name using a case‑insensitive match on `ili.clinician`. To compute monthly totals, we group by `i.service_month` and sum `ili.cost` in each group. This produces a monthly cost profile for the clinician, showing how much was billed for that provider in each month.

---

## Canonical 0032 – Show year-to-date hours for clinician {clinician}

Here the user wants total hours, year‑to‑date, for a specific clinician. We use `invoice_line_items` joined to `invoices` so we can see both clinician names and the associated invoice dates. We filter by `i.district_key` and match `ili.clinician` case‑insensitively to the target clinician. To enforce the YTD window, we restrict `i.invoice_date` so its year matches the current year. We group by the clinician name (normalized to lower case) and compute `SUM(ili.hours)` as total_hours for that clinician in the current year. The result is a single row giving the clinician’s year‑to‑date hours.

---

## Canonical 0033 – Show year-to-date cost for clinician {clinician}

These queries mirror 0032 but focus on cost. We again use `invoice_line_items` joined to `invoices`, because `ili.cost` stores the cost per service line and `i.invoice_date` carries the timing. We filter by `i.district_key` and case‑insensitively match `ili.clinician` to the clinician name provided. We restrict `i.invoice_date` to the current calendar year to create the YTD window. We then group by clinician (lowercased) and compute `SUM(ili.cost)` as total_cost. The result reports how much has been billed for that clinician so far this year.

---

## Canonical 0034 – Which clinicians have the highest total hours this school year?

These questions ask which clinicians have delivered the most hours in the current school year. We use `invoice_line_items` joined to `invoices` so we can combine line‑item hours with invoice dates. A school‑year CTE defines `sy.start` and `sy.end` from July 1 through June 30. We filter by `i.district_key` and limit `i.invoice_date` to be between `sy.start` and `sy.end`. We group by clinician name (lowercased) and compute `SUM(ili.hours)` as total_hours for each clinician. Finally, we order by total_hours descending and limit to the top clinicians to highlight those who worked the most hours in the school year.

---

## Canonical 0035 – Which clinicians have the highest total cost this school year?

Here the user wants to know which clinicians generate the highest billed cost over the school year. We again work from `invoice_line_items` joined to `invoices`, but this time we aggregate `ili.cost` rather than hours. We filter by `i.district_key` and restrict `i.invoice_date` to the school‑year window using a CTE with `sy.start` and `sy.end`. We group by clinician (normalized to lower case) and compute `SUM(ili.cost)` to get each clinician’s total cost. The result set is ordered by total_cost descending and limited to the top rows, revealing which clinicians are the most expensive over the current school year.

---

## Canonical 0036 – Show hours by clinician type for this school year

These questions focus on hours by clinician type (or license) across the school year. In the canonical query, clinician type is represented by `ili.service_code`, which we treat as the classification for grouping. We join `invoice_line_items` to `invoices` to access invoice dates and filter by `i.district_key`. A school‑year CTE defines the July‑through‑June window; we filter `i.invoice_date` into that range. We then group by `ili.service_code` and compute `SUM(ili.hours)` as total_hours for each clinician type. Ordering by total_hours descending highlights which provider types deliver the most hours across the school year.

---

## Canonical 0037 – Show cost by clinician type for this school year

Here we want total cost by clinician type, not hours, over the school year. We use the same join between `invoice_line_items` and `invoices`, with `ili.service_code` serving as the clinician type or license category. We filter invoices by `i.district_key` and restrict `i.invoice_date` to the school‑year range defined in the CTE. We group by `ili.service_code` and aggregate `SUM(ili.cost)` to get each type’s total billed cost. Results are ordered by total_cost descending, allowing users to see which clinician types drive the highest spending.

---

## Canonical 0038 – Compare clinician types by monthly hours

These questions are about monthly hours broken out by clinician type. We use `invoice_line_items` joined to `invoices` so we can combine line‑level hours with `service_month` and clinician type (`ili.service_code`). We filter by `i.district_key` to stay within the district. We group by `i.service_month` (lowercased) and `ili.service_code` so each row corresponds to one clinician type in one month. Within each group, we sum `ili.hours` to compute total hours delivered by that type in that month. This yields a grid of monthly hour totals by clinician type that can be used for comparisons and trend analysis.

---

## Canonical 0039 – Compare clinician types by monthly cost

These prompts mirror 0038 but look at cost instead of hours. We use the same join between `invoice_line_items` and `invoices`, and treat `ili.service_code` as the clinician type. We filter on `i.district_key` and group by both clinician_type and the lowercased `service_month`. Within each group, we compute `SUM(ili.cost)` to get total cost for that type and month. Ordering by month and type (or cost) provides a clear view of how spending varies across clinician types and months.

---

## Canonical 0040 – Compare clinicians {clinician_a} and {clinician_b} by monthly hours

These questions focus on comparing the monthly hours of two named clinicians. We use `invoice_line_items` joined to `invoices` so we can aggregate hours per clinician per month. We filter by `i.district_key` and restrict `ili.clinician` to the two clinicians provided, using case‑insensitive matching. To compare workloads over time, we group by the lowercased `service_month` and the lowercased clinician name. Within each group, we sum `ili.hours` to get the total hours that clinician worked in that month. The result is a set of monthly hour totals for each of the two clinicians, which can be ordered in a way that makes their month‑to‑month comparison easy.

---

## Canonical 0041 – Compare clinicians {clinician_a} and {clinician_b} by monthly cost

This is the cost analogue of 0040. We use `invoice_line_items` joined to `invoices`, filter on `i.district_key`, and restrict `ili.clinician` to the two selected clinicians case‑insensitively. Instead of hours, we aggregate `ili.cost`. We group by both the lowercased `service_month` and the lowercased clinician name, then compute `SUM(ili.cost)` within each group. The resulting table shows the monthly cost contribution of each clinician, making it straightforward to compare how expensive each clinician is on a month‑by‑month basis.

---

## Canonical 0045 – Show total district spend by month for this school year

These prompts ask for monthly districtwide spending, but limited to the current school year. We use the `invoices` table, where `total_cost` and `service_month` are available. A CTE defines the school year as running from July 1 of the current year through June 30 of the next year; we filter `invoice_date` into this range. We also filter by `district_key` to ensure we only consider invoices from the relevant district. We group by the lowercased `service_month` and sum `total_cost` within each group. The final result is a monthly spending timeline for the district over the school year.

---

## Canonical 0046 – Show total district hours by month for this school year

This is the hours equivalent of 0045. We use the `invoices` table, which stores `total_hours` per invoice along with `service_month`. As before, a school‑year CTE defines `sy.start` and `sy.end`, and we restrict `invoice_date` to that window. We filter invoices by `district_key` to keep the scope to a single district. We group by `service_month` (lowercased) and compute `SUM(total_hours)` for each month. The output is a month‑by‑month summary of total district service hours for the current school year.

---

## Canonical 0047 – Show year-to-date district spend

Here the user wants a single number: how much the district has spent so far this year. We use the `invoices` table because `total_cost` is already aggregated at the invoice level. We filter by `district_key` to limit the data to the correct district. To make the query year‑to‑date, we restrict `invoice_date` so that its year matches the current calendar year. There is no grouping because we want a single total, so we simply compute `SUM(total_cost)` across all matching invoices. The result is one scalar value representing YTD district spending.

---

## Canonical 0048 – Show year-to-date district hours

These questions ask for the total number of hours billed districtwide so far this year. We again use the `invoices` table, this time aggregating `total_hours`. We filter by `district_key` and restrict `invoice_date` so that its year equals the current year, which defines the YTD window. We then compute `SUM(total_hours)` over all invoices that meet those criteria. The output is a single value showing total hours delivered to the district year‑to‑date.

---

## Canonical 0049 – Show district spend trend over the school year

Here we want to understand how district spending changes across the school year. Conceptually this is similar to 0045 but framed as a “trend.” We use the `invoices` table, filter by `district_key`, and restrict `invoice_date` to the school‑year window defined in a CTE. We group by `service_month` and sum `total_cost` to get monthly totals. Because the user is interested in trends, we can interpret or present the results in chronological month order, showing how spend increases or decreases as the school year progresses.

---

## Canonical 0050 – Show district hours trend over the school year

This is the hours trend analogue of 0049. We work from the `invoices` table, filter by `district_key`, and restrict `invoice_date` to the school‑year range. We group by `service_month` and compute `SUM(total_hours)` to get monthly hour totals. When ordered by month, these results reveal how total service hours change across the school year, which can highlight periods of higher or lower staffing intensity.

---

## Canonical 0051 – Which month had the highest district spend this school year?

These questions look for the single month with the highest total district spend within the current school year. We effectively reuse the school‑year monthly spend aggregation: using `invoices`, filter by `district_key`, limit `invoice_date` to the school‑year window, group by `service_month`, and sum `total_cost` for each month. Once we have monthly totals, we order by total_spend in descending order and limit to one row. The resulting row indicates the month with the highest district spend, along with the amount.

---

## Canonical 0052 – Which month had the lowest district spend this school year?

This is the opposite of 0051: we are looking for the smallest monthly spend within the school year. We again aggregate spend by month using `invoices`, `district_key`, the school‑year date window, and `SUM(total_cost)` grouped by `service_month`. Instead of ordering descending, we order by total_spend ascending and limit to one row. The final row shows which month was least expensive for the district and what the spend was in that month.

---

## Canonical 0053 – What is the district's average monthly spend this school year?

These questions ask for an average monthly spend across the school year. We first compute monthly totals in a subquery or CTE by reading `invoices`, filtering by `district_key`, restricting `invoice_date` to the school‑year window, grouping by `service_month`, and summing `total_cost`. Once we have one total per month, we compute the average of those totals, often with rounding for readability. The final result is a single scalar that represents typical monthly district spending for the current school year.

---

## Canonical 0054 – What is the district's average monthly hours this school year?

This is the hours counterpart to 0053. We compute monthly hour totals in a CTE by filtering `invoices` by `district_key`, restricting `invoice_date` to the school‑year window, grouping by `service_month`, and summing `total_hours`. Then we compute the average of these monthly totals, optionally rounding to a reasonable precision. The final output is a single value showing the average number of hours provided per month during the school year.

---

## Canonical 0055 – Compare district spend for {month_a} and {month_b}

These queries compare districtwide spending between two named months. We use the `invoices` table and filter by `district_key` to stay within the district. We match `service_month` case‑insensitively against the two requested months (`month_a` and `month_b`), typically via an IN condition. We group by the normalized `service_month` and compute `SUM(total_cost)` for each month. The result is two rows, one per month, showing total district spend in each, which can be directly compared to see which month cost more.

---

## Canonical 0056 – Compare district hours for {month_a} and {month_b}

These prompts ask for a similar comparison but focused on hours instead of cost. We again use `invoices`, filter by `district_key`, and restrict `service_month` to the two requested months in a case‑insensitive way. We group by `service_month` and compute `SUM(total_hours)` for each. The output is a pair of rows, each giving the total hours provided in one of the months, letting the district compare service volume between the two periods.

---

## Canonical 0057 – Show total district spend for {month}

Here the user wants a single number: how much the district spent in a given month. We read from the `invoices` table, filter by `district_key`, and match `service_month` case‑insensitively to the user’s month parameter. We then aggregate `SUM(total_cost)` across all invoices that match. The result is a single scalar showing total district spend for the requested month.

---

## Canonical 0058 – Show total district hours for {month}

This is the hours analogue of 0057. We use `invoices`, filter by `district_key`, and match `service_month` case‑insensitively to the requested month. Instead of summing cost, we compute `SUM(total_hours)` across all matching invoices. The result is a single value showing the total service hours billed to the district in that month.

---

## Canonical 0059 – Show district spend since the start of this school year

These questions are about school‑year‑to‑date spend, broken out by month. We define the school year via a CTE with `sy.start` on July 1 of the current year and `sy.end` on June 30 of the next. We query `invoices`, filter by `district_key`, and require `invoice_date` to fall between `sy.start` and `sy.end`. We group by `service_month` and sum `total_cost` for each month, giving a month‑by‑month school‑year spend timeline. Ordered chronologically, this shows how district spending has accumulated since the school year began.

---

## Canonical 0060 – Show invoice details for {student} for {month}

These queries ask for detailed invoice line items for a specific student within a specific month. We use `invoice_line_items` joined to `invoices` to access service_date, student, clinician, service_code, hours, cost, and the invoice’s `service_month` and number. We filter by `i.district_key` to stay within the correct district and match `ili.student` case‑insensitively to the requested student name. We also filter `i.service_month` to the given month, again case‑insensitively. We then return detailed fields such as invoice_number, service_month, service_date, student, clinician, service_code, hours, and cost. Ordering by service_date and invoice_number produces a clear view of everything billed for that student in that month.

---

## Canonical 0061 – Show invoice details for {student} from {vendor} for {month}

These questions further restrict 0060 by vendor. We join `invoice_line_items` to `invoices` and then to `vendors` so we can filter by vendor name as well as by student and month. We filter by `i.district_key` and match `v.name` case‑insensitively to the vendor specified by the user. We also match `ili.student` case‑insensitively to the student and `i.service_month` to the requested month. We select the same detailed line‑item fields (invoice_number, service_month, service_date, student, clinician, service_code, hours, cost). Ordering by service_date and invoice_number makes it easy to understand all services that a specific vendor delivered to a specific student during the given month.

---
