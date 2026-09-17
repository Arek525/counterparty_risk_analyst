# Evaluation

The current experiment measures policy extraction, evidence retrieval, status agreement,
quotation support and tokens separately. It uses real Gemini calls and production components,
with no extra evaluation platform. Reference labels and review judgments are agent-authored;
**independent human review remains pending**.

## Files and cases

- [protocol.json](protocol.json): definitions, split rules, budget, limitations and review status.
- [run.py](run.py): explicit, resumable runner using production parsing, E5, pgvector,
  hybrid ranking, prompts and quotation validation in a disposable database.
- [results.json](results.json): one artifact with the freeze record, summaries, every provider
  attempt, structured outputs, token metadata, selected chunk IDs and agent review notes.
- `cases/`: one file per policy family; each contains the policy, two counterparties,
  proposed reference requirements/statuses, rationales and required evidence passages.
  Reference annotations never enter the model request.

| Split / file in `cases/` | Cases | Tests |
|---|---|---|
| `development/data-lifecycle.json` | dev-01–02 | Maximum deadlines, narrow statutory holds, incomplete confirmation evidence |
| `development/incident-response.json` | dev-03–04 | Wrong starting event, missing intervals, conflicting binding schedules |
| `development/access-control.json` | dev-05–06 | Absent applicability, recovery-account exception, complete access controls |
| `development/data-location.json` | dev-07–08 | Polish/English retrieval, remote access versus storage, explicit annex precedence |
| `development/independent-assurance.json` | dev-09–10 | Missing independent report, supplied report, corrective-action completeness |
| `development/managed-operations.json` | dev-11–12 | Late exception, 56,561-character packet, hostile instructions, missing approver |
| `held-out/service-continuity.json` | test-01–02 | Recovery bounds, dated exercises, stale evidence and unresolved remediation |
| `held-out/subcontractor-changes.json` | test-03–04 | Narrow emergency exception, missing annexes and Polish prompt injection |
| `held-out/external-transfers.json` | test-05–06 | Long transport evidence, TLS contradiction, unknown retention |

There are 12 development cases across six policy families and six reserved cases across
three different families. Each policy has three reference obligations. Families, not individual
requirements, define the split. All documents are synthetic UTF-8 text; long documents contain
constructed administrative background, some shared across splits. Policies themselves are short.

## Recorded result and interpretation

Measured on 2026-09-17 with `gemini-3.5-flash-lite`, temperature 0, prompt
`semantic-assessment-v6`, pinned local multilingual E5 and top-8 hybrid retrieval.
Code/corpus were frozen at `5731778` before the first reserved-case call. Exact hashes and
provider model versions are recorded in `results.json`. No final-test result informed a change.

The final run made 36 provider requests: three extractions, 18 hybrid assessments and
15 full-context assessments. Full context was ineligible for all three requirements of test-01
because the serialized input exceeded the **application's** 25,000-character limit.
No source was truncated. Raw source length alone does not determine eligibility: instructions,
requirements, relationship fields and citation metadata also consume the input budget.

| Result | Hybrid | Full context |
|---|---:|---:|
| Attempted assessments | 18 | 18 |
| Completed / ineligible / technical errors | 18 / 0 / 0 | 15 / 3 / 0 |
| Status agreement on completed assessments | 18/18 | 15/15 |
| Status agreement on paired assessments | 15/15 | 15/15 |
| Paired input tokens | 32,387 | 39,031 |
| Paired output tokens | 4,651 | 4,604 |
| Paired combined tokens | 37,038 | 43,635 |
| Paired HTTP median / nearest-rank p95, n=15 | 1.78 / 2.15 s | 1.74 / 1.94 s |
| Sufficient quotations on all completed assessments, agent review | 18/18 | 14/15 |

Paired token reduction is `1 - 37038 / 43635 = 15.1%`. Adding the shared 4,915 extraction
tokens once to each arm gives `1 - 41953 / 48550 = 13.6%`. Embeddings use local compute,
not Gemini tokens. No dollar-cost saving is inferred from token counts.

The 12 short-document pairs had identical input counts; combined tokens were 21,992 versus
21,873, so hybrid used 0.5% more. The three pairs from the single eligible long document used
15,046 versus 21,762 combined tokens, a 30.9% reduction. This is a small, controlled result,
not a general savings estimate for arbitrary contracts.

Local model initialization from cached artifacts took 1.84 s. Passage indexing took
0.04–1.47 s per packet; query encoding and pgvector scoring took 0.04–0.07 s per case.
Five-second request-start spacing handled the observed 15-request/minute quota. Provider
HTTP timings exclude that pacing; step wall times include it. No API/queue latency or
production throughput claim is made. The full-context arm does not need the hybrid index.

Extraction recovered 9/9 reference obligations, with 9/9 supported proposed obligations,
according to agent review of descriptions, scopes, bounds and exceptions. Hybrid recovered
21/21 required evidence groups, including all groups for each of 18 requirements.
Both arms had zero false passes among nine fail/unknown/conflict reference items.
All completed findings passed production quotation validation.

The agent marked one full-context conflict citation insufficiently self-contained: the
TLS quotations omitted the explicit same-period/no-precedence sentence used in the explanation.
The source contains it and the status is correct. Review notes are per assessment; this is a
conservative agent judgment that still needs human review, not a second-model or human score.
No separate judge model was called; these qualitative checks were made by the implementation agent.

<!-- BEGIN RECORDED FINAL CASES -->
## Final cases: inspect the actual results

Expand a case to compare its reference answers with the saved Gemini responses from
`runs.reserved_final_v6` in [results.json](results.json). These are the final cases only,
not development runs. Explanations and quotations retain their recorded wording and language.
Reference rationales and citation-review notes are agent-authored; independent human review is pending.

Token counts below are per assessment and exclude shared policy extraction. HTTP time excludes
rate-limit pacing and local indexing. **Ineligible** means the application rejected the input
before calling Gemini, not that the model returned a failure.

<details>
<summary>test-01 — A recent successful production recovery exercise</summary>

**Source data:** [service-continuity.json](cases/held-out/service-continuity.json). Evidence: 15,242 characters; language(s): en.

**Relationship:** High-criticality scheduling service Assessment reference date: 2026-09-17.

### P07-R1 — Recovery commitments

For a high-criticality service, the supplier must contractually commit to recovery within 7 hours of declaring a service disruption and to losing no more than 3 hours of committed customer transactions.

**Expected: Pass.** Both binding maxima meet policy and the recovery trigger matches.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Pass | 4,851 | 304 | 1.59 s |
| Full context | Ineligible | 0 | 0 | No call |

**Hybrid — Gemini explanation**

The requirement mandates that for a high-criticality service, the supplier contractually commits to recovery within 7 hours of declaring a service disruption and to losing no more than 3 hours of committed customer transactions. The relationship context confirms the service is a high-criticality scheduling service. Evidence from the service assurance packet explicitly states that the signed service schedule commits to restoration within 5 hours (meeting the maximum bound of within 7 hours) and loss of no more than 2 hours of committed customer transactions (meeting the maximum bound of no more than 3 hours). Therefore, the supplier fully meets the recovery commitments.

**evidence-13-1.md**

> The signed service schedule commits to restoration within 5 hours after declaration of a service disruption and loss of no more than 2 hours of committed customer transactions.

**Full context:** Assessment context exceeds 25000 characters; source text was not truncated. No model response or citation was generated.

*Recorded steps: `test-01/hybrid/P07-R1` and `test-01/full_document/P07-R1`.*

### P07-R2 — Annual restoration exercise

For a high-criticality service, the supplier must perform a restoration exercise at least once every 12 months and provide a dated result covering the contracted production configuration.

**Expected: Pass.** Supplied dates demonstrate the required interval and production scope.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Pass | 4,842 | 369 | 1.74 s |
| Full context | Ineligible | 0 | 0 | No call |

**Hybrid — Gemini explanation**

The requirement applies to high-criticality services, which matches the relationship business_criticality 'high' and applicability text. The evidence from document 4a2ec505-dab4-519f-91dd-028b5ff0d21f states that 'Restoration exercise record RS-26 is dated 8 August 2026 and covers the contracted production configuration. The previous exercise was 20 August 2025; the next exercise is scheduled within 12 months.' This shows that a restoration exercise was performed within the 12-month maximum interval (from August 20, 2025 to August 8, 2026) and provided a dated result covering the contracted production configuration, fully satisfying the requirement.

**evidence-13-1.md**

> Restoration exercise record RS-26 is dated 8 August 2026 and covers the contracted production configuration. The previous exercise was 20 August 2025; the next exercise is scheduled within 12 months.

**Full context:** Assessment context exceeds 25000 characters; source text was not truncated. No model response or citation was generated.

*Recorded steps: `test-01/hybrid/P07-R2` and `test-01/full_document/P07-R2`.*

### P07-R3 — Exercise remediation

Each unresolved material failure in the supplied restoration exercise must have a documented corrective action and target date. A successful exercise with no material failures does not require a remediation plan.

**Expected: Not applicable.** The supplied result explicitly has no material failures.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Not applicable | 4,841 | 275 | 1.81 s |
| Full context | Ineligible | 0 | 0 | No call |

**Hybrid — Gemini explanation**

The requirement mandates remediation plans only when the supplied restoration exercise contains unresolved material failures. The provided evidence explicitly states that the restoration exercise record RS-26 shows successful recovery of every tested production dependency and no material failures. Therefore, the trigger condition for this requirement is absent, making it not applicable.

**evidence-13-1.md**

> Restoration exercise record RS-26 is dated 8 August 2026 and covers the contracted production configuration. The previous exercise was 20 August 2025; the next exercise is scheduled within 12 months. The result records successful recovery of every tested production dependency and no material failures.

**Full context:** Assessment context exceeds 25000 characters; source text was not truncated. No model response or citation was generated.

*Recorded steps: `test-01/hybrid/P07-R3` and `test-01/full_document/P07-R3`.*

</details>

<details>
<summary>test-02 — Marketing targets do not replace binding commitments</summary>

**Source data:** [service-continuity.json](cases/held-out/service-continuity.json). Evidence: 685 characters; language(s): en.

**Relationship:** High-criticality scheduling service Assessment reference date: 2026-09-17.

### P07-R1 — Recovery commitments

For a high-criticality service, the supplier must contractually commit to recovery within 7 hours of declaring a service disruption and to losing no more than 3 hours of committed customer transactions.

**Expected: Fail.** The binding schedule has no recovery guarantee and permits transaction loss above the3h ceiling.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Fail | 1,464 | 254 | 1.72 s |
| Full context | Fail | 1,464 | 242 | 1.76 s |

**Hybrid — Gemini explanation**

The relationship indicates a high-criticality service, making the requirement applicable. The requirement mandates a contractual commitment to recovery within 7 hours of declaring a service disruption and losing no more than 3 hours of committed customer transactions. However, the evidence explicitly states that the signed service schedule disclaims a binding recovery deadline and permits a loss of up to 6 hours of committed customer transactions, which violates both bounds.

**Full context — Gemini explanation**

The relationship indicates a high-criticality service, making the requirement applicable. The supplier fails to meet the recovery commitments because the signed service schedule explicitly disclaims a binding recovery deadline and permits a data loss of up to 6 hours of committed customer transactions, which violates the maximum bound of 7 hours for recovery and 3 hours for transaction loss.

**Quoted evidence — identical in both methods**

**evidence-14-1.md**

> the signed service schedule disclaims a binding recovery deadline and permits loss of up to 6 hours of committed customer transactions.

*Recorded steps: `test-02/hybrid/P07-R1` and `test-02/full_document/P07-R1`.*

### P07-R2 — Annual restoration exercise

For a high-criticality service, the supplier must perform a restoration exercise at least once every 12 months and provide a dated result covering the contracted production configuration.

**Expected: Fail.** A confirmed last exercise in2024 exceeds12months as of2026-09-17.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Fail | 1,455 | 330 | 1.70 s |
| Full context | Fail | 1,455 | 275 | 1.52 s |

**Hybrid — Gemini explanation**

The requirement mandates that for a high-criticality service, the supplier must perform a restoration exercise at least once every 12 months and provide a dated result covering the contracted production configuration. The assessment reference date is 17 September 2026. The evidence shows that the only supplied restoration record is dated 1 February 2024, and the supplier confirms that no later exercise has been performed. The interval between 1 February 2024 and 17 September 2026 is over 31 months, exceeding the maximum allowable interval of 12 months (at least once every 12 months). Therefore, the supplier failed to perform the restoration exercise within the required frequency.

**Full context — Gemini explanation**

The requirement mandates that for a high-criticality service, the supplier must perform a restoration exercise at least once every 12 months. The assessment reference date is 17 September 2026. The evidence shows that the last restoration exercise was performed on 1 February 2024 and confirms that no later exercise has been performed. This is a span of over 31 months, failing the maximum interval of 12 months.

**Quoted evidence — identical in both methods**

**evidence-14-1.md**

> The supplied restoration record is dated 1 February 2024; its scope is the contracted production configuration. The supplier confirms that no later exercise has been performed.

*Recorded steps: `test-02/hybrid/P07-R2` and `test-02/full_document/P07-R2`.*

### P07-R3 — Exercise remediation

Each unresolved material failure in the supplied restoration exercise must have a documented corrective action and target date. A successful exercise with no material failures does not require a remediation plan.

**Expected: Fail.** The unresolved material failure has an action but explicitly lacks a target date.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Fail | 1,455 | 258 | 1.48 s |
| Full context | Fail | 1,455 | 249 | 1.25 s |

**Hybrid — Gemini explanation**

The requirement states that each unresolved material failure in the supplied restoration exercise must have a documented corrective action and target date. The evidence establishes that the supplied restoration exercise contains unresolved material failure F-9, and while a corrective action is logged ('redesign the restore dependency order'), the completion-date field is explicitly left unassigned. This missing target date constitutes a grounded violation of the remediation plan obligation.

**Full context — Gemini explanation**

The requirement states that each unresolved material failure in the supplied restoration exercise must have a documented corrective action and target date. The evidence confirms that the restoration exercise contains an unresolved material failure F-9 with a documented corrective action to redesign the restore dependency order, but the completion-date field is left unassigned, which violates the requirement for a target date.

**Quoted evidence — identical in both methods**

**evidence-14-1.md**

> That exercise contains unresolved material failure F-9. The action log says to redesign the restore dependency order, but leaves the completion-date field unassigned.

*Recorded steps: `test-02/hybrid/P07-R3` and `test-02/full_document/P07-R3`.*

</details>

<details>
<summary>test-03 — An emergency exception does not waive a separate obligation</summary>

**Source data:** [subcontractor-changes.json](cases/held-out/subcontractor-changes.json). Evidence: 794 characters; language(s): en.

**Relationship:** Hosted business service Assessment reference date: 2026-09-17.

### P08-R1 — Nowy podwykonawca

Dostawca musi uzyskać pisemną zgodę Vela przed udostępnieniem jej danych osobowych każdemu nowemu podwykonawcy. Wcześniejsze poinformowanie Vela nie zastępuje zgody.

**Expected: Fail.** Emergency change permission expressly does not waive prior written subcontractor approval.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Fail | 1,498 | 243 | 1.72 s |
| Full context | Fail | 1,498 | 313 | 1.94 s |

**Hybrid — Gemini explanation**

The supplier violated the requirement to obtain prior written consent from Vela before sharing personal data with a new subcontractor. The evidence states that during an emergency repair, a new data-processing subcontractor was added and personal data was shared immediately without prior written approval from Vela, and that the supplier merely relies on an emergency-service-change exception which is not authorized by the requirement.

**Full context — Gemini explanation**

Dostawca naruszył wymóg uzyskania pisemnej zgody Vela przed udostępnieniem danych osobowych każdemu nowemu podwykonawcy. Dowody wskazują, że nowy podwykonawca został dodany i dane osobowe zostały udostępnione natychmiast bez uzyskania uprzedniej pisemnej zgody Vela. Powoływanie się przez dostawcę na wyjątek dotyczący awarii (emergency-service-change exception) nie jest dozwolone przez wymaganie, ponieważ jedynym dopuszczalnym sposobem jest uzyskanie pisemnej zgody Vela, a wcześniejsze poinformowanie lub brak zgody nie spełnia tego warunku.

**Quoted evidence — identical in both methods**

**evidence-15-1.md**

> The repair added a new data-processing subcontractor and personal data was shared immediately; Vela had not given written subcontractor approval.

*Recorded steps: `test-03/hybrid/P08-R1` and `test-03/full_document/P08-R1`.*

### P08-R2 — Rejestr podwykonawców

Dla każdego podwykonawcy przetwarzającego dane osobowe Vela dostawca musi prowadzić aktualny rejestr obejmujący nazwę podmiotu, kraj przetwarzania i powierzoną funkcję.

**Expected: Pass.** The current complete register supplies entity, country and function for both processors.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Pass | 1,492 | 286 | 1.84 s |
| Full context | Pass | 1,492 | 280 | 1.59 s |

**Hybrid — Gemini explanation**

The requirement mandates that the supplier maintain an up-to-date register of each subcontractor processing Vela's personal data, including the entity name, country of processing, and entrusted function. Evidence shows that subcontractors process customer personal data. The supplier's current subcontractor register lists North Quay Processing, Poland, transaction queue hosting, and Delta Storage, Sweden, encrypted archive storage, which satisfies all elements of the required register (entity name, country of processing, and entrusted function).

**Full context — Gemini explanation**

The requirement mandates that the supplier must maintain an up-to-date register of each subcontractor processing Vela's personal data, including the entity name, processing country, and assigned function. The evidence confirms that subcontractors process Vela personal data and that a current subcontractor register is maintained, explicitly listing 'North Quay Processing, Poland, transaction queue hosting' and 'Delta Storage, Sweden, encrypted archive storage', thereby fulfilling all required details for the subcontractor register.

**Quoted evidence — identical in both methods**

**evidence-15-1.md**

> The current subcontractor register lists North Quay Processing, Poland, transaction queue hosting, as the new processor. It also lists the existing processor Delta Storage, Sweden, encrypted archive storage; these are the only processors of Vela personal data.

*Recorded steps: `test-03/hybrid/P08-R2` and `test-03/full_document/P08-R2`.*

### P08-R3 — Zmiana awaryjna

Awaryjna zmiana usługi może zostać wykonana bez uprzedniej zgody na samą zmianę tylko w celu usunięcia aktywnej awarii; dostawca musi wtedy poinformować Vela w ciągu 4 godzin od rozpoczęcia zmiany. Ten wyjątek nie zwalnia z uzyskania zgody na nowego podwykonawcę.

**Expected: Fail.** The active outage and 2.5-hour notice meet the timing conditions, but the supplier explicitly applies the exception to waive new-subcontractor consent, contrary to the material restriction in this same obligation. Evaluate the full clause, not only its notice deadline.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Fail | 1,550 | 469 | 1.92 s |
| Full context | Fail | 1,550 | 428 | 1.92 s |

**Hybrid — Gemini explanation**

The requirement states that an emergency service change may be performed without prior approval only to remove an active outage, with notification to Vela within 4 hours, but explicitly clarifies that this exception does not exempt the supplier from obtaining approval for a new subcontractor. The evidence confirms that during an emergency repair starting at 02:00 (with notification sent at 04:30, satisfying the 4-hour window), the supplier added a new data-processing subcontractor (North Quay Processing) and shared personal data without prior written subcontractor approval, relying improperly on the emergency-service-change exception to bypass subcontractor approval.

**evidence-15-1.md**

> During an active service outage, we began an emergency repair at 02:00 and notified Vela at 04:30 the same day. The repair added a new data-processing subcontractor and personal data was shared immediately; Vela had not given written subcontractor approval.

**evidence-15-1.md**

> The supplier relies on the emergency-service-change exception as its reason for omitting prior approval of North Quay Processing.

**Full context — Gemini explanation**

The requirement states that an emergency service change may be performed without prior approval only to remove an active outage, and the supplier must notify Vela within 4 hours of starting the change. However, this exception explicitly does not exempt the supplier from obtaining approval for a new subcontractor. The evidence shows that the emergency repair added a new data-processing subcontractor (North Quay Processing) without prior written approval from Vela, and the supplier explicitly relied on the emergency-service-change exception as its reason for omitting this prior approval, violating the explicit condition that the exception does not waive subcontractor approval.

**evidence-15-1.md**

> The repair added a new data-processing subcontractor and personal data was shared immediately; Vela had not given written subcontractor approval.

**evidence-15-1.md**

> The supplier relies on the emergency-service-change exception as its reason for omitting prior approval of North Quay Processing.

*Recorded steps: `test-03/hybrid/P08-R3` and `test-03/full_document/P08-R3`.*

</details>

<details>
<summary>test-04 — Missing annexes cannot be filled in by an instruction</summary>

**Source data:** [subcontractor-changes.json](cases/held-out/subcontractor-changes.json). Evidence: 668 characters; language(s): pl.

**Relationship:** Hosted business service Assessment reference date: 2026-09-17.

### P08-R1 — Nowy podwykonawca

Dostawca musi uzyskać pisemną zgodę Vela przed udostępnieniem jej danych osobowych każdemu nowemu podwykonawcy. Wcześniejsze poinformowanie Vela nie zastępuje zgody.

**Expected: Unknown.** The absent approval and missing sharing timeline cannot establish either compliance or an explicit violation.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Unknown | 1,526 | 364 | 2.05 s |
| Full context | Unknown | 1,526 | 348 | 1.74 s |

**Hybrid — Gemini explanation**

The requirement mandates that the supplier must obtain written consent from Vela before sharing personal data with any new subcontractor, noting that prior notification does not replace consent. The selected evidence mentions that the attachment registry lists Vela's consent for a new subcontractor and the current list of subcontractors, but neither of those two attachments was provided, and the packet does not show whether or when the new subcontractor received the data. Because the necessary documents confirming whether consent was obtained prior to data sharing are missing, the status is unknown.

**Requested information:**

- Kopia pisemnej zgody Vela na nowego podwykonawcę
- Dokumentacja potwierdzająca czy i kiedy nowy podwykonawca otrzymał dane osobowe

**Full context — Gemini explanation**

The requirement states that the supplier must obtain written consent from Vela before sharing personal data with any new subcontractor, and prior notification does not replace consent. The evidence mentions that the attachment registry lists Vela's consent for a new subcontractor and the current list of subcontractors, but neither attachment was provided. Furthermore, the evidence states that it cannot be determined from the package whether and when the new subcontractor received the data. Therefore, the status is unknown due to missing documents and targeted missing information.

**Requested information:**

- Copy of Vela's written consent for the new subcontractor
- Evidence confirming whether and when the new subcontractor received personal data

**Quoted evidence — identical in both methods**

**evidence-16-1.md**

> Rejestr załączników wymienia zgodę Vela na nowego podwykonawcę oraz aktualny wykaz podwykonawców, ale żaden z tych dwóch załączników nie został przekazany. Z pakietu nie wynika, czy i kiedy nowy podwykonawca otrzymał dane.

*Recorded steps: `test-04/hybrid/P08-R1` and `test-04/full_document/P08-R1`.*

### P08-R2 — Rejestr podwykonawców

Dla każdego podwykonawcy przetwarzającego dane osobowe Vela dostawca musi prowadzić aktualny rejestr obejmujący nazwę podmiotu, kraj przetwarzania i powierzoną funkcję.

**Expected: Unknown.** A reference to an unprovided register does not establish its coverage or contents.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Unknown | 1,520 | 303 | 1.47 s |
| Full context | Unknown | 1,520 | 323 | 1.64 s |

**Hybrid — Gemini explanation**

The evidence acknowledges the existence of a subcontractor list ('aktualny wykaz podwykonawców'), but explicitly states that the attachment itself was not provided ('żaden z tych dwóch załączników nie został przekazany'). Therefore, it cannot be verified whether the register includes all required details such as the entity name, processing country, and assigned function. Missing documents or silence are treated as unknown.

**Requested information:**

- The actual subcontractor register/attachment containing entity names, processing countries, and assigned functions.

**Full context — Gemini explanation**

The evidence states that the register of subcontractors exists ('Rejestr załączników wymienia zgodę Vela na nowego podwykonawcę oraz aktualny wykaz podwykonawców'), but the actual register attachments were not provided ('ale żaden z tych dwóch załączników nie został przekazany'). Consequently, it cannot be verified whether the register includes all required details such as the entity name, processing country, and assigned function. Therefore, the status is unknown and targeted missing information is required.

**Requested information:**

- The complete subcontractor register containing entity names, processing countries, and assigned functions.

**Quoted evidence — identical in both methods**

**evidence-16-1.md**

> Rejestr załączników wymienia zgodę Vela na nowego podwykonawcę oraz aktualny wykaz podwykonawców, ale żaden z tych dwóch załączników nie został przekazany.

*Recorded steps: `test-04/hybrid/P08-R2` and `test-04/full_document/P08-R2`.*

### P08-R3 — Zmiana awaryjna

Awaryjna zmiana usługi może zostać wykonana bez uprzedniej zgody na samą zmianę tylko w celu usunięcia aktywnej awarii; dostawca musi wtedy poinformować Vela w ciągu 4 godzin od rozpoczęcia zmiany. Ten wyjątek nie zwalnia z uzyskania zgody na nowego podwykonawcę.

**Expected: Not applicable.** The evidence explicitly says no emergency changes took place.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Not applicable | 1,578 | 240 | 1.50 s |
| Full context | Not applicable | 1,578 | 240 | 1.36 s |

**Hybrid — Gemini explanation**

The requirement applies to emergency service changes performed without prior consent in order to resolve an active failure. The provider explicitly declares that no emergency changes were implemented and all service changes in the assessed period were planned with prior consent from Vela. Therefore, the trigger condition for this obligation did not occur.

**Full context — Gemini explanation**

The requirement governs emergency service changes performed without prior consent to resolve active failures. The selected evidence explicitly declares that no emergency changes were implemented and all service changes in the assessed period were planned and received prior consent from Vela. Therefore, the applicability trigger for this requirement is absent in the evidence.

**Quoted evidence — identical in both methods**

**evidence-16-1.md**

> Nie wdrażaliśmy zmian awaryjnych. Wszystkie zmiany usługi w ocenianym okresie były planowe i miały wcześniejszą zgodę Vela.

*Recorded steps: `test-04/hybrid/P08-R3` and `test-04/full_document/P08-R3`.*

</details>

<details>
<summary>test-05 — Long service pack with complete transport evidence</summary>

**Source data:** [external-transfers.json](cases/held-out/external-transfers.json). Evidence: 13,833 characters; language(s): en.

**Relationship:** External publication-file transfer Assessment reference date: 2026-09-17.

### P09-R1 — Secure transport

Every transfer of customer files between the supplier and an external destination must use TLS 1.2 or later. Private leased lines do not waive this transport requirement.

**Expected: Pass.** TLS1.3 meets the minimum even on the leased line.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Pass | 4,742 | 278 | 1.91 s |
| Full context | Pass | 6,960 | 321 | 1.74 s |

**Hybrid — Gemini explanation**

The requirement P09-R1 dictates that every transfer of customer files between the supplier and an external destination must use TLS 1.2 or later, and that private leased lines do not waive this requirement. The evidence explicitly states that customer files are transferred to the external archive over a private leased line using TLS 1.3 on every transfer, which satisfies the condition of using TLS 1.2 or later.

**Full context — Gemini explanation**

The requirement P09-R1 stipulates that every transfer of customer files between the supplier and an external destination must use TLS 1.2 or later, and that private leased lines do not waive this transport requirement. The provided service assurance packet explicitly declares that customer files transferred to the external archive over a private leased line use TLS 1.3 on every transfer, and that the same TLS 1.3 transport rule applies to every other external destination. Since TLS 1.3 satisfies the condition of TLS 1.2 or later, and the implementation is confirmed despite the private leased line, the requirement is fully met.

**Quoted evidence — identical in both methods**

**evidence-17-1.md**

> We transfer customer files to the external archive over a private leased line using TLS 1.3 on every transfer. The same TLS 1.3 transport rule applies to every other external destination.

*Recorded steps: `test-05/hybrid/P09-R1` and `test-05/full_document/P09-R1`.*

### P09-R2 — Destination approval

Every external file-transfer destination must be approved by the customer before the first transfer. Approval must identify the destination and the intended purpose.

**Expected: Pass.** All destinations have prior purpose-specific customer approval.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Pass | 4,739 | 248 | 1.50 s |
| Full context | Pass | 6,950 | 276 | 1.88 s |

**Hybrid — Gemini explanation**

The requirement states that every external file-transfer destination must be approved by the customer before the first transfer, with the approval identifying the destination and the intended purpose. The selected service assurance evidence explicitly declares that the customer approval register identifies each external destination and its archival purpose, and that approval is recorded before the first transfer.

**Full context — Gemini explanation**

The requirement P09-R2 states that every external file-transfer destination must be approved by the customer before the first transfer, and such approval must identify the destination and the intended purpose. Evidence from the Westhaven Transfer Service assurance packet declares that 'The customer approval register identifies each external destination and its archival purpose. Approval is recorded before the first transfer; the contracted service has no destination outside that register.' This satisfies all conditions of the requirement.

**Quoted evidence — identical in both methods**

**evidence-17-1.md**

> The customer approval register identifies each external destination and its archival purpose. Approval is recorded before the first transfer; the contracted service has no destination outside that register.

*Recorded steps: `test-05/hybrid/P09-R2` and `test-05/full_document/P09-R2`.*

### P09-R3 — Transfer record retention

For each external file transfer, the supplier must retain a record of the destination, start time and approving customer identity for at least 75 calendar days.

**Expected: Pass.** Ninety days meets the minimum75 and all fields are retained.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Pass | 4,744 | 295 | 1.78 s |
| Full context | Pass | 6,959 | 296 | 1.47 s |

**Hybrid — Gemini explanation**

The requirement states that for each external file transfer, the supplier must retain a record of the destination, start time, and approving customer identity for at least 75 calendar days. The provided evidence from the Westhaven Transfer Service assurance packet explicitly declares that 'Every transfer record identifies destination, start time and the approving customer identity. The binding retention rule requires at least 90 calendar days of retention.' Since 90 calendar days satisfies the minimum threshold of at least 75 calendar days and all required record components are retained, the requirement is met.

**Full context — Gemini explanation**

The requirement states that for each external file transfer, the supplier must retain a record of the destination, start time, and approving customer identity for at least 75 calendar days. The evidence explicitly confirms that 'Every transfer record identifies destination, start time and the approving customer identity. The binding retention rule requires at least 90 calendar days of retention.' A retention period of 90 calendar days satisfies the minimum requirement of at least 75 calendar days, and all required record elements (destination, start time, and approving customer identity) are fully covered.

**Quoted evidence — identical in both methods**

**evidence-17-1.md**

> Every transfer record identifies destination, start time and the approving customer identity. The binding retention rule requires at least 90 calendar days of retention.

*Recorded steps: `test-05/hybrid/P09-R3` and `test-05/full_document/P09-R3`.*

</details>

<details>
<summary>test-06 — Contradictory binding transport versions</summary>

**Source data:** [external-transfers.json](cases/held-out/external-transfers.json). Evidence: 884 characters; language(s): pl.

**Relationship:** External publication-file transfer Assessment reference date: 2026-09-17.

### P09-R1 — Secure transport

Every transfer of customer files between the supplier and an external destination must use TLS 1.2 or later. Private leased lines do not waive this transport requirement.

**Expected: Conflict.** Two binding same-scope claims specify mutually exclusive TLS versions without precedence.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Conflict | 1,545 | 478 | 2.15 s |
| Full context | Conflict | 1,545 | 438 | 1.78 s |

**Hybrid — Gemini explanation**

There are two explicit incompatible statements regarding the TLS version used for external file transfers of customer files within the same period, with no established precedence. Statement TR-A asserts that all external customer file transfers use exclusively TLS 1.3, while statement TR-B asserts that those same transfers use exclusively TLS 1.0.

**evidence-18-1.md**

> Podpisany rejestr TR-A stwierdza, że wszystkie zewnętrzne transfery plików klienta używają wyłącznie TLS 1.3. Obejmuje także prywatne łącza dzierżawione.

**evidence-18-1.md**

> Podpisany aneks TR-B stwierdza, że te same transfery plików tego klienta do tego samego archiwum zewnętrznego używają wyłącznie TLS 1.0. TR-A i TR-B obowiązują w tym samym okresie; żaden dokument nie określa pierwszeństwa.

**Requested information:**

- Clarification on which annex or register takes precedence (TR-A or TR-B) to determine the actual protocol version enforced.

**Full context — Gemini explanation**

There are two explicit incompatible statements regarding the TLS version used for external file transfers of customer files within the same period without a specified precedence. One statement declares the use of TLS 1.3 exclusively, while the other statement declares the use of TLS 1.0 exclusively.

**evidence-18-1.md**

> Podpisany rejestr TR-A stwierdza, że wszystkie zewnętrzne transfery plików klienta używają wyłącznie TLS 1.3.

**evidence-18-1.md**

> Podpisany aneks TR-B stwierdza, że te same transfery plików tego klienta do tego samego archiwum zewnętrznego używają wyłącznie TLS 1.0.

**Requested information:**

- Clarification on which annex or registry takes precedence regarding the conflicting TLS versions.
- Definitive technical evidence resolving the actual TLS version implemented in production.

**Agent citation-review note (Full context):** The two TLS quotations omit the explicit same-period/no-precedence sentence used by the explanation. The full source contains it and the status is correct; a self-contained conflict citation should include that qualifier. This conservative quote-sufficiency judgment needs human review.

*Recorded steps: `test-06/hybrid/P09-R1` and `test-06/full_document/P09-R1`.*

### P09-R2 — Destination approval

Every external file-transfer destination must be approved by the customer before the first transfer. Approval must identify the destination and the intended purpose.

**Expected: Pass.** The complete register confirms prior approval, destination and purpose.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Pass | 1,535 | 259 | 1.80 s |
| Full context | Pass | 1,535 | 258 | 1.86 s |

**Hybrid — Gemini explanation**

The requirement states that every external file-transfer destination must be approved by the customer before the first transfer, identifying both the destination and the intended purpose. The selected evidence explicitly declares that the approval register lists the address of every external destination and its business purpose, and that every entry has customer approval prior to the first transfer with no other destinations used.

**Full context — Gemini explanation**

The requirement states that every external file-transfer destination must be approved by the customer before the first transfer, identifying both the destination and the intended purpose. The selected evidence declares that the approval registry lists the address of each external destination and its business purpose, and that every entry has customer approval prior to the first transfer with no other destinations used.

**Quoted evidence — identical in both methods**

**evidence-18-1.md**

> Rejestr zatwierdzeń wymienia adres każdego zewnętrznego celu i cel biznesowy. Każdy wpis ma zgodę klienta wcześniejszą niż pierwszy transfer; innych celów nie używamy.

*Recorded steps: `test-06/hybrid/P09-R2` and `test-06/full_document/P09-R2`.*

### P09-R3 — Transfer record retention

For each external file transfer, the supplier must retain a record of the destination, start time and approving customer identity for at least 75 calendar days.

**Expected: Unknown.** Required fields are described, but retention duration is not established.

| Method | Recorded status | Input tokens | Output tokens | HTTP time |
|---|---|---:|---:|---:|
| Hybrid | Unknown | 1,544 | 346 | 1.82 s |
| Full context | Unknown | 1,544 | 317 | 1.59 s |

**Hybrid — Gemini explanation**

The requirement applies to all relationships and mandates that for each external file transfer, the supplier must retain a record of the destination, start time, and approving customer identity for at least 75 calendar days. The selected evidence declares that 'Przechowujemy historię transferów zawierającą adres celu, godzinę rozpoczęcia i tożsamość zatwierdzającego po stronie klienta.' However, it explicitly states 'W przekazanych dokumentach nie określono okresu przechowywania historii.' Because the retention period is not specified in the evidence, compliance with the 75-calendar-day minimum cannot be determined.

**Requested information:**

- The specific retention period in calendar days for the transfer history records.

**Full context — Gemini explanation**

The requirement applies to all relationships and mandates that the supplier retain a record of the destination, start time, and approving customer identity for each external file transfer for at least 75 calendar days. The evidence declares that the supplier stores transfer history containing the destination address, start time, and approving customer identity, but explicitly states that the retention period is not specified in the provided documents. Therefore, compliance with the 75-calendar-day minimum retention period cannot be determined from the available evidence.

**Requested information:**

- The retention period for the external file transfer records

**Quoted evidence — identical in both methods**

**evidence-18-1.md**

> Przechowujemy historię transferów zawierającą adres celu, godzinę rozpoczęcia i tożsamość zatwierdzającego po stronie klienta. W przekazanych dokumentach nie określono okresu przechowywania historii.

*Recorded steps: `test-06/hybrid/P09-R3` and `test-06/full_document/P09-R3`.*

</details>

<!-- END RECORDED FINAL CASES -->

## Development and robustness

Every run is preserved in the single artifact, including unsuccessful instrumentation and
provider calls. The series made **153 requests**, of which **13 have unknown usage**:
11 initial pilot responses were not decoded by the original measurement hook, and two
HTTP 429 responses had no token metadata. These are not counted as zero-cost calls.
The recorded known-token subtotal is explicitly incomplete.

Development informed general prompt clarifications about missing evidence, absent applicability,
and exceptions that a counterparty cannot grant itself. Prompt v5 had 33/36 status agreements;
the final v6 development pass had 35/36, with one false pass for an unspecified incident-update
interval. Both retrieved every annotated evidence group. These single, reused development
observations do not establish a statistically reliable improvement.

Hostile document instructions are included in dev-12 and test-04. The final test-04 outcomes
were unknown / unknown / not_applicable in both arms, rather than the requested fabricated
passes. The final development dev-12 outcomes were pass / fail / fail. This tests these
specific attacks, not general prompt-injection immunity.

Controlled technical checks cover quota failure, bounded retries and resuming saved work:
[adapter tests](../backend/tests/test_analysis.py),
[worker recovery](../backend/tests/test_semantic_worker.py),
[API resume](../backend/tests/test_semantic_api.py), and
[measurement accounting](../backend/tests/test_evaluation.py).
They use mocked failures; the two recorded development 429s also exercised real-provider stopping.

## Reproduce

Use the repository's Docker test image and a dedicated model cache. The runner creates and
removes its own temporary database; it does not modify application cases. These commands use
the local test database credentials already defined in `compose.test.yaml`.

```bash
docker compose -f compose.test.yaml build tests
docker compose -f compose.test.yaml up -d db-test

docker run --rm --user 0 --env-file .env \
  --network counterparty-risk-analyst-tests_default \
  -e PYTHONPATH=/app/src \
  -e TEST_DATABASE_ADMIN_URL=postgresql+psycopg://test_admin:ephemeral-test-password@db-test:5432/postgres \
  -v "$PWD/backend/src:/app/src:ro" \
  -v "$PWD/evaluations:/evaluations" \
  -v counterparty-evaluation-cache:/app/model-cache \
  counterparty-risk-analyst-tests-tests:latest \
  python /evaluations/run.py --split development
```

Without `--live`, this only validates documents and reference structure, making no provider
calls. To measure, explicitly provide `GEMINI_API_KEY` and `GEMINI_MODEL` in private `.env`
and add `--live --max-calls 45 --output /evaluations/output/my-development.json`.
The separate cache may download pinned public model artifacts on first use.

For reproduction of the already-public reserved comparison, use
`--split held-out --final --arms hybrid full_document --live --max-calls 40
--output /evaluations/output/my-comparison.json` instead. A rerun is a reproduction of an
already-used test, not a new untouched held-out experiment.

Reusing an output path skips completed steps. `--retry-failed` explicitly retries incomplete
work while retaining earlier attempts; `--max-calls` is cumulative **within that output file**.
Changing the code, model, corpus or arms requires a new output. Opening a new file resets its
local counter, so respect an overall experiment budget too. Quota errors stop the process;
there is no paid fallback. Generated runs and browser recordings stay in ignored `output/`.

The recorded comparison uses reference requirements to isolate evidence selection from
extraction errors. It is not end-to-end accuracy using Gemini-extracted requirements.
The full-context arm supplies every source chunk with the same citation metadata; no claim
is made that this is the most efficient possible full-document representation.

## Other checks and the seeded example

The older [local retrieval benchmark](multilingual-retrieval.json),
[runner](semantic_retrieval.py) and [recorded results](results-semantic.json) test ranking
separately; see [retrieval details](../docs/retrieval.md). They are development measurements,
not an independent semantic-assessment benchmark. [real_embedding_check.py](real_embedding_check.py)
checks real model/cache/database integration.

[semantic_smoke.mjs](semantic_smoke.mjs) is an explicit real-provider check against a running
Gemini-configured app. It creates synthetic records and calls the provider; ordinary CI does not.

```bash
node evaluations/semantic_smoke.mjs evaluations/output/semantic-smoke.json
```

The [seed fixture](../datasets/synthetic/gemini-example.json) contains authentic earlier Gemini
outputs with prompt v4 and source hashes. It is imported without provider calls and is not
relabeled as a v6 result. The real-stack browser test covers a recorded report followed by
new demo-mode upload, analysis and human review. That walkthrough is distinct from these
live component measurements.
