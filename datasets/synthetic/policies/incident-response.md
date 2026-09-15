# Third-Party Security Incident and Resilience Standard

Synthetic portfolio demonstration; not legal advice or a statement of any real organization's practices. Northstar Labs and all named suppliers are fictional.

Owner: Security Incident Response Lead. Approver: Northstar Risk Committee. Version: 1.0. Effective: 2026-09-15. Review due: 2027-09-15. Policy set: Northstar Labs Third-Party Assurance Standard.

## 1. Purpose, applicability and event definitions

This document establishes a usable incident interface between Northstar and an assessed supplier. The four identified IR controls are the supplier obligations in this document. Other paragraphs explain those controls and assign Northstar work. They do not add unlisted counterparty requirements. Incident preparation is assessed for every relationship, even before any event has occurred. The duties described by each control operate when the qualifying event arises; assessing preparedness does not imply that an incident has already occurred.

A qualifying incident is a suspected or confirmed event affecting the confidentiality, integrity or availability of Northstar data, systems, credentials or service delivery. It includes credible indications of unauthorized access, misuse of an operational identity and material disruption within the assessed service boundary. A general news article about an unrelated platform is not evidence that this supplier has suffered such an event. Northstar's Incident Commander determines the internal triage route using the known service dependency and available facts.

Awareness is the point at which the supplier becomes aware of the qualifying incident, rather than the time at which its investigation reaches a final conclusion. Calendar hours include nights and weekends. An initial notice is a first communication of known facts; an update adds or corrects information as investigation proceeds. A confirmed incident supports a scoped root-cause report, while an initial suspicion can close with a documented explanation of why the suspected impact was not established.

## 2. Precedence and preparation

This document owns the initial notification clock. The privacy document governs ordinary deletion requests, and the governance document governs continuity and exit planning. An incident preservation need can affect data handling, but it does not silently replace the privacy exception process. Northstar Security and Privacy must coordinate any preservation decision and document its basis. Reviewers retain the applicable sources so a later analysis can distinguish an incident-specific restriction from a general service retention practice.

Northstar's Business Owner must identify the service dependency and available fallback before relying on an incident contact. The Incident Commander must maintain Northstar's own monitored intake route and escalation responsibilities. A supplier can send a timely notice that Northstar mishandles internally; the assessment should not confuse these separate actors. Northstar teams must test that the internal recipient can reach Security, Privacy and the Business Owner without relying on one individual's availability.

A preparation review can inspect the supplier's escalation route, sample notice structure and exercise records. These materials demonstrate planned arrangements to different degrees. A contact list supports reachability but does not show how a real event was handled. An exercise record shows what was tested, including the assumptions and simulation limits. Northstar Third-Party Risk must preserve those distinctions in the evidence record rather than treating any document with incident in its title as complete assurance.

## 3. Initial notice and the clock

IR-01 — Severity: High. Applies to qualifying incidents in every relationship.

The supplier must notify Northstar within 24 calendar hours after becoming aware of a suspected or confirmed incident affecting Northstar data, systems, credentials or service delivery.

The first notice can be incomplete. Useful known facts include the affected service, detection time, nature of the suspected impact, immediate containment steps, contact route and areas still under investigation. The absence of a confirmed cause does not delay the initial notice. Northstar Security must distinguish a supplier's stated notification commitment from evidence that a particular historical event met it. A declared number of hours can establish the promised notice window, while an event assessment needs the actual awareness and communication timestamps.

A notice timestamp and an awareness timestamp refer to different points. Discovery by a third party, automated alert creation and human triage may also differ. Northstar's Incident Commander must ask the supplier to explain the relevant chronology when assessing a real event. A correction to an earlier estimate is retained with its reason. It does not erase the earlier communication or justify changing the clock to the date of a final executive briefing.

Northstar Privacy must determine whether an event raises separate communications or notification questions for Northstar. Those internal duties are not outsourced to the supplier by this standard. The supplier notice provides information for that decision; it is not a substitute for it. Procurement must preserve any contractual incident schedule that sets a stricter commitment, while Security records how that commitment relates to the operational baseline used in the current assessment.

## 4. Evidence and investigation timeline

IR-02 — Severity: High. Applies to qualifying incidents in every relationship.

The supplier must preserve relevant incident evidence and maintain a timestamped timeline of observations, containment actions and recovery decisions affecting Northstar.

Relevant evidence can include audit records, operational events, configuration snapshots and investigation notes. Preservation does not mean distributing unrestricted copies to every participant. A review can establish what was preserved, who controlled it and how its integrity was maintained. Northstar Security must use an appropriate channel for sensitive material and request only what is needed to understand the impact. Production secrets and unrelated customer content are not appropriate attachments to a general assurance ticket.

A useful timeline distinguishes observation from inference. An operator may observe a failed login, infer a possible misuse route and later reject that hypothesis. Each item has a time reference and an identified source or decision owner. Northstar's Incident Commander must retain unresolved uncertainty in the case record. A neat narrative written after closure can omit important decision points; the evidence assessment considers whether the record supports the stated sequence and service impact.

Preservation also interacts with routine deletion and log rotation. Northstar Security and Privacy must document why relevant material is isolated and when the preservation decision is reviewed. The exception identifies affected data categories and access boundaries. It is not permission to keep all records indefinitely for unspecified investigations. The privacy standard's ordinary deletion rule continues to describe the normal service commitment outside the documented incident-specific boundary.

## 5. Containment, recovery and communication

IR-03 — Severity: Medium. Applies to qualifying incidents in every relationship.

The supplier must provide containment and recovery updates to Northstar through incident closure, including material changes to assessed impact and unresolved recovery risks.

Updates explain what changed since the previous communication and what remains unknown. A fixed update cadence can be agreed during triage according to event severity and operational need. This standard deliberately does not create an additional universal interval in hours. Northstar's Incident Commander must record the agreed cadence and the route for urgent changes. Silence is not evidence that recovery has completed, and a status page may omit information specific to Northstar's service scope.

Containment can interrupt service while limiting harm. Northstar's Business Owner must participate in decisions affecting its own operations and fallback arrangements. A supplier's technical action and Northstar's business decision remain separate records even when they happen in the same meeting. Reviewers look for a coherent explanation of the chosen action, expected effect, observed result and remaining exposure. Containment quality depends on the event context and the observed results, which Security evaluates with the Incident Commander.

Recovery readiness depends on the affected boundary. A restored user interface may coexist with delayed background processing or unavailable administrative tooling. Northstar Security must ask what was tested before the service was described as recovered. The Business Owner must validate the operational outcome relevant to Northstar. A declaration that all systems are healthy is useful only when its scope and observation period are clear. Independent technical evidence can strengthen that understanding without removing the need for a human decision.

## 6. Root cause and corrective action

IR-04 — Severity: Medium. Applies to confirmed incidents in every relationship.

For confirmed incidents, the supplier must deliver a scoped root-cause and corrective-action report identifying contributing factors, accountable remediation owners and verification of closure.

A scoped report explains the affected service and evidence limitations. Root cause may involve several contributing conditions rather than a single person or failed component. Corrective actions address those conditions and identify how completion is checked. Northstar Security must distinguish an action being assigned, an action being implemented and an action being verified. A future target date is not a completed control, and a generic training promise may not address the technical route that caused the incident.

The report can preserve uncertainty where a definitive cause is unavailable. In that case the review asks whether the remaining uncertainty changes the service decision or calls for additional controls. Northstar Third-Party Risk must link significant corrective actions to the supplier's open assurance record. A closed incident ticket does not automatically close a separate risk exception. Conversely, an incident outside the assessed boundary should not be represented as proof that a Northstar-specific requirement failed.

## 7. Exercises and internal lessons

Northstar's Incident Commander must conduct an internal lessons review after material events and maintain the readiness of the intake and escalation process. High-criticality service exercises are considered with the continuity and exit obligation in the governance document. The supplier exercise narrative is evidence for that existing obligation rather than a fifth incident control. A walkthrough can demonstrate role coordination, while a recovery test can demonstrate a technical outcome; the review records which kind occurred.

Useful scenarios expose a boundary, such as the primary contact being unavailable, an uncertain personal-data impact or a restore that reintroduces deleted records. Northstar teams must identify their own improvement actions and owners. An exercise is not a prediction that an actual event will unfold identically. The assessment uses it as evidence of preparation and as a way to find unresolved dependencies before a time-critical decision is needed.

## 8. Exceptions and records

The Security Incident Response Lead approves documented, time-bound exceptions to incident preparation or evidence arrangements after consulting Privacy and the Business Owner. Northstar Third-Party Risk must record compensating controls, responsible owners and reassessment before expiry. An exception never delays the initial notice while facts remain incomplete. Any proposed contractual change to the notification commitment is escalated for a new policy and relationship decision rather than hidden as an informal operational practice.

Northstar must retain the source version, evidence provenance, chronology and human decisions needed to reconstruct the review. New evidence can justify a new analysis without rewriting the earlier report. The review record keeps residual risk, evidence gaps and reviewer disposition separate. A satisfactory declared notice window does not close unresolved questions about investigation or recovery capability. Security retains those questions until an accountable owner resolves them.
