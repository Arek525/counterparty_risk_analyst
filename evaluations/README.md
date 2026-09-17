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
