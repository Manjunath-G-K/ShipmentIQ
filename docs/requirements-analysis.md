# Requirements Analysis: Customs Broker Import Shipment Cross-Check Tool

## Source and audit basis

This document is based on `AGENTS.md`, the complete client brief in `docs/client-brief.md`, and the selected problem statement. The earlier version was written before the client brief was available; this revision corrects those omissions and supersedes the earlier source-gap statements.

The document separates requirements stated in the brief from assumptions and unresolved questions. It does not select technologies, define architecture, or claim that any client target has been achieved.

## 1. Product overview

Company A is a freight forwarder and customs broker operating at Nhava Sheva, Navi Mumbai. It has 85 employees, including a 14-person documentation team. The product is an AI-assisted import-shipment documentation tool for that team.

The product shall maintain a shipment record, accept the shipment's commercial invoice, packing list, and bill of lading, extract structured information from those documents, provide a human review experience, cross-check related information across documents, and export verified shipment data in the filing software's Excel import layout as CSV. It is intended to reduce retyping and identify inconsistencies without replacing the existing customs filing software.

The core build is an end-to-end workflow of approximately six to eight screens: shipment list, document upload, AI extraction, side-by-side document review with cross-checks, and CSV export, with the remaining screens needed to make that workflow functional.

AI output is proposed information, not proof of correctness. Human confirmation is required for low-confidence fields and fields involved in failed cross-checks. Export must not silently include unresolved or unverified information.

## 2. Actual client problem

### Explicit requirements and context from the brief

Importers currently send invoices, packing lists, and bills of lading as PDFs, scans, or photographs. Documentation executives currently:

1. receive shipment documents through email;
2. manually retype information into an Excel checklist;
3. enter the information again into customs filing software; and
4. ask senior employees to resolve doubts through a WhatsApp group.

The client wants to drop in a shipment's documents, obtain the data in a form ready for checking, catch mismatches such as differing weights, and continue using the existing filing software.

The client estimates 1,100 monthly shipments, 45 minutes of manual data entry per shipment, and an annual manual-entry cost of ₹34.65 lakh. The brief also estimates ₹35.64 lakh in annual cost from shipment errors and delays, for a total estimated annual impact of ₹70.29 lakh. These figures are client-provided assumptions and are not independently verified by this document.

### Product boundary

The product assists documentation work and prepares an import-ready export. It does not file on a customs portal, classify HSN codes, calculate customs duty, or provide a customer-facing importer tracking portal.

## 3. Target users and their responsibilities

### Documentation Executive — explicit user

- Upload shipment documents.
- Review AI-extracted information.
- Correct incorrect or incomplete fields.
- Resolve validation discrepancies.
- Prepare shipment data for export.
- Confirm low-confidence fields and fields involved in failed cross-checks.
- Manually enter information when a page cannot be read.

### Documentation Manager — explicit user

- Approve documentation workflows where applicable.
- Review shipment data and discrepancies.
- Monitor correction history.
- Monitor accuracy reports, including accuracy by field and supplier.

### Importer — external participant, not an application user in the MVP

Importers provide shipment documents and answer queries. A customer-facing importer portal is explicitly out of scope.

### Managing Director — commercial decision maker

The Managing Director is identified as the commercial decision maker, not as a required operational role in the product.

The exact permission matrix, manager-approval conditions, and whether a manager must approve every export are unresolved; the two required application roles and role-based access control are not unresolved.

## 4. Explicit functional requirements

The system shall:

1. Maintain a shipment record.
2. Support uploading commercial invoices, packing lists, and bills of lading.
3. Extract the following information from uploaded documents using a vision AI model:
   - parties;
   - invoice number;
   - invoice date;
   - currency;
   - incoterm;
   - line items;
   - HSN codes as present in the source documents;
   - packages;
   - weights; and
   - containers.
4. Provide a document review screen that keeps the original document accessible and displays the original document beside extracted fields.
5. Make low-confidence fields visible and identify information requiring human verification.
6. Require human confirmation for low-confidence fields.
7. Require human confirmation for fields involved in failed cross-checks.
8. Permit correction of incorrect or incomplete fields.
9. Permit manual entry for unreadable pages or when extraction is not possible.
10. Preserve edit history and record corrections to extracted fields.
11. Support accuracy reporting per field and supplier.
12. Run these cross-document checks:
    - invoice total against the sum of invoice line items;
    - package information across the invoice, packing list, and bill of lading where applicable; and
    - weight information across all three documents.
13. Identify mismatches and make them visible to the user.
14. Prevent export until unresolved issues are cleared; failed cross-checks and unconfirmed fields must not silently pass.
15. Export verified shipment data as CSV using the filing software's Excel import layout. The actual filing-software template must not be invented when it has not been supplied.
16. Provide a shipment list showing shipment status and review progress.
17. Provide authentication/sign-in and role-based access control for the required Documentation Executive and Documentation Manager roles.
18. Use realistic seeded sample data for the main workflows.

The product shall not fabricate AI values, treat confidence as proof of correctness, silently export unverified information, or claim HSN classification, duty calculation, customs-portal filing, or regulatory certification.

## 5. Non-functional requirements

### Reliability, validation, and auditability

- AI responses must be validated as structured data before downstream use.
- Incorrect, incomplete, invalid, or uncertain AI output must be surfaced for human action.
- A low-confidence field requires human confirmation; confidence alone cannot approve a field.
- A field involved in a failed cross-check requires human confirmation.
- Failed or unresolved validations must remain visible and must not silently pass.
- Corrections must preserve edit history and be usable for accuracy reporting by field and supplier.
- Export eligibility must be enforced by trusted application-side rules, not only by UI state.
- Important business logic must be tested, including extraction-result handling, cross-checking, correction history, role access, and export gating.

### Performance and evaluation targets

The client expects to reduce average entry time from 45 minutes to under 15 minutes per shipment, achieve 95% field accuracy on 200 past shipments, and halve amended Bills of Entry within three months. These are client success targets, not achievements of the take-home application. They require a defined evaluation process and must not be claimed without supporting measurement.

The brief does not provide latency, throughput, concurrency, availability, or recovery-time targets.

### Security, confidentiality, and privacy

- Client prices, documents, and extracted shipment information must be protected.
- Hosting must be in India.
- Role-based access control is required.
- The selected AI provider must not train on client data.
- Importer contact information must be handled responsibly as personal data under the Digital Personal Data Protection Act, 2023.
- Secrets must not be committed.
- Real personal information must not be included in the repository.
- All inputs must be validated and access control must be enforced; client-side authorization alone must not be trusted.

This document does not provide a legal compliance guarantee or regulatory certification.

### UI, device, and interaction quality

- The application is primarily designed for desktop use.
- The interface must be responsive, functional, and polished.
- The visual direction is clean and minimal enterprise: white space, restrained colour, clear typography, purposeful interface elements, and no unnecessary clutter.
- Loading, empty, and error states are required.
- The document review screen is the highest-priority working screen because executives use it throughout the day.
- Review actions should be kept within one click where the brief calls for that productivity behavior.

## 6. Mandatory MVP scope

### Core build

The candidate must deliver the core end-to-end functionality in approximately six to eight screens:

1. shipment list;
2. document upload;
3. AI extraction;
4. side-by-side document review with cross-checks; and
5. CSV export;

plus only the additional screens needed to make these workflows functional. The core build takes priority over optional requirements.

The core build must include the three document types, required extraction fields, confidence scores, human review, manual entry for unreadable pages, visible cross-checks, correction history, accuracy-reporting support, shipment status/review progress, the two required roles, and export gating.

### Mandatory engineering baseline

The take-home product must have a functional frontend, functional backend, database integration, authentication/sign-in, role-based access control, realistic seeded sample data, functional AI or automation, handling for incorrect or uncertain AI output, a responsive and polished interface, loading/empty/error states, tests for important business logic, input validation, access control, no secrets, no real personal information, and no dead buttons or fake functionality.

Payments, messages, and external systems may be mocked where necessary. This does not authorize claiming that those integrations exist.

## 7. Features explicitly out of scope

The brief explicitly excludes:

- filing on the customs portal;
- HSN classification;
- customs duty calculation; and
- a customer-facing importer tracking portal.

The following are also not to be claimed unless separately supplied as requirements:

- invented customs CSV/Excel columns, mappings, or template behavior;
- regulatory compliance certification or guarantee;
- AI approval without human review where required; and
- external system integration beyond the defined export and any clearly labelled mock.

HSN codes are an extraction field when present in source documents; HSN classification is out of scope.

## 8. End-to-end user workflows

### 8.1 Shipment list and intake

1. A signed-in user with an authorized role opens the shipment list.
2. The list shows shipment status and review progress.
3. The Documentation Executive creates or opens a shipment record.
4. The executive uploads the available commercial invoice, packing list, and bill of lading.
5. The system accepts the supported PDFs, scans, or photographs and reports processing state or errors.

### 8.2 AI extraction

1. Vision AI reads the uploaded documents, including varied-quality scans, skewed pages, and bilingual content where supported by the confirmed policy.
2. The system returns structured fields with confidence scores.
3. Low-confidence fields and information requiring verification are highlighted.
4. Invalid, missing, or unreadable results remain unresolved rather than becoming approved values.

### 8.3 Review and correction

1. The review screen displays the original document and extracted fields side by side.
2. The Documentation Executive verifies low-confidence fields and fields implicated by failed cross-checks.
3. The executive corrects incorrect or incomplete fields or manually enters values for unreadable pages.
4. The system records the original value, correction, field, supplier context, user, and time to the extent defined by the audit policy; the minimum required behavior is preserved edit/correction history.
5. Affected cross-checks are rerun or remain visibly unresolved after a correction.

### 8.4 Cross-document validation

1. The system compares invoice totals with the sum of invoice line items.
2. It compares package information across the invoice, packing list, and bill of lading where applicable.
3. It compares weights across all three documents.
4. It makes mismatches visible and identifies the information requiring human verification.
5. The executive resolves discrepancies; the Documentation Manager reviews or approves where applicable.

### 8.5 Export

1. The user requests CSV export of verified shipment data.
2. The system checks required confirmations, cleared cross-check issues, role authorization, and required review status.
3. If an issue remains unresolved, export is blocked with an actionable reason.
4. If eligibility conditions are met, the system produces a CSV matching the supplied filing-software Excel import layout.
5. The product does not submit the CSV to a customs portal or claim portal acceptance.

## 9. AI extraction requirements

- Use a vision AI model to read uploaded documents and return structured fields with confidence scores.
- Extract parties, invoice number, invoice date, currency, incoterm, line items, HSN codes as written in the documents, packages, weights, and containers.
- Highlight low-confidence fields.
- Require human confirmation for low-confidence fields.
- Require human confirmation for fields involved in failed cross-checks.
- Do not independently approve shipment information based on AI output.
- Validate structured output and surface malformed, missing, contradictory, or uncertain values.
- Support skewed scans, bilingual content, variable document quality, and some unreadable pages through appropriate handling; manual entry is required when extraction is not possible.
- Record corrections so accuracy can be reported per field and supplier.
- The AI provider and model are not specified. The selected provider must not train on client data.

Confidence scores indicate model uncertainty; they are not proof that a field is correct.

## 10. Cross-document validation requirements

The mandatory checks are:

1. Invoice total versus the sum of invoice line items.
2. Package information across the invoice, packing list, and bill of lading where applicable.
3. Weight information across the invoice, packing list, and bill of lading.

The system shall:

- identify mismatches and make them visible;
- identify fields requiring human verification when a check fails;
- prevent failed or unresolved checks from silently passing or permitting export;
- account for corrected values and avoid treating stale validation as current; and
- not assume which document is correct when values disagree.

The brief does not supply exact document-specific field mappings, permitted weight or currency rounding tolerances, or supplier identity-matching rules. These remain explicit configuration/policy questions rather than invented behavior.

The supplied sample must demonstrate the weight discrepancy for SHP-24811: invoice gross weight 3,120 kg versus packing-list gross weight 3,165 kg, a 45 kg difference requiring human review. The system must not automatically select the correct value.

## 11. Human review and correction requirements

- The original document must remain accessible during review.
- Extracted fields must be shown beside the source document.
- Low-confidence fields must be immediately noticeable.
- Information requiring human verification must be identified.
- Low-confidence fields and fields involved in failed cross-checks require human confirmation.
- The Documentation Executive must be able to correct incomplete or incorrect fields and manually enter values for unreadable pages.
- The Documentation Manager must be able to review shipment data and discrepancies and approve workflows where applicable.
- Edit history and correction records must be retained and support accuracy reporting by field and supplier.
- A correction must cause affected checks to be rerun or remain unresolved; it must not create an unverified pass.

The exact manager approval rules, confidence thresholds, correction-history retention period, and accuracy metric formula are unresolved.

## 12. Export eligibility rules

Export is permitted only for verified shipment data and only when:

- the user is signed in and authorized for export;
- the required human confirmations are complete;
- low-confidence fields requiring confirmation are confirmed;
- fields involved in failed cross-checks are confirmed and the discrepancy is resolved under the approved workflow;
- no required cross-check remains failed or unresolved; and
- the output can be generated using the supplied filing-software Excel import layout.

Export must be blocked when any required issue remains unresolved. The system must not silently export unverified information.

The actual filing-software import template has not been supplied and must not be invented. Export is a CSV deliverable matching that layout, not customs-portal filing.

## 13. Authentication and authorization

- Authentication/sign-in is mandatory.
- Role-based access control is mandatory.
- The required roles are Documentation Executive and Documentation Manager.
- The Executive role must support upload, review, correction, discrepancy resolution, and preparation for export.
- The Manager role must support review of shipment data/discrepancies, applicable workflow approval, correction-history monitoring, and accuracy-report monitoring.
- Access control must be enforced in trusted application logic and not only in the client interface.
- Unauthorized users must not access protected documents, extracted data, correction history, reports, or export actions.

The exact role-permission matrix, user provisioning, organization boundaries, session policy, and manager approval conditions are unresolved.

## 14. Data protection and security requirements

- Host the application in India.
- Protect confidential client prices.
- Protect uploaded documents and extracted shipment information.
- Ensure the selected AI provider does not train on client data.
- Handle importer contact information responsibly as personal data under the Digital Personal Data Protection Act, 2023.
- Do not commit secrets.
- Do not include real personal information in the repository.
- Use synthetic or clearly labelled sample data for development, testing, and demonstration.
- Validate uploaded documents, AI output, corrections, export requests, and authorization-sensitive inputs.
- Enforce authorization server-side/trusted-side; do not trust client-provided authorization or export eligibility.
- Handle errors without exposing confidential shipment information unnecessarily.

The brief does not specify encryption algorithms, retention/deletion periods, backups, data-residency details beyond India hosting, redaction, incident response, or a legal compliance certification process. No regulatory guarantee may be claimed.

## 15. Error and failure scenarios

The workflow must visibly and appropriately handle:

- failed document upload or processing;
- skewed scans;
- bilingual or otherwise difficult-to-read content;
- variable document quality;
- unreadable pages;
- missing, malformed, or uncertain AI output;
- low-confidence fields;
- invoice-total versus line-item-sum mismatch;
- package mismatch across applicable documents;
- weight mismatch across the three documents;
- a correction that makes a previous check stale;
- unauthorized access or action;
- export requested while unresolved issues remain; and
- export generation failure.

In all such cases the system must avoid fabricated success, make the issue visible, and provide the supported next action. Unreadable pages must be manually enterable. Retry behavior, notification behavior, and recovery-time targets are not defined by the brief.

## 16. Synthetic sample data requirements

The application must seed realistic sample data for the main workflows. The client-provided sample data is:

| Shipment ID | Document | Supplier | Item | Quantity | Unit price | Gross weight (kg) |
|---|---|---|---|---:|---:|---:|
| SHP-24811 | Invoice | Company B (China) | LED panel light 40W | 2,400 | USD 6.80 | 3,120 |
| SHP-24811 | Packing list | Company B (China) | LED panel light 40W | 2,400 | — | 3,165 |
| SHP-24812 | Invoice | Company C (Sweden) | Steel ball valve DN50 | 180 | EUR 42.50 | 1,460 |

Required sample behavior:

- SHP-24811 must show the 45 kg invoice/packing-list weight discrepancy and require human review.
- The application must not assume which SHP-24811 document has the correct weight.
- SHP-24812 has only an invoice record in the supplied sample.
- Any additional SHP-24812 documents used for demonstration must be clearly labelled synthetic sample data.
- No real personal information, credentials, secrets, or real customs records may be committed.
- Samples should cover successful extraction, low confidence, unreadable pages/manual entry, correction history, matching checks, mismatched checks, blocked export, and cleared export.

## 17. Acceptance criteria

The following acceptance criteria are tied to the traceability IDs in section 20:

1. **AC-01 / SHIP-01:** A signed-in authorized user can view a shipment list with shipment status and review progress and maintain a shipment record.
2. **AC-02 / DOC-01:** The workflow accepts a commercial invoice, packing list, and bill of lading for a shipment and shows processing state or a useful error.
3. **AC-03 / AI-01:** Seeded documents produce structured values for the required extraction fields, including parties, invoice number/date, currency, incoterm, line items, HSN codes as written, packages, weights, and containers, with confidence scores.
4. **AC-04 / AI-02 / REVIEW-01:** The review screen keeps the original document accessible beside extracted fields and highlights low-confidence and human-verification items.
5. **AC-05 / AI-03 / REVIEW-02:** A low-confidence field and a field involved in a failed check cannot be finalized without human confirmation.
6. **AC-06 / REVIEW-03:** A reviewer can correct an incorrect/incomplete field and manually enter a value for an unreadable page; the system preserves the edit/correction history.
7. **AC-07 / VAL-01:** The system demonstrates invoice-total versus line-item-sum checking, package checking across applicable documents, and weight checking across all three documents.
8. **AC-08 / VAL-02 / SAMPLE-01:** SHP-24811 visibly reports the 45 kg weight mismatch, requires human review, and does not automatically choose a correct document.
9. **AC-09 / EXP-01:** Export is blocked while any required low-confidence confirmation, failed cross-check, or other required issue remains unresolved.
10. **AC-10 / EXP-02:** After required confirmations and discrepancy resolution, the system exports verified shipment data as CSV according to the supplied filing-software Excel import layout; it does not claim customs-portal submission.
11. **AC-11 / REPORT-01:** Correction records support accuracy reporting by field and supplier, and a manager can monitor the history/reporting workflow.
12. **AC-12 / ROLE-01 / SEC-01:** Documentation Executive and Documentation Manager sign in with role-based access, and unauthorized users cannot access protected shipment data or protected actions.
13. **AC-13 / UI-01:** The core workflow is usable on desktop in an approximately six-to-eight-screen, clean and minimal enterprise interface with side-by-side review, visible discrepancies, clear typography, restrained colour, purposeful controls, and important review actions within one click where applicable.
14. **AC-14 / UI-02 / ENG-01:** Functional frontend/backend/database integration, loading/empty/error states, input validation, access control, important-business-logic tests, seeded sample data, and no dead buttons or fake functionality are demonstrable.
15. **AC-15 / SEC-02:** The implementation uses no committed secrets or real personal information, protects shipment data, is hosted in India, and uses an AI provider that does not train on client data.
16. **AC-16 / TARGET-01:** Any measurement of success targets uses a defined evaluation, including the 200-past-shipment sample for the 95% field-accuracy target; the application does not claim the target was achieved without evidence.

The exact filing-software template, confidence thresholds, rounding tolerances, manager approval policy, and accuracy-report formula must be supplied before their field-level acceptance tests can be finalized.

## 18. Assumptions and unresolved questions

### Assumptions for this analysis only

- “Verified shipment data” means data that has passed the required human confirmations and cross-check conditions; the client must confirm the final approval state.
- A shipment may not always contain all three documents because the brief says package checks apply “where applicable,” and SHP-24812 currently has only an invoice record.
- HSN codes are extracted as document-provided values; no classification or validation against a tariff system is assumed.
- Accuracy reporting will use correction history as its source of evidence, but the exact numerator, denominator, baseline, and reporting period are not defined.
- “Within one click” applies to important review actions in the review interface, but the specific actions and interaction count require design confirmation.

### Unresolved questions explicitly identified by the brief

- What is the actual filing software's Excel import layout, including columns, ordering, formats, encoding, and required fields?
- What are the exact field-level confidence thresholds?
- What weight and currency rounding/tolerance rules apply?
- What are the exact document-specific field mappings?
- What are the exact manager approval rules?
- Which AI provider and model may be used, and how will the no-training-on-client-data condition be verified?
- What document retention duration and deletion behavior apply?
- How are supplier identities matched across documents?
- Which fields are included in accuracy reports, and how is accuracy calculated per field and supplier?
- Are PDFs, scans, and photographs all required input formats for the take-home build, and what size/page limits apply?
- What bilingual languages and document-quality conditions must be supported?
- What are the user-provisioning, organization-boundary, session, and audit-retention rules?
- Which workflows require Documentation Manager approval, and can an executive resolve every discrepancy?
- What are the expected performance, availability, accessibility, and browser targets?

## 19. Risks and limitations

- The actual filing-software CSV/Excel template is not supplied, so export layout correctness cannot be verified against a real template.
- Exact thresholds and tolerances are not supplied, so a technically plausible check could disagree with operational policy unless these are confirmed.
- Vision AI may extract incorrect values even with high confidence; human review is essential.
- Skewed, bilingual, low-quality, and unreadable pages increase extraction and review risk.
- A document mismatch does not prove which source is correct; automatically choosing one could create a filing error.
- Corrections can make prior validation stale; export gating must use current review state.
- A field-accuracy target based on 200 past shipments needs a labelled evaluation set and a defined metric; it cannot be inferred from demo samples.
- The target of halving amended Bills of Entry within three months cannot be demonstrated by a take-home application alone without operational deployment data.
- India hosting and no-training AI processing are explicit constraints, but the provider, hosting arrangement, and verification evidence are unresolved.
- Handling importer contact information responsibly does not by itself establish legal compliance; no regulatory certification may be claimed.
- The six-week client timeline and ₹7.5 lakh budget are client planning constraints, not evidence that an implementation is complete or feasible within this document.

## 20. Requirements traceability

| ID | Original brief requirement | Requirements section(s) | Acceptance criterion |
|---|---|---|---|
| SHIP-01 | Maintain a shipment record; show shipment status and review progress | 4, 8.1, 16 | AC-01 |
| DOC-01 | Upload commercial invoice, packing list, and bill of lading | 4, 6, 8.1 | AC-02 |
| AI-01 | Vision AI extracts the named shipment, party, commercial, item, packaging, weight, and container fields with confidence scores | 4, 9 | AC-03 |
| AI-02 | Display low-confidence fields and information requiring human verification | 4, 9, 11 | AC-04 |
| AI-03 | Human confirmation for low-confidence fields and fields in failed cross-checks; no silent unverified export | 4, 9, 12 | AC-05, AC-09 |
| REVIEW-01 | Original document remains accessible beside extracted fields | 4, 8.3, 11 | AC-04 |
| REVIEW-02 | Executives correct incorrect/incomplete fields and manually enter unreadable pages | 3, 9, 11, 15 | AC-06 |
| REVIEW-03 | Maintain edit history and record corrections to extracted fields | 4, 9, 11 | AC-06 |
| REPORT-01 | Accuracy reporting per field and supplier; manager monitors it | 3, 4, 11 | AC-11 |
| VAL-01 | Invoice total versus invoice line-item sum | 4, 8.4, 10 | AC-07 |
| VAL-02 | Package information across invoice, packing list, and bill of lading where applicable | 4, 8.4, 10 | AC-07 |
| VAL-03 | Weight information across all three documents | 4, 8.4, 10, 16 | AC-07, AC-08 |
| VAL-04 | Identify mismatches and make them visible; do not assume the correct document | 4, 8.4, 10, 16 | AC-08 |
| EXP-01 | Export verified shipment data as CSV using filing software's Excel import layout; do not invent the template | 4, 7, 12, 19 | AC-10 |
| EXP-02 | Prevent export until unresolved issues are cleared | 4, 9, 10, 12 | AC-09, AC-10 |
| CORE-01 | Approx. six-to-eight-screen core build: shipment list, upload, extraction, side-by-side review/cross-checks, CSV export | 1, 6, 17 | AC-13 |
| ROLE-01 | Documentation Executive and Documentation Manager roles and responsibilities | 3, 6, 13 | AC-12 |
| SEC-01 | Authentication/sign-in, RBAC, access control, input validation | 5, 6, 13, 14 | AC-12, AC-14 |
| SEC-02 | Protect confidential prices, documents, extracted data; India hosting; AI provider does not train on client data | 5, 14 | AC-15 |
| PRIV-01 | Handle importer contact information responsibly under DPDP Act 2023 | 5, 14, 19 | AC-15 |
| DATA-01 | Skewed scans, bilingual content, variable quality, unreadable pages with manual entry | 9, 15 | AC-06, AC-14 |
| SAMPLE-01 | Seed realistic sample data; demonstrate SHP-24811 45 kg mismatch; label additional SHP-24812 documents synthetic | 6, 16 | AC-08, AC-14 |
| UI-01 | Desktop-first, clean/minimal enterprise interface; side-by-side review, visible uncertainty/discrepancies, one-click review actions | 5, 8.3, 11, 17 | AC-04, AC-13 |
| ENG-01 | Functional frontend/backend/database, functional AI/automation, loading/empty/error states, tests, no dead buttons/fake functionality | 5, 6, 15, 17 | AC-14 |
| TARGET-01 | Client success targets: under 15 minutes, 95% on 200 past shipments, half amended Bills of Entry | 2, 5, 17, 19 | AC-16 |
| OUT-01 | No customs portal filing, HSN classification, duty calculation, or importer tracking portal | 2, 7, 8.5, 9, 12 | AC-10, AC-15 |

