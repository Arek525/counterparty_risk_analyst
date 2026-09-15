# Third-Party Information Security Standard

Synthetic portfolio demonstration; not legal advice or a statement of any real organization's practices. Northstar Labs and all named suppliers are fictional.

Owner: Head of Information Security. Approver: Northstar Risk Committee. Version: 1.0. Effective: 2026-09-15. Review due: 2027-09-15. Policy set: Northstar Labs Third-Party Assurance Standard.

## 1. Purpose, applicability and definitions

This standard describes the security baseline for assessed technology relationships. Its purpose is to make the boundary between a supplier's service and Northstar's own configuration visible before either party relies on the other. The six identified SEC controls below are the supplier obligations in this document. Other paragraphs explain those controls or assign internal Northstar responsibilities; they do not add unlisted supplier obligations. A missing document is a reason to request evidence, not evidence that a control operates or fails.

The baseline addresses technology suppliers storing Northstar data or accessing Northstar systems. The assessment records purpose, shared data, system access and business criticality in the relationship context. Conditional controls distinguish personal-data processing, privileged access and high business criticality. The encryption baseline in this standard applies to relationships involving personal data. The access lifecycle control is limited to relationships with privileged access. Security reviewers consider other data and access arrangements manually before approving the relationship.

Northstar data means information supplied by Northstar or produced for it through the assessed service. A privileged account can alter service configuration, grant access, inspect protected records or bypass ordinary user restrictions. Supplier personnel includes employees and authorized contractors acting under the supplier's direction. A declaration describes what a supplier says; independent evidence describes work performed by an assessor outside the operating team. Neither label guarantees truth, coverage or freshness.

## 2. Precedence and shared responsibility

This document forms one standard with the privacy, governance and incident documents. The privacy document defines the end-of-service deletion trigger; the incident document defines the initial notification clock. Security terminology does not replace those definitions. Where a contractual schedule appears inconsistent, Northstar Security and Procurement must record the conflict, identify the binding agreement and obtain an owner decision before treating the policy as satisfied. Reviewers do not infer an exception from silence or from a previous approval.

The Business Owner must describe the architecture boundary, including customer-managed configuration, supplier infrastructure and shared operational tasks. For example, a customer may control ordinary user invitations while a supplier controls its support accounts and storage keys. A diagram is useful only when it names who operates each component and identifies which environment it represents. Marketing diagrams often omit administrative paths. Northstar Security must compare the diagram with the access description instead of assuming that a hosted service has no access to customer records.

## 3. Ownership and inventory

SEC-03 — Severity: Medium. Supplier accountability for security.

The supplier must name an accountable security owner and maintain a current inventory of controls and assets supporting the assessed service.

The owner can be a role backed by a monitored address; publishing a personal telephone number is unnecessary. The inventory explains the production boundary, supporting identity services, operational tooling and material dependencies. Evidence can include a dated ownership statement and a scoped asset register with sensitive identifiers redacted. The useful question is whether an operator can identify what protects this service and who resolves an exception, rather than whether a long spreadsheet exists.

Northstar Third-Party Risk must record the evidence date, service name, coverage period and declared author. A generic enterprise control catalogue may establish intent without demonstrating service coverage. When a supplier has acquired a business or replaced an operational platform, Northstar Security must check whether the inventory reflects that change. A pending update remains visible in the review record and is assigned to an owner with a due date.

## 4. Identity and privileged access

SEC-01 — Severity: High. Applies when privileged access is present.

For relationships with privileged access, the supplier must enable MFA for every privileged account, including supplier support accounts accessing Northstar systems or the assessed service.

This baseline includes interactive administrative paths and support escalation paths. MFA means multi-factor authentication using distinct factor categories. A protected ordinary user login does not establish that a separate administrative interface has the same protection. Northstar Security must ask which account populations and authentication paths the declaration covers. Evidence may describe the identity provider, enforcement policy, enrollment coverage and treatment of emergency access without disclosing recovery secrets.

SEC-04 — Severity: High. Applies when privileged access is present.

For relationships with privileged access, supplier personnel must receive approved least-privilege access and have that access revoked promptly when their duties change or end.

Least privilege means access proportionate to an approved operational task. Prompt revocation is intentionally a contextual obligation rather than an invented universal number of hours. Useful records include an access request, approving role, effective entitlement and a completed removal example. A monthly review does not alone prove that a departure was handled when it occurred. Northstar reviewers distinguish preventive approval, event-driven removal and periodic reconciliation; each addresses a different failure mode.

Northstar's own administrators must configure the customer side of the service according to the agreed responsibility record. Supplier operation of an identity platform does not relieve Northstar of managing its own joiners and leavers. When a shared account is encountered, Security must establish its purpose and traceability before deciding whether evidence supports the access control. An exception has a named approver, compensating measures and an expiry; it is not hidden inside a favorable questionnaire answer.

## 5. Data protection and keys

SEC-02 — Severity: High. Applies when personal data is processed.

For relationships processing personal data, the supplier must keep Northstar data encrypted at rest across production storage, replicas, logs and backups.

The assessed boundary includes derived service records containing Northstar data. A production database statement alone leaves replicas and operational exports unexplained. Key management information helps reviewers understand who can decrypt records, how access is separated from routine application operation and how recovery is controlled. An encryption declaration establishes the stated storage protection; reviewers separately consider algorithm choice, implementation assurance and key-management practices.

Northstar Security must request an architecture explanation when data passes through temporary stores, analytics pipelines or support attachments. Redacted configuration evidence may show enforcement without revealing key material. Transport security and secrets handling belong in the architecture review as contextual considerations; this document does not introduce additional numbered supplier controls for them. If a storage component falls outside the declared boundary, the reviewer records that limit rather than broadening the declaration by assumption.

## 6. Vulnerabilities, development and change

SEC-05 — Severity: High. Vulnerability management.

The supplier must operate a documented vulnerability and patch process that prioritizes remediation using severity, exposure and service impact, including testing, change approval and tracked exceptions.

A useful process identifies intake sources, triage responsibility and the route from a finding to a deployed correction. Public exposure can make a moderately scored weakness urgent; a severe issue in an unreachable test component may call for a different response. This standard deliberately avoids a universal patch deadline. Northstar Security must examine whether the supplier can explain its prioritization and show the disposition of a meaningful sample rather than merely quote a policy title.

Testing and approval may be implemented through a controlled deployment pipeline, review gates or an emergency-change procedure. Separation between author and approver can reduce accidental release risk, but a checkbox does not establish that the gate cannot be bypassed. Reviewers look for a coherent example connecting a finding, risk decision, test result and deployment record. When an urgent repair bypasses a normal step, the relevant evidence includes the recorded reason and follow-up review under the same process.

Development practices, logging and monitoring provide context for that assessment. A supplier can use code review, dependency scanning, runtime detection and operational alerts to find weaknesses at different stages. Northstar Security must avoid interpreting a list of tools as proof that findings are resolved. Redacted samples can explain how an alert reaches an accountable operator and how the operator records closure. Detailed exploit payloads and production credentials are inappropriate review attachments.

## 7. Independent assurance and recovery context

SEC-06 — Severity: Medium. Applies when business criticality is high.

For high-criticality services, the supplier must provide current independent assurance evidence identifying the assessed service, covered controls, review period and material exclusions.

An independent report is useful only within its stated scope. A certificate may identify a management system while omitting the product under review. A report may cover the production platform but exclude a newly acquired support portal. Northstar Third-Party Risk must retain the exclusion in the assessment and seek an explanation of the uncovered service path. Describing a document as independent does not make every statement in a supplier-authored summary independently verified.

Backup and restoration practices provide context for the continuity obligation in the governance document. Evidence can identify recovery objectives, dependencies and a completed restore exercise. A backup exists to support a recovery outcome; its mere existence does not prove a usable restore. Northstar's Business Owner must explain the impact of service loss so Security can assess whether the evidence addresses the relationship's actual needs. The governance control remains the single supplier obligation for continuity and exit planning.

## 8. Review records and exceptions

Northstar Security must record the control, missing evidence, assessed impact, compensating measures, proposed expiry and responsible owner for each exception. The Head of Information Security approves security exceptions after consulting Privacy where personal data is involved. Northstar Third-Party Risk must schedule reassessment before expiry and keep the previous record available for comparison. Acceptance of residual risk is a human decision bound to the assessed service and policy version, not a change to the quoted source.

The review record distinguishes a supplier declaration, independently examined material and Northstar interpretation. Evidence freshness follows the service's change history and stated coverage period, not the date on which a file was uploaded. An old report with a recent filename remains old evidence. When the supplier cannot disclose a sensitive report, Northstar may arrange restricted review and record its actual scope; absence of a public copy does not justify inventing findings. These records support an accountable decision without presenting the assessment as a security certification.
