# Third-Party Privacy and Data Handling Standard

Synthetic portfolio demonstration; not legal advice or a statement of any real organization's practices. Northstar Labs and all named suppliers are fictional.

Owner: Privacy Lead. Approver: Northstar Risk Committee. Version: 1.0. Effective: 2026-09-15. Review due: 2027-09-15. Policy set: Northstar Labs Third-Party Assurance Standard.

## 1. Purpose, applicability and vocabulary

This document governs relationships in which personal data is processed. Its six identified PRI controls describe the supplier-facing baseline. The remaining paragraphs provide operational interpretation and Northstar responsibilities. They do not create additional supplier controls. The baseline is an internal assessment standard for the fictional organization, not a statement that every legal obligation has been captured. Northstar Privacy must determine the relevant legal and contractual context before approving an actual processing arrangement.

Personal data is information relating to an identifiable person in the assessed relationship. The relationship description records the intended purpose, categories of shared data and system access, and the importance of the service. Processing includes ordinary service operation and authorized support activity. A subprocessor performs processing for the supplier; a location can describe storage, routine computation or remote access, and those concepts are not interchangeable. A declaration is supplied by the counterparty, while independent evidence describes work performed outside its operating team.

Documented instructions are the authorized purposes and handling directions agreed for the assessed service. A deletion trigger is termination of that service or an authenticated deletion request from Northstar. Calendar days include weekends. An authenticated request is verified through the agreed channel before destructive action starts. Northstar Privacy must distinguish a valid request from a message whose sender or scope is uncertain, without allowing internal administrative delay to rewrite an agreed trigger.

## 2. Precedence and responsibilities

The information security document defines the encryption baseline, the governance document defines relationship ownership and the incident document defines initial incident notice. This document controls the interpretation of the deletion window and primary hosting location. Northstar Procurement must bring inconsistent schedules to Privacy before contract approval. Reviewers retain both conflicting source passages rather than silently selecting whichever gives a favorable result. A human owner resolves applicability and records the basis for the decision.

Northstar's Business Owner must map the intended data flow before sharing records. That map identifies collection, service use, routine output, support access and end-of-service handling. Privacy must compare the proposed purpose with the actual service configuration. For example, a contact directory used to send product notices differs from a dataset reused to train a supplier product. A vague description such as customer data hides the distinction and is insufficient for the internal review.

## 3. Processing agreement and instructions

PRI-01 — Severity: High. Applies when personal data is processed.

For relationships processing personal data, the supplier must have a signed DPA with Northstar before processing begins.

DPA means data processing agreement. The signed schedule identifies the assessed service and the parties acting in the arrangement. A supplier's public template can support negotiation but is not the same as an executed agreement. A signed-state declaration is the starting point for examining the service scope, date, signatories and schedules. Privacy determines the parties' roles and reviews the relevant contractual provisions.

PRI-05 — Severity: High. Applies when personal data is processed.

For relationships processing personal data, the supplier must process Northstar data only for documented purposes and minimize the data used to what those purposes need.

The purpose record describes the service outcome, categories involved and any operational access needed to deliver it. Minimization can concern fields, granularity, recipient groups or storage duration. Removing direct identifiers may reduce exposure while leaving indirect identification possible. Northstar Privacy must assess the proposed dataset in context rather than treating a masking label as proof that it contains no personal data. Worked samples should use synthetic values instead of copying customer records into assurance attachments.

A change from generating aggregate usage statistics to building user profiles changes the review question even if the infrastructure is unchanged. Northstar's Business Owner must raise such a change before expanding the use case. Privacy must record whether revised instructions, a new assessment or additional controls are needed. This internal change review explains the existing purpose-limitation control; it does not create a separate supplier obligation hidden in narrative text.

## 4. Locations and remote access

PRI-03 — Severity: High. Applies when personal data is processed.

For relationships processing personal data, the supplier must keep primary hosting and processing for the assessed service in the EU.

The hosting baseline concerns the assessed service's primary storage and routine computation. It is not a shortcut for evaluating every remote-access arrangement. A US support subprocessor can raise a question about transfer scope without changing the declared primary hosting region. Northstar Privacy must ask what records can be accessed, for what task, under whose authorization and with which safeguards. The presence of a US organization in a list is not by itself evidence that the primary platform is hosted there.

The service boundary includes production replicas when they participate in normal processing. An architecture narrative can explain exceptional recovery locations and the conditions under which they are used. Reviewers record any unresolved boundary separately instead of assigning a region to components the evidence does not describe. Location names in corporate addresses, legal notices or billing details do not establish where this service processes data. Exact quotes and source locations make these distinctions reviewable.

## 5. Subprocessor inventory and change review

PRI-04 — Severity: Medium. Applies when personal data is processed.

For relationships processing personal data, the supplier must maintain a current subprocessor inventory and give Northstar advance notice of changes so Privacy can review access scope and transfer safeguards.

An informative inventory names the entity, service function, access category and operating locations. Broad labels such as infrastructure or support can conceal materially different capabilities. A supplier can describe whether an operator sees customer content, pseudonymous telemetry or only a contact address. Northstar Privacy must compare the inventory with the architecture and the signed schedule. An omitted dependency remains a review gap even when another supplier entity holds a broadly worded certification.

Advance notice supports a decision before the changed processing takes effect; this standard intentionally does not invent a universal numerical notice period. The contractual schedule can specify a period appropriate to the relationship. Northstar Procurement must preserve that schedule with the review record. Privacy must document approval, conditions or an objection and identify the operational response if a change cannot be accepted. Privacy reviews transfer safeguards and subprocessor authorization together with the declared regional boundary.

## 6. Return, deletion and preservation boundaries

PRI-02 — Severity: High. Applies when personal data is processed.

For relationships processing personal data, the supplier must complete deletion of Northstar personal data within 30 calendar days after service termination or an authenticated deletion request, excluding documented preservation obligations and technically isolated backup cycles.

The comparable ordinary deletion-window declaration is the maximum ordinary deletion window after that trigger. It is not the lifetime of an active customer account, the age of an invoice or a general log retention period. A supplier stating a shorter operational target can be compared with the baseline only if the same trigger and scope apply. Northstar Privacy must seek clarification where a number refers to a different dataset or a different event. The review record preserves those different meanings until the supplier clarifies the applicable commitment.

Preservation obligations are documented exceptions with a stated basis, restricted purpose and review point. Technically isolated backups are outside the ordinary window only when their cycle and isolation are explained. Northstar Privacy must record what remains, why it remains and when the exception is reconsidered. A blanket phrase such as backups retained as needed does not establish a bounded exception. Data restored during recovery needs particular attention because a restore can reintroduce records previously removed from active service.

Secure return provides a useful exit route before deletion. The Northstar Business Owner must identify the recipient, expected format and integrity checks for exported records. Procurement must coordinate service termination so the receiving team can validate the export before access closes. The supplier's description of return procedures can support the governance exit-plan control, but this document does not add another independent numbered obligation. Export availability and deletion completion are distinct events in the review timeline.

## 7. Assistance with individual requests

PRI-06 — Severity: Medium. Applies when personal data is processed.

For relationships processing personal data, the supplier must support Northstar with access, correction, deletion and export requests using the agreed authenticated request process.

The service description can show how records are located, corrected, removed or produced in an intelligible format. Assistance may use a product feature or an operational support route, provided the route addresses the actual dataset. Northstar Privacy must verify the identity and authority of the requester before forwarding instructions. A counterparty does not decide Northstar's response merely because it holds the records. The internal case record links the request, instruction and received assistance without exposing unnecessary personal information.

Request handling may reveal a mismatch between stated inventory and actual service behavior. For example, an export might omit event metadata that the service still associates with an account. Privacy must record the unresolved category and ask the Business Owner whether the service use remains appropriate. This assessment concerns completeness and meaning; the presence of a support email address alone does not demonstrate successful assistance.

## 8. Evidence, changes and exceptions

Northstar Privacy must retain dated evidence of the agreement, data-flow description, location statement, inventory and relevant deletion explanation. Redaction is acceptable when the remaining content supports the assessed claim. A file containing only a document title does not establish the content of its unavailable schedules. Supplier-authored summaries retain declaration provenance even when they describe an independent audit. Review notes identify which passages were inspected and what remains unresolved.

The Privacy Lead approves time-bound privacy exceptions with Security and Procurement consulted where their controls are affected. Northstar Third-Party Risk must record the affected requirement, reason, compensating measures, owner and expiry, and schedule reassessment before that expiry. A review cannot erase an exception by changing a requirement quote. Policy revisions create a new version, while earlier analysis retains the original sources and decision basis. This separation makes the assessment useful for accountable operations without presenting a favorable status as legal certification.
