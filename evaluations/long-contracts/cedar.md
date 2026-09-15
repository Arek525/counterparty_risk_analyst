# Cedar Bridge payroll processing agreement

Synthetic portfolio contract between Northstar Labs, the customer, and Cedar Bridge Operations, the supplier. Neither party represents a real organization. Effective date: 1 October 2026. This text is designed to test retrieval of agreed service boundaries and qualifications; it is not legal advice or an executable commercial instrument.

## 1. Contract documents and interpretation

The agreement covers payroll preparation for Northstar's European workforce. It includes the signed service schedule below, four incorporated Northstar supplier standards and the executed change schedule at the end of this file. The final change schedule prevails over inconsistent deadlines in the supplier standards for the specifically named activity. Silence in that schedule does not waive unrelated requirements. An internal sales presentation or an unsigned implementation estimate cannot change an obligation in the executed documents.

Production payroll means the tenant that receives employee identifiers, bank routing details, salary components and approved adjustments. It excludes the supplier's training tenant, demonstration dataset and corporate billing records. A person reading the agreement should establish which population a statement concerns before comparing numerical commitments. Several operating tasks occur after termination, and a delivery deadline must not be confused with a deletion deadline. The chronology in the final change schedule is part of the agreed service definition.

The customer appoints its Payroll Operations Lead as the instruction owner. The supplier appoints a named service manager and deputy in the private contact register. Those names are deliberately absent from this synthetic document. An instruction is authenticated through the service desk and linked to the customer's tenant; an email from an unknown address is not an instruction to disclose or remove employee records. The supplier records conflicting instructions and seeks clarification rather than choosing the instruction with the earliest timestamp.

## 2. Administrative identities

Cedar requires a second authentication factor for every human administrator entering the production payroll console. This includes supplier support personnel using a temporary elevated role. Access requests identify the maintenance task, tenant and approving service owner. Session records distinguish approval from the moment the entitlement becomes active. Employment termination triggers revocation independently of the periodic review calendar.

Non-interactive payroll connectors are excluded from the human MFA rule and instead use scoped credentials rotated at least every 45 days. The inventory explicitly classifies an identity as a human account or a connector; an operator cannot avoid the second factor by relabelling their ordinary login. Connector permissions are restricted to the integration endpoints stated in the interface register. The rotation record includes the replacement date and confirmation that the retired credential no longer succeeds. The customer manages its own ordinary payroll-user assignments.

## 3. Storage and removal

The ordinary contract rule requires removal of production payroll records within 30 days after service termination. Removal includes working replicas and job outputs that remain available to the application. The supplier confirms the tenant and removal trigger before initiating the workflow. Northstar can request a completion receipt listing the stores processed, the completion date and any outstanding preservation exception. An outstanding exception is reported rather than silently treating partial removal as complete.

Encryption covers production payroll databases, their replicas, event logs and disaster-recovery copies. The customer does not receive raw encryption keys through an assurance request. Instead the supplier provides a configuration description and a sample of access-control evidence. The inventory distinguishes the key-administration role from the role that reads ordinary payroll output. Change approval is recorded before a component moves to a different storage class.

Diagnostic CSV exports containing employee records are included in the encryption obligation even when their intended lifetime is less than one working day. An export created for a support task has a task owner and a removal instruction. A file copied to a personal workstation is outside the approved diagnostic route. The supplier may demonstrate the route using synthetic data, but that demonstration is not independent evidence of every past support task.

## 4. Incident escalation

Cedar sends the first payroll incident notice within 18 hours after a credible service-impact signal reaches the designated response channel. Initial facts may be incomplete. The notice names the assessed service, describes known impact and provides the next update route. It must not imply that the absence of a completed investigation proves there was no impact. The supplier records later corrections without erasing the initial observations.

Waiting for root-cause confirmation does not postpone the start of the 18-hour notification period. The response lead distinguishes a potential impact signal from a routine application warning with no service consequence. Escalation decisions remain available for review. A customer request for an additional update does not reset the initial deadline. The parties can coordinate communications through their named contacts without treating that coordination as permission to suppress a notice.

## 5. Location and support boundary

Primary payroll storage and routine calculation take place in Germany and Ireland. The architecture register names the production database, processing queue and approved recovery location. Office addresses are not substituted for component locations. Relocation of a production component follows the change procedure and is not implied by adding a new supplier employee.

The original support schedule limits human access to personnel working in the European Economic Area. A later change can authorize another support route only when the customer approves its scope and safeguards. The contractual location of the supplier's parent entity is not itself evidence of where records are viewed. Northstar's privacy reviewer assesses the actual access path, record categories and duration together.

## 6. Changes to delivery partners

Cedar gives 20 calendar days of advance notice before adding a delivery partner with access to payroll records. The notice names the activity, location, data categories and proposed start date. A marketing reseller with no access to the service is not treated as a payroll delivery partner merely because it signs a referral agreement. Objections identify a concrete concern for the assessed activity and enter the contract-change register.

An emergency replacement following insolvency may start immediately, but Cedar must notify Northstar within two working days and supply the same access details. This exception does not remove the need to record the replacement, verify its controls or address the customer's objection. The supplier remains accountable for the authorized work and cannot treat the partner's own template as a unilateral amendment to this agreement.

## 7. Service levels and planned exercises

The recovery target for the production payroll tenant is six hours from declaration of a service disaster. The declaration is a recorded operational event, not the time at which an individual employee first reports a login problem. The recovery plan identifies processing dependencies, customer validation steps and the role authorized to declare ordinary operation restored. A successful infrastructure restart alone does not demonstrate that a payroll run has reconciled correctly.

The six-hour target does not apply to the quarterly payroll simulation environment, whose restoration is scheduled on a best-effort basis. That environment contains synthetic records and is separated from production processing. An exercise report must state which environment was tested, the start trigger and the validation performed. Northstar should not compare the duration of a training exercise with the production recovery target without checking those boundaries.

## 8. Assurance and inspection

Cedar's available independent assurance report covers the established payroll processing platform for January through December 2025. A register entry identifies the report and its scope; the underlying report is supplied through an authorized review route. The supplier must disclose known exclusions rather than present a company certificate as proof that every acquired component is assessed. Northstar can request supporting declarations while deciding whether independent coverage is adequate.

The independent report excludes the connector acquired in February 2026; its extension assessment is scheduled and has not yet been completed. Operational monitoring and internal testing of that connector are useful evidence but do not alter the report's stated period. The customer records its decision about compensating measures separately from the supplier's target date for finishing the extension. A planned assessment is not a completed assessment.

## 9. Billing, acceptance and exit coordination

The monthly charge separates production processing capacity, approved implementation work and optional training sessions. The customer may challenge an item by identifying the relevant order and disputed amount; the service manager records the response. An invoice dispute does not itself authorize disclosure of employee records to the billing team. Purchase-order identifiers are retained in corporate records under their own schedule and do not replace the service's removal obligations.

Acceptance of the initial interface confirms that the agreed synthetic test records pass the reconciliation procedure. It is not acceptance of every future file and does not release the supplier from reporting a later control failure. Material interface changes require an updated test plan with the customer. A change in an external banking endpoint can require a joint transition plan without amending the definition of production payroll data.

On termination Cedar makes a tenant-specific payroll export available for customer validation. The export includes the documented field map and record counts. Northstar confirms whether the package can be used in its receiving system; availability of a download link is only one step in that process. The change schedule below fixes the delivery window and describes what may remain after validation. Termination of processing and closure of a billing account are separate events.

<!-- ANNEXES -->

## Executed change schedule CB-7

This schedule is signed with the main agreement and applies only to production payroll. It prevails over inconsistent general deadlines for the named obligations. All other Northstar supplier standards continue to apply. The parties deliberately retain the original provisions above so that the reader can identify the baseline and the exact amendment rather than treating both numbers as unresolved contradictions.

CB-7 replaces the ordinary 30-day removal deadline with a 14-day deadline for production payroll records. The trigger remains service termination. Technically isolated recovery copies follow a 60-day expiry cycle and cannot be used for ordinary payroll processing during that period. If a restoration reintroduces records previously removed, the removal instructions are reapplied before normal access resumes. A documented preservation hold is separately identified by record category and custodian; it is not an indefinite exception for the whole tenant.

CB-7 permits a named Canadian specialist to access masked payroll troubleshooting records for an approved incident task, overriding the earlier EEA-only support restriction for that task alone. The specialist cannot export full salary files. Access requires a task owner, approval and session record. This authorization does not move primary storage or routine calculation outside Germany and Ireland. Additional overseas access requires a new approved change.

Cedar must deliver the exit export within seven calendar days after Northstar's authenticated request. The seven-day delivery window does not extend the amended 14-day removal deadline. If validation cannot finish within that interval, the parties must record a scoped instruction and preservation basis rather than silently continuing ordinary processing. The final receipt distinguishes successful delivery, customer validation and deletion completion.
