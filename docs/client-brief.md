\# Client Brief: Customs Broker's AI Document Extraction and Cross-Check Tool for Import Shipments



\## 1. Client



\*\*Company A — Navi Mumbai\*\*



A freight forwarder and customs broker operating at Nhava Sheva.



\- Employees: 85

\- Annual revenue: ₹60–75 crore

\- Documentation team: 14 employees



\## 2. Current Situation



Importers email invoices, packing lists and bills of lading as PDFs, scans or photographs.



Documentation executives currently:



1\. Receive shipment documents through email.

2\. Manually retype document information into an Excel checklist.

3\. Enter the information again into customs filing software.

4\. Ask senior employees to resolve doubts through a WhatsApp group.



This process creates significant manual work and increases the possibility of data-entry errors.



\## 3. Business Problem



The client estimates the following operational costs.



\### Manual data entry



\- Monthly shipments: 1,100

\- Time spent per shipment: 45 minutes

\- Staff hourly cost: ₹350



Annual calculation:



1,100 × 0.75 hours × 12 = 9,900 hours



9,900 × ₹350 = ₹34.65 lakh per year.



\### Shipment errors and delays



\- Annual shipments: 13,200

\- Error rate: 3%

\- Affected shipments: 396

\- Average cost per affected shipment: ₹9,000



396 × ₹9,000 = ₹35.64 lakh per year.



\### Total estimated annual impact



₹34.65 lakh + ₹35.64 lakh = \*\*₹70.29 lakh per year\*\*.



These figures are client-provided assumptions.



\## 4. Users and Decision Makers



The system has the following intended users:



\### Documentation Executive



\- Upload shipment documents.

\- Review AI-extracted information.

\- Correct incorrect or incomplete fields.

\- Resolve validation discrepancies.

\- Prepare shipment data for export.



\### Documentation Manager



\- Approve documentation workflows where applicable.

\- Review shipment data and discrepancies.

\- Monitor correction history and accuracy reports.



\### Importers



Importers provide shipment documents and answer queries. A customer-facing importer portal is outside the current scope.



\*\*Commercial decision maker:\*\* Managing Director.



\## 5. Client's Requirements and Expectations



The client describes the problem as follows:



"My team spends half the day typing what is already written in a PDF. I want to drop in a shipment's documents and get the data out ready to check. It must catch mismatches, like weights that differ across documents. I don't want to change our filing software."



The intended product should reduce manual data entry, identify inconsistencies across shipment documents and produce verified structured data without replacing existing customs filing software.



\## 6. Mandatory Requirements



\### 6.1 Shipment Management



\- Maintain a shipment record.

\- Support uploading the following documents:

&nbsp; - Commercial invoice.

&nbsp; - Packing list.

&nbsp; - Bill of lading.



\### 6.2 AI Document Extraction



Extract information from uploaded documents, including:



\*\*Shipment and party information\*\*

\- Parties.

\- Invoice number.

\- Invoice date.



\*\*Commercial information\*\*

\- Currency.

\- Incoterm.



\*\*Item information\*\*

\- Line items.

\- HSN codes.



\*\*Shipment and packaging information\*\*

\- Packages.

\- Weights.

\- Containers.



\### 6.3 Document Review Interface



Provide a review screen that displays:



\- Original document.

\- Extracted fields.

\- Low-confidence fields.

\- Information requiring human verification.



The original document must remain accessible during review.



\### 6.4 Cross-Document Validation



Implement checks for:



1\. Invoice total against the sum of invoice line items.

2\. Package information across the invoice, packing list and bill of lading where applicable.

3\. Weight information across all three documents.



Identify mismatches and make them visible to the user.



\### 6.5 CSV Export



\- Export verified shipment data.

\- Use the filing software's Excel import layout.

\- Do not invent the actual filing software's import template if it has not been supplied.



\### 6.6 Shipment Status List



Provide a shipment list showing shipment status and review progress.



\### 6.7 Correction History and Accuracy Reporting



\- Maintain edit history.

\- Record corrections made to extracted fields.

\- Support accuracy reporting per field and supplier.



\## 7. Core Build — Mandatory Take-Home Scope



The Software Engineering candidate must deliver the following end-to-end functionality in approximately 6–8 screens:



1\. Shipment list.

2\. Document upload.

3\. AI extraction.

4\. Side-by-side document review with cross-checks.

5\. CSV export.



\*\*Required roles:\*\*

\- Documentation Executive.

\- Documentation Manager.



\*\*Required AI functionality:\*\*

\- Field extraction with confidence scores.



\*\*Main engineering challenge:\*\*

Reliable cross-checking across three different shipment documents.



Payments, messages and external systems should be mocked where necessary. Sample data should be seeded into the application.



The core build takes priority over the remaining optional requirements.



\## 8. Out of Scope



The following are explicitly excluded:



\- Filing on the customs portal.

\- HSN classification.

\- Customs duty calculation.

\- Customer tracking portal.



The application should not claim to perform these functions.



\## 9. AI and Automation Requirements



A vision AI model reads uploaded documents and returns structured fields with confidence scores.



\### When AI extraction is incorrect or uncertain



The application must:



1\. Highlight low-confidence fields.

2\. Require human confirmation for low-confidence fields.

3\. Require human confirmation for fields involved in failed cross-checks.

4\. Prevent export until unresolved issues are cleared.

5\. Allow unreadable pages to be handled through manual entry.

6\. Record corrections to support accuracy reporting per field and supplier.



AI extraction must assist the documentation executive rather than independently approve shipment information.



The system must not silently export unverified information.



\## 10. Constraints



\### Data Confidentiality



\- Client prices are confidential.

\- Documents and extracted shipment information must be protected.

\- Hosting must be in India.

\- Role-based access control is required.

\- The selected AI provider must not train on client data.



\### Personal Data Protection



Importer contact information is personal data under the Digital Personal Data Protection Act, 2023.



The application must handle such information responsibly.



\### Document Characteristics



\- Scanned documents may be skewed.

\- Documents may contain bilingual content.

\- Document quality may vary.

\- Some pages may be unreadable.



The application must support appropriate handling of these conditions, including manual entry when extraction is not possible.



\### Intended Usage



The application is primarily designed for desktop use.



\## 11. Design Expectations



The client prefers a clean and minimal enterprise interface.



Design principles:



\- White space.

\- Restrained colour palette.

\- Clear typography.

\- Purposeful interface elements.

\- No unnecessary visual clutter.



The document review screen is especially important because documentation executives will use it throughout the working day.



It must:



1\. Display the original document and extracted fields side by side.

2\. Make uncertain fields immediately noticeable.

3\. Highlight validation discrepancies.

4\. Keep important review actions within one click.



The design should prioritize productivity, clarity and efficient document verification.



\## 12. Budget and Timeline



\- Client budget: ₹7.5 lakh.

\- Client implementation timeline: 6 weeks.



The take-home assignment has a separate candidate deadline.



\## 13. Client Success Metrics



The client expects:



\### Data entry time



Reduce average entry time per shipment from 45 minutes to under 15 minutes.



\### Field extraction accuracy



Achieve 95% field accuracy on 200 past shipments.



\### Shipment amendment reduction



Halve amended Bills of Entry within 3 months.



These are client targets, not achievements that the take-home application can claim without supporting evaluation.



\## 14. Sample Data



The following sample data is provided by the client.



| Shipment ID | Document | Supplier | Item | Quantity | Unit Price | Gross Weight (kg) |

|---|---|---|---|---:|---:|---:|

| SHP-24811 | Invoice | Company B (China) | LED panel light 40W | 2400 | USD 6.80 | 3120 |

| SHP-24811 | Packing list | Company B (China) | LED panel light 40W | 2400 | - | 3165 |

| SHP-24812 | Invoice | Company C (Sweden) | Steel ball valve DN50 | 180 | EUR 42.50 | 1460 |



\### Important sample-data observation



For shipment SHP-24811:



\- Invoice gross weight: 3,120 kg.

\- Packing list gross weight: 3,165 kg.

\- Difference: 45 kg.



This should produce a weight discrepancy requiring human review.



The application must not automatically assume which document contains the correct weight.



Shipment SHP-24812 has only an invoice record in the supplied sample. Additional documents, if needed for demonstration, must be clearly labelled as synthetic sample data.



\## 15. Additional Take-Home Assignment Requirements



The candidate must build a working product end to end.



\### Mandatory engineering requirements



\- Functional frontend.

\- Functional backend.

\- Database integration.

\- Authentication and sign-in.

\- Role-based access control.

\- Main workflows implemented using realistic sample data.

\- Functional AI or automation.

\- Appropriate handling of incorrect or uncertain AI output.

\- Responsive and polished interface.

\- Loading, empty and error states.

\- Tests for important business logic.

\- Input validation.

\- Access control.

\- No secrets in the repository.

\- No real personal information in the repository.

\- No dead buttons or fake functionality.



\### Required submission



One ZIP file, maximum 25 MB, containing:



1\. Technical Design Document (PDF or Word).

2\. `deployment.md`.



The project must have a public GitHub repository.



\### Technical Design Document must include



\- GitHub URL at the top.

\- Live application URL, if deployed.

\- Architecture and technology choices.

\- Data model.

\- Main workflows.

\- AI implementation.

\- UI and design decisions.

\- Scope cuts.

\- Future improvements.

\- Explicitly labelled assumptions.



\### deployment.md must include



\- Step-by-step local setup instructions.

\- Deployment instructions.

\- Environment variable names only, never their values.

\- Reviewer demo login credentials.



\### Additional rules



\- Work independently.

\- Preserve Git commit history.

\- Do not commit secrets or real personal data.

\- Keep the repository public until review is complete.

\- Label every assumption.

\- Do not claim features that are not implemented.



\*\*Assignment deadline: 9 November 2026, 11:59 PM IST.\*\*



---



\## 16. Source and Assumption Policy



The requirements above are based on the supplied client brief and take-home assignment.



The following information has not been supplied and must not be invented:



\- Actual customs filing software CSV/Excel import template.

\- Exact field-level confidence thresholds.

\- Permitted weight and currency rounding tolerances.

\- Exact document-specific field mappings.

\- Exact manager approval rules.

\- AI provider and model.

\- Hosting provider.

\- Document retention duration.

\- Detailed supplier identity-matching rules.



Any implementation decisions made in these areas must be explicitly documented as assumptions or configurable policies.



The application must not claim customs portal integration, HSN classification, duty calculation or regulatory certification.

