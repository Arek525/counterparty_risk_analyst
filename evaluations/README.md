# Analysis evaluation

Run from the repository root in the backend Python environment:

```bash
PYTHONPATH=backend/src python evaluations/run.py
PYTHONPATH=backend/src python evaluations/run.py --check
PYTHONPATH=backend/src python -m pytest evaluations/test_gate.py
PYTHONPATH=backend/src python evaluations/run.py --mode gemini
```

`--check` writes the same reviewable reports and exits 1 if hybrid status or risk
accuracy is below 90%, citation resolution is below 100%, either pipeline obeys
the adversarial instruction, or a required case is missing. The dedicated gate
tests include deliberate failures to verify CI catches regressions. The gate is
only for the fixed demo dataset; `--check --mode gemini` is rejected before calls.
Default evaluation without `--check` remains a reporting command.

The real-model command
requires `GEMINI_API_KEY` and an explicitly chosen `GEMINI_MODEL`; missing values
write `pending_credentials` to `results-gemini.json` and exit 2. No real model calls
were made for the committed demo report. Separate live results now exist for
`gemini-3.5-flash-lite`: [report](report-gemini.md), [first baseline](results-gemini-baseline.json),
and [verification notes](../docs/verification/gemini.md). Dataset review and broader
quality validation remain unfinished. Never add credentials to Git.

`held_out.json` is a small versioned synthetic regression set separate from the
Northstar/Orchard development examples in `datasets/synthetic`. Gold labels are
hand-authored for this project, not independently reviewed. Ten cases cover complete,
missing, high-with-missing, direct contradiction, different scope/period, regional
ambiguity, inapplicability, synonym retrieval, arbitrary manual policy and injection.
Results retain each generated report so metric totals can be inspected.
This corpus has now been used to fix real-provider integration and prompts, so
it is a development regression set, not an untouched final test set.

The extraction metric matches field/value pairs, not scope or period accuracy.
Citation resolution checks exact quote/document/location, not semantic entailment.
Retrieval recall@3 checks manually listed relevant chunks. Analysis uses top8 and
can therefore behave differently from the top3 retrieval metric on larger inputs.
Report completeness compares resolved applicable findings against expected labels.
Authorization, recovery and UI behavior have separate integration checks.

## Demo and provider boundaries

API runs can persist scoped pgvector cosine similarities in the immutable snapshot.
The engine consumes those stored similarities for hybrid ranking. This offline
benchmark computes the same cosine scores locally and does not measure PostgreSQL
query latency or database scope isolation.

Demo is an English pattern extractor and 128-dimensional signed hash embeddings
with a small alias vocabulary (`demo-hash-v1`). It does not run an LLM. Supported
fields: `retention_days`, `notification_hours`, `hosting_region`,
`subprocessors_region`, `mfa`, `encryption_at_rest`, `dpa_signed`. Other custom
policies remain editable manual requirements with unknown findings. Uploaded
policies need human review and approval; proposal thresholds come from their text.
No Polish extraction quality claim is made, although application output is Polish.
Compound statements isolate values by named-control clauses; decimal thresholds
remain numeric. Pattern extraction still does not provide general language
understanding. Real-model citation validation establishes source resolution, not
semantic entailment of the extracted value; reviewer assessment and provider
evaluation remain necessary.

Gemini uses REST `generateContent`, JSON schema structured output and local
Pydantic validation. Sources must resolve to the eligible snapshot. It cannot assign
risk, change access controls, execute rules, approve decisions or create tickets.
Metadata controls whether evidence is a declaration or independent supporting
material. Local code calculates findings/risk with a fixed operator allowlist.

Provider limits: 48,000 input characters, 4,096 output tokens, 250,000 response
bytes, 25-second read timeout/5-second connect timeout, checked 60-second total
runtime boundary, two attempts only on transient network/server errors, one active
request per process, at least two seconds between calls. HTTP 429 stops immediately.
No paid fallback exists; account billing is not changed. These process-local rate
limits are not a distributed quota manager. Actual account pricing and usage must
be checked before credentials are enabled; real cost is reported `null`, never zero.

Source for the implemented optional API contract:
[Google structured output documentation](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).
Live compatibility was checked with Gemini 3.5 Flash-Lite. Large top-level batch
`maxItems` caused HTTP 400; these bounds remain in local Pydantic validation
(200 facts, 100 requirements), while token/byte caps still bound provider output.
Region aliases such as `European Union`/`EU` are canonicalized for equality and
discrepancy checks. The original `raw_value` is retained when changed and used for
text operators such as `contains`, so normalization cannot create substring matches.

## Explicit risk rules v1

A confirmed High failure yields High even if another requirement is unknown.
Medium or Low failures yield Medium. Conflicting same-fact evidence with a failing
value preserves that conservative severity while the finding remains conflict.
Low requires every applicable requirement resolved and no discrepancy. Otherwise
risk is `Unable to assess`. An all-inapplicable set has 100% evidence completeness
but cannot establish Low risk. Completeness counts pass/fail, excluding conflicts,
unknowns and requirements that do not apply. Human decision remains separate.

Direct contradictions require equal explicit scope and period; differing or absent
scope/period creates an ambiguity requiring review. EU hosting plus a US
subprocessor produces a question, not an automatic contradiction or violation.
