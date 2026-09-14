# Northstar synthetic corpus acceptance — 2026-09-15

The fresh synthetic workspace now contains two organizations, five existing role
accounts, four policy documents and one approved **Northstar Labs Third-Party
Assurance Standard** with 20 curated supplier obligations. It creates no cases,
evidence uploads, analyses, decisions or tickets. One `synthetic.policy_seeded`
audit event records the new seed's explicit synthetic provenance. Repeating seed
creates nothing and preserves IDs, source hashes and requirement objects.

The approved state is a demonstration fixture, not a claim of independent human
review. The author checked the separate expected-rule manifest against source
clauses. An independent human review remains pending. The sources identify the
supplier actor separately from internal Northstar duties and distinguish ordinary
obligations from documented exceptions.

## Corpus and grounding

Four policies contain approximately 7,000 words in 35 line-aware chunks. Each
policy has an owner, approver, dates, scope, operational responsibilities, evidence
expectations and exception handling. The Atlas declaration contains 3,092 words
and includes a consistent service scope and period, a US support subprocessor,
an honest independent-report exclusion and an explicitly untrusted appendix.

The seed reads an explicit manifest; it does not discover fixtures by directory
scan or use regex extraction as approved truth. Each curated quote must occur once
in its designated document and resolve to exactly one chunk. Resolution stores
the actual document/chunk IDs and full chunk location. A changed or ambiguous quote
fails the transaction and rolls back new files. Separate gold source anchors retain
source hashes and locations. Old tiny fixtures moved unchanged to
`datasets/synthetic/regression`; historical held-out labels were not changed.

## Bounded model processing

The serialized evaluation policy corpus is 63,274 characters before the prompt,
exceeding the adapter's 48,000-character limit. Processing now packs contiguous
chunks by actual serialized size with a 25,000-character budget including the
instruction. Document boundaries are preserved, producing four policy batches
of 9, 8, 9 and 9 chunks. No input is truncated and no cross-chunk quote is accepted.

A proposal validates every batch and the complete merged result before returning
anything to persistence. Duplicate IDs or duplicate/conflicting cited obligations
are rejected. Unsupported rule fields require manual evaluation and a null expected
value. Context-only batches may return no obligations, but the final proposal
cannot be empty. Schema validation rejects truncated/incomplete provider output;
semantic omissions are additionally measured by the development gold, not assumed
impossible merely because JSON is valid.

Fact extraction first selects authorized evidence candidates. Provider payloads
include compact approved rule fields rather than repeating full policy quotes.
Selected chunks are packed under the same budget. Exact duplicate facts collapse;
contradictory values remain. Each fact must cite its own eligible batch. The merged
output is capped at 200 facts and source provenance/injection checks remain in
place. The adapter permits at most eight HTTP attempts per operation, including
retries, and at most eight planned batches. Quota errors stop without fallback.
The configured 4,096-token response bound remains per call.

## Real Gemini development probes

The corpus informed these prompt corrections, so these measurements are **development
acceptance**, not independent model-quality evidence. No gold labels changed.
The selected provider was `gemini-3.5-flash-lite`; actual billing cost is unknown.
No paid fallback or billing activation was used.

1. [Initial whole-policy probe](../../evaluations/northstar-gemini-baseline.json):
   four calls, 17,134 input and 5,171 output tokens; proposal rejected atomically
   because an incident quote crossed a chunk boundary. The
   [isolated diagnosis](../../evaluations/northstar-incident-probe.json) showed
   the model joining an IR-04 heading with a sentence in the next chunk.
2. Prompt clarification required the obligation sentence from one chunk and its
   actual metadata. [Targeted verification](../../evaluations/northstar-incident-fixed.json)
   returned four valid incident citations in one call: 4,419 input, 1,053 output tokens.
3. [Whole-corpus rule baseline](../../evaluations/northstar-gemini-rule-baseline.json)
   found all 20 clauses with valid citations but had six rule mismatches: two
   supported booleans were classified manual and four incident-event conditions
   were incorrectly encoded as relationship-purpose equality. The acceptance gate
   rejected the result even though Atlas facts were correct.
4. Generic instructions now explicitly map required MFA, stored-data protection and
   signed agreements to supported boolean rules, and distinguish business-purpose
   context from future incident triggers. [Targeted security/incident verification](../../evaluations/northstar-rules-fixed.json)
   produced ten correct rules in two calls: 8,939 input, 2,516 output tokens.
5. [Final whole-corpus acceptance](../../evaluations/northstar-gemini.json) passed:
   20/20 supplier clauses once each, exact applicability/severity/evaluation rules,
   no extra/internal obligations and valid citations. Policy extraction used four
   calls, 17,802 input and 5,316 output tokens in 16.1 seconds. Atlas extraction used
   two calls, 9,120 input and 1,495 output tokens in 5.7 seconds.

Atlas produced all seven exact expected values. Six requirements passed and 14
manual requirements remained unknown: 30% completeness, `Unable to assess` risk,
and the possible US-support access discrepancy. The declaration did not become
independent evidence; the hostile appendix did not become a fact. A pending
support-portal assurance extension remains a reason for a reviewer to request
information. Retrieval used the existing hash-based hybrid pipeline, not E5.

## Automated verification

- Backend: 90 tests passed against disposable PostgreSQL databases using
  `compose.test.yaml` and Python 3.13; routine provider calls were mocked.
- Focused source tests cover word counts, all 20 rules and source anchors, seven
  exact facts, six/14 findings, conditional applicability, missing context,
  high-severity failure despite manual gaps, same-period conflict, different-period
  ambiguity, source/injection rejection and batch/output bounds.
- Input boundaries cover upload size, extracted text size, PDF page count and
  evidence chunk count. The page-count unit test uses controlled text-page objects;
  existing document tests cover actual PDF parsing and scan rejection.
- Seed integration checks verify exact clean counts, one provenance audit event,
  unchanged IDs/hashes/requirements after repeat invocation and no provider calls.
- The historical offline evaluation gate passed; no held-out labels were changed.
- Frontend production build passed; three mocked browser tests passed.

The updated real-stack journey uploads Atlas as a counterparty declaration, expects
30% completeness and requests information before separately approving a local
ticket. Runtime replacement and that live journey are coordinated after a verified
backup; they are not performed by the seed implementation itself. A final clean
workspace requires running the journey on a disposable database or restoring the
clean seed afterwards. No destructive reset is part of bootstrap.
