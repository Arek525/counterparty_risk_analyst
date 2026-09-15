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
5. Initial v4 whole-corpus acceptance (retained in Git commit `52d9b90`) passed:
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

## Generic document review corrections

Independent review found three cases not covered by the initial Atlas journey.
Retrieval rankings could alternate chunks from different documents and exhaust the
batch count despite a small input; the prompt referred only to suppliers; and a
size split could lose section-level scope from an earlier batch.

Selected evidence is now ordered by document, page and line before packing, without
changing which chunks retrieval selected. The prompt covers external suppliers,
customers and partners, while excluding the assessing organization's own internal
duties. Unrepresentable relationship conditions require manual evaluation rather
than an unconditional executable rule; future incident readiness commitments remain
distinct from relationship conditions.

Policy batches now carry bounded untrusted context: the document introduction,
active Markdown headings and opening paragraphs, and adjacent preceding text.
Context is included in the serialized input budget. Only current chunks can supply
new obligations or citations; context cannot create repeated requirements. A split
without explicit Markdown section context, an overlarge context (8,000 serialized
characters), or a context/chunk pair exceeding the total budget is rejected before
provider calls. This boundary matters for long unstructured TXT/PDF policies: users
need to split them into scoped sections when they exceed a single batch. Context
preservation does not establish universal semantic understanding of policy prose.

Regression checks cover interleaved retrieval from two documents, customer/partner
roles alongside an internal owner, inherited section scope across the size boundary,
rejection of citations from context, unstructured split rejection, and exact fact
cardinality. The gold gate now rejects extra same-valued facts as well as incorrect
values. Expected scope/period labels were not invented or changed.

After these corrections, the full backend suite passed 96 tests in 23.74 seconds;
Ruff, formatting, diff checks and offline Northstar acceptance passed. New real-model
probes are coordinated separately and do not run in the regression suite.

The [generic-role live probe](../../evaluations/generic-policy-gemini.json) passed:
17 chunks split into two batches, with personal-data scope and High severity in the
introduction and customer/partner obligations at the end. Both external obligations
were extracted correctly; the internal Cedar duty was excluded. The artifact
includes a reproducible input recipe. Two calls used 9,852 input and 494 output
tokens in 4.3 seconds.

A subsequent [v5 Northstar run](../../evaluations/northstar-gemini-v5-error.json)
was safely rejected for another opaque-coordinate error. An
[isolated incident call](../../evaluations/northstar-incident-v5.json) happened to
return correct coordinates; [the captured production-payload diagnosis](../../evaluations/northstar-incident-v5-context.json)
showed the exact unchanged IR-04 sentence paired with the preceding heading's chunk
ID and location. This variability remains evidence of model limitations.

Gemini proposals now resolve a failed citation's **unchanged literal quote** only
within its claimed document and the current eligible batch. Exactly one chunk and
one occurrence are required. Only `chunk_id` and `location` are replaced with actual
source metadata, then full strict source validation runs again. No quote rewriting,
fuzzy matching, context lookup or cross-document lookup is permitted. The correction
count is recorded in model metrics and the `policy.proposed` audit event. Manual API
edits still use strict validation directly. Regression tests cover unique relocation
and rejection of absent, ambiguous, cross-document, context-only and stitched quotes.

The same canonical-coordinate check also applies to Gemini fact batches. After
source-order grouping, a [captured Atlas response](../../evaluations/northstar-fact-probe.json)
had seven correct quotes and chunk/document IDs, but returned invented narrow
locations such as `line 17` instead of the supplied full-chunk location. The
[whole-run artifact](../../evaluations/northstar-gemini-fact-error.json) preserves
that rejected attempt. Exact unique grounding now corrects those coordinates before
fact aggregation. Report metrics count corrections; evidence type and injection
checks still run afterwards. A regression rejects even an otherwise valid fact
source when it belongs to a later batch, preserving the eligible-source boundary.


After the shared source-coordinate correction, the full backend suite passed
106 tests in 23.79 seconds; Ruff, formatting and diff checks passed. Provider calls
remained mocked. Manual source editing and source-document isolation were not
relaxed by the Gemini-only correction path.

[Final v5 acceptance](../../evaluations/northstar-gemini.json) passed all 20 policy
rules and all seven exact Atlas facts with the stricter cardinality gate. Four
policy calls used 18,322 input and 5,093 output tokens in 15.70 seconds, with one
uniquely grounded coordinate correction. Two fact calls used 9,120 input and 1,439
output tokens in 5.22 seconds, with seven location corrections. The final result
remains six passes, 14 unknowns, 30% completeness and Unable to assess, with the
US-support discrepancy. No additional provider calls were used to repair citations.
