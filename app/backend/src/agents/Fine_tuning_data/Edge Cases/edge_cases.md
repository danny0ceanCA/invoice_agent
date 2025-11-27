# ============================
# CARESPEND EDGE CASE TRAINING SET
# 50 High-Value Failure & Clarification Scenarios
# ============================

Each Edge Case includes:
- user message
- clarifying assistant output
- CoT (explaining why SQL must NOT be run)

Format:
## EdgeCase XXXX
User:
Assistant_Text:
CoT:

---

## EdgeCase 0001 – Missing student name
User: "Show me the hours."
Assistant_Text: "I need a student name or 'all students' before I can run this report. Which student did you have in mind?"
CoT: "The user requested hours but did not specify a student, vendor, or the entire district. Hours queries require a clear scope. According to system rules, the agent must not guess missing filters and must ask a clarifying question instead of running SQL."

---

## EdgeCase 0002 – Missing student for cost query
User: "How much did they cost?"
Assistant_Text: "I’m not sure which student you mean. Can you provide a student name?"
CoT: "The pronoun 'they' is ambiguous because no prior context exists. SQL should not run without a clear student filter, so the assistant must ask for clarification."

---

## EdgeCase 0003 – Ambiguous last name
User: "Show me invoices for Garcia."
Assistant_Text: "Several students match the name Garcia. Which specific student do you mean?"
CoT: "Last names alone may match multiple students. The system requires explicit disambiguation before running SQL. A clarifying question is necessary."

---

## EdgeCase 0004 – Student not found
User: "How many hours did Xyzantha receive?"
Assistant_Text: "I couldn’t find any students matching that name. Could you check the spelling?"
CoT: "The requested student does not exist in the dataset. Running SQL would return an empty result set, and system rules state we must ask for confirmation when user input appears incorrect."

---

## EdgeCase 0005 – Invalid month
User: "Show me spend for Smarch."
Assistant_Text: "Smarch isn’t a valid month. Could you provide a valid service month?"
CoT: "Service months must match the data in invoices.service_month. 'Smarch' is invalid, so SQL must not run. Request clarification."

---

## EdgeCase 0006 – Misspelled month
User: "Show me hours for Octuber."
Assistant_Text: "Did you mean October? Please confirm before I run the report."
CoT: "Misspelling detected. SQL must not assume the intended month. Clarification is required."

---

## EdgeCase 0007 – Missing vendor name
User: "Show me the vendor hours."
Assistant_Text: "Which vendor should I use? Please provide a vendor name."
CoT: "The query requires a vendor filter. The system prohibits assumptions. Ask for clarification."

---

## EdgeCase 0008 – Vendor not found
User: "Show me hours for VendorZebra."
Assistant_Text: "I couldn’t find a vendor matching that name. Can you double-check the spelling?"
CoT: "Vendor does not exist in vendors table; SQL would produce no results. Assistant must clarify instead of running empty query."

---

## EdgeCase 0009 – Out-of-domain query (hiring teachers)
User: "How many teachers were hired last year?"
Assistant_Text: "I can only answer questions about invoices, hours, students, and vendors. Could you rephrase your question?"
CoT: "Question is outside the invoice analytics domain. The system requires refusing with a helpful clarification."

---

## EdgeCase 0010 – Asking about contracts or HR
User: "Show me the HR staff details."
Assistant_Text: "I can only respond to invoice and service-hour analytics. What invoice-related data can I help you with?"
CoT: "Outside domain. Must redirect user."

---

## EdgeCase 0011 – Missing scope for “compare”
User: "Compare them."
Assistant_Text: "Compare who? I need the specific students or vendors you want to compare."
CoT: "System requires identifiable entities. No prior scope exists."

---

## EdgeCase 0012 – Missing invoice number for detail
User: "Show me the invoice detail."
Assistant_Text: "Which invoice number should I use? I need a specific invoice."
CoT: "Invoice-detail queries require invoice_number based filtering. Must not run SQL without it."

---

## EdgeCase 0013 – Asking for invoice detail when previous result was NOT invoice summary
User: “Show me the detailed breakdown.”
Assistant_Text: "I need either a specific student or invoice number to provide a detailed breakdown."
CoT: "No invoice context exists, so agent must ask for a clarifying detail."

---

## EdgeCase 0014 – Asking for “top vendors” without timeframe
User: "Who are the top vendors?"
Assistant_Text: "Do you want top vendors by hours or by cost, and for which timeframe?"
CoT: "Ambiguous metrics/time periods must be clarified."

---

## EdgeCase 0015 – Asking “show me more” without context
User: "Show me more."
Assistant_Text: "What additional information are you looking for? Hours, cost, or vendor details?"
CoT: "System rules prohibit guessing user intent."

---

## EdgeCase 0016 – Pronoun without context (“her”)
User: "How much did she cost?"
Assistant_Text: "Which student are you referring to?"
CoT: "No active student scope exists; pronoun is ambiguous."

---

## EdgeCase 0017
User: "Show me all the service details."
Assistant_Text: "I can show detailed service entries, but I need a student, vendor, or invoice number. Which one should I use?"
CoT: "The user asked for service details, which requires a student, vendor, or invoice filter. System rules forbid running SQL without essential filters, so the assistant must ask for clarification instead of executing a query."
