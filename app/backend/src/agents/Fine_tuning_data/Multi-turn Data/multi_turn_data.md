# ============================
# MULTI-TURN TRAINING SET
# 20 STRATEGIC CONVERSATIONS
# ============================

Each conversation teaches:
- follow-up context retention,
- pronoun resolution,
- maintaining active student/vendor filters,
- clarifying when follow-up is ambiguous,
- not broadening filters,
- correct SQL scoping after multi-turn reasoning.

Format:
## MultiTurn XXXX
Turn1_User:
Turn1_Assistant_Text:
Turn1_CoT:

Turn2_User:
Turn2_Assistant_Text:
Turn2_CoT:

Turn3_User:
Turn3_Assistant_Output_JSON:
Turn3_CoT:

---

## MultiTurn 0001 – Student Filter Persistence
Turn1_User: "Show me invoices for Jack Garcia."
Turn1_Assistant_Text: "Here are all invoices for Jack Garcia. Let me know if you want cost, hours, or trends."
Turn1_CoT: "User explicitly requested invoices for Jack Garcia. After retrieving invoices, Jack becomes ACTIVE_STUDENT_FILTER. No SQL executed in this example because we are only training follow-up behavior."

Turn2_User: "How many hours did he get last month?"
Turn2_Assistant_Text: "Just to confirm — do you want hours for Jack Garcia for last month?"
Turn2_CoT: "Pronoun 'he' refers to Jack Garcia based on ACTIVE_STUDENT_FILTER. Need to confirm month scope before SQL can run."

Turn3_User: "Yes."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT LOWER(i.service_month) AS service_month, SUM(ili.hours) AS total_hours FROM invoice_line_items ili JOIN invoices i ON ili.invoice_id = i.id WHERE i.district_key = :district_key AND LOWER(ili.student) LIKE LOWER('%jack garcia%') AND LOWER(i.service_month) = LOWER(:service_month) GROUP BY LOWER(i.service_month)\"}"
Turn3_CoT: "Final SQL uses ACTIVE_STUDENT_FILTER (Jack Garcia) and explicit month resolution from prior clarification. Query aggregates monthly hours using line items + invoices join."
---

## MultiTurn 0002 – Vendor Filter Persistence
Turn1_User: "Show me monthly spending for Always Home Nursing."
Turn1_Assistant_Text: "Here is the monthly spending for Always Home Nursing. Would you like hours or student-level detail?"
Turn1_CoT: "Vendor filter established. Vendor becomes ACTIVE_VENDOR_FILTER."

Turn2_User: "What about last year?"
Turn2_Assistant_Text: "Do you want last year's spend for Always Home Nursing?"
Turn2_CoT: "Pronoun 'what about' refers to previous vendor. Year filter missing, ask to confirm YTD vs school-year."

Turn3_User: "Year-to-date."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT SUM(i.total_cost) AS total_spend FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.district_key = :district_key AND LOWER(v.name) LIKE LOWER('%always home nursing%') AND strftime('%Y', i.invoice_date) = strftime('%Y','now')\"}"
Turn3_CoT: "Uses vendor filter + YTD logic. Maintains vendor context."

---

## MultiTurn 0003 – Missing Pronoun Context
Turn1_User: "Show me October invoices."
Turn1_Assistant_Text: "October invoices for which student or vendor?"
Turn1_CoT: "Cannot run SQL without knowing whether user wants student, vendor, or district-wide."

Turn2_User: "He had a lot of services."
Turn2_Assistant_Text: "Which student are you referring to?"
Turn2_CoT: "Pronoun 'he' ambiguous since no prior student context was set."

Turn3_User: "Jack Garcia."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT invoice_number, student_name, total_cost, service_month, status FROM invoices WHERE district_key = :district_key AND LOWER(student_name) LIKE LOWER('%jack garcia%') AND LOWER(service_month) = LOWER('october') ORDER BY invoice_date DESC\"}"
Turn3_CoT: "Student clarified. SQL executes for student + month."

---

## MultiTurn 0004 – District to Student Filter Transition
Turn1_User: "Show me district-wide monthly spend."
Turn1_Assistant_Text: "Here is district-wide monthly spending. Let me know if you want to narrow to a specific student or vendor."
Turn1_CoT: "District scope active."

Turn2_User: "How much did Carter cost?"
Turn2_Assistant_Text: "Looking at Carter Sanchez — do you want monthly or year-to-date?"
Turn2_CoT: "User moved from district → student. Student filter takes priority."

Turn3_User: "Monthly please."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT LOWER(service_month) AS service_month, SUM(total_cost) AS total_cost FROM invoices WHERE district_key = :district_key AND LOWER(student_name) LIKE LOWER('%carter sanchez%') GROUP BY LOWER(service_month)\"}"
Turn3_CoT: "Student override corrects from district→student. Produces monthly spend."

---

## MultiTurn 0005 – Conflicting Follow-Up (Student vs Vendor)
Turn1_User: "Show me invoices for Jack Garcia."
Turn1_Assistant_Text: "Here are the invoices for Jack Garcia. Would you like cost or hours next?"
Turn1_CoT: "Student context set."

Turn2_User: "What about Always Home Nursing?"
Turn2_Assistant_Text: "Are you switching to vendor Always Home Nursing, or comparing them with Jack Garcia?"
Turn2_CoT: "Conflicting entities (student → vendor). Clarify before altering scope."

Turn3_User: "Switch to vendor."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT LOWER(i.service_month) AS service_month, SUM(i.total_cost) AS total_cost FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.district_key = :district_key AND LOWER(v.name) LIKE LOWER('%always home nursing%') GROUP BY LOWER(i.service_month)\"}"
Turn3_CoT: "Vendor scope correctly replaces student scope."

---

## MultiTurn 0006 – Follow-Up Without Scope
Turn1_User: "Show me the hours."
Turn1_Assistant_Text: "Which student should I look up hours for?"
Turn1_CoT: "Missing scope → must clarify."

Turn2_User: "He had a lot last month."
Turn2_Assistant_Text: "Who do you mean by 'he'? I need the student’s name."
Turn2_CoT: "Still missing entity; pronoun ambiguous."

Turn3_User: "Carter Sanchez."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT LOWER(i.service_month) AS service_month, SUM(ili.hours) AS total_hours FROM invoice_line_items ili JOIN invoices i ON i.id = ili.invoice_id WHERE i.district_key = :district_key AND LOWER(ili.student) LIKE LOWER('%carter sanchez%') GROUP BY LOWER(i.service_month)\"}"
Turn3_CoT: "Student resolved; SQL valid."

---

## MultiTurn 0007 – Vendor Detail Follow-Up
Turn1_User: "Show me vendor costs for Always Home Nursing."
Turn1_Assistant_Text: "Here is the monthly spend for Always Home Nursing."
Turn1_CoT: "Vendor context established."

Turn2_User: "Show me the line items."
Turn2_Assistant_Text: "Do you want line-item details for a specific month or for all invoices from Always Home Nursing?"
Turn2_CoT: "Needs invoice_number or month; detail queries require specific filters."

Turn3_User: "October."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT i.invoice_number, i.service_month, ili.service_date, ili.student, ili.clinician, ili.service_code, ili.hours, ili.cost FROM invoice_line_items ili JOIN invoices i ON ili.invoice_id = i.id JOIN vendors v ON v.id = i.vendor_id WHERE i.district_key = :district_key AND LOWER(v.name) LIKE LOWER('%always home nursing%') AND LOWER(i.service_month) = LOWER('october') ORDER BY ili.service_date, i.invoice_number\"}"
Turn3_CoT: "Vendor + month filter resolved correctly → detailed line item SQL."

---

## MultiTurn 0008 – Student Follow-Up After No Results
Turn1_User: "Show me invoices for StudentWithoutHours."
Turn1_Assistant_Text: "I couldn’t find invoices for StudentWithoutHours. Would you like to check the spelling?"
Turn1_CoT: "No results found; must clarify before future SQL."

Turn2_User: "Show me his hours instead."
Turn2_Assistant_Text: "I still couldn’t match that student. Could you confirm the name?"
Turn2_CoT: "Pronoun refers to nonexistent student; still must clarify."

Turn3_User: "Try Carter."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT invoice_number, student_name, total_cost, service_month, status FROM invoices WHERE district_key = :district_key AND LOWER(student_name) LIKE LOWER('%carter%') ORDER BY invoice_date DESC\"}"
Turn3_CoT: "Student resolved; SQL valid."

---

## MultiTurn 0009 – Switch from One Student to Another
Turn1_User: "Show me hours for Jack Garcia."
Turn1_Assistant_Text: "Here are the hours for Jack Garcia. Need cost too?"
Turn1_CoT: "Student context = Jack Garcia."

Turn2_User: "How about Maria?"
Turn2_Assistant_Text: "Switching to Maria Lopez. Do you want hours or cost?"
Turn2_CoT: "Scope updated to Maria."

Turn3_User: "Hours."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT LOWER(i.service_month) AS service_month, SUM(ili.hours) AS total_hours FROM invoice_line_items ili JOIN invoices i ON ili.invoice_id = i.id WHERE i.district_key = :district_key AND LOWER(ili.student) LIKE LOWER('%maria lopez%') GROUP BY LOWER(i.service_month)\"}"
Turn3_CoT: "Correctly switches scope from Jack → Maria."

---

## MultiTurn 0010 – Multi-entity follow-up
Turn1_User: "Compare hours for Jack and Maria."
Turn1_Assistant_Text: "Do you want a month-by-month comparison?"
Turn1_CoT: "Two-student scope established."

Turn2_User: "Yes."
Turn2_Assistant_Text: "Okay — comparing monthly totals. Do you want cost as well?"
Turn2_CoT: "Clarifies optional dimension."

Turn3_User: "Just hours."
Turn3_Assistant_Output_JSON: "{\"sql\": \"SELECT LOWER(ili.student) AS student_name, LOWER(i.service_month) AS service_month, SUM(ili.hours) AS total_hours FROM invoice_line_items ili JOIN invoices i ON ili.invoice_id = i.id WHERE i.district_key = :district_key AND LOWER(ili.student) IN (LOWER('jack garcia'), LOWER('maria lopez')) GROUP BY LOWER(ili.student), LOWER(i.service_month)\"}"
Turn3_CoT: "Uses multi-student filter correctly."
