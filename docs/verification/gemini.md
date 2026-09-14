# Live Gemini verification — 2026-09-14

The local application can now use Gemini 3.5 Flash-Lite for evidence extraction
and policy proposals. The API key remains in the ignored `.env`; the committed
template contains no key. No billing activation, paid fallback, publication, or
real business-system writes were performed. All provider inputs were synthetic.
Measured provider cost remains unknown (`null`); no claim is made about the
account's actual billing status.

## Compatibility and corrections

Google accepted the key for Models listing but rejected generation with
`gemini-2.5-flash-lite` (HTTP 404: unavailable to new users). The provider suggested
`gemini-3.5-flash-lite`; it supports a [free tier](https://ai.google.dev/gemini-api/docs/pricing)
and answered the bounded probes. This is an explicit configuration change, not
an application fallback.

The original structured FactBatch schema produced HTTP 400. Isolated probes found
that removing its large `maxItems` bound made the same schema work. The adapter
now omits top-level array-size bounds from the provider request, while validating
the returned data against the unchanged local schemas. Input, output-token,
response-byte, timeout and retry limits remain. Offline regression tests cover
both acceptance and rejection of oversized fact/requirement batches.

The first live evaluation exposed three failures: region names (`European Union`)
were compared literally against codes (`EU`), supporting subcontractor facts were
omitted, and one injection-case response omitted the valid retention declaration.
Field-specific canonicalization and extraction prompt v2 address these observed
issues. Original values remain available as `raw_value` when normalized; text
containment uses original values. Regression tests cover the false match that
would result from looking for `US` inside `Russia`.

Policy probes also exposed invented narrower line locations, omitted conditional
applicability and an omitted manual requirement. Policy instructions now require
copying chunk metadata exactly, specify supported relationship keys and require
retaining requirements that need manual review. Source validation remains strict.

## Measured comparison

Both runs used the same ten cases in `evaluations/held_out.json`, without changing
gold labels. Each run made 20 analysis calls (10 per retrieval variant), with at
least six seconds between request starts in the verification harness. The regular
adapter retains its process-local two-second spacing. Diagnostic/policy/browser
calls are additional and are not included in the table's token totals.

| Measurement | Initial lexical | Initial hybrid | Updated lexical | Updated hybrid |
|---|---:|---:|---:|---:|
| Finding status accuracy | 83.3% | 83.3% | 91.7% | 100% |
| Risk accuracy | 80% | 80% | 90% | 100% |
| Extraction precision | 80% | 80% | 90.9% | 91.7% |
| Extraction recall | 72.7% | 72.7% | 90.9% | 100% |
| Exact citation resolution | 100% | 100% | 100% | 100% |
| Input/output tokens | 2351/1280 | 2401/1079 | 3311/1206 | 3361/1457 |

The updated hybrid run averaged 1.29 seconds per analysis inside the engine,
excluding harness pacing and the API queue. Its extraction precision is below
100% because the model also extracted an ethics-liaison fact that the gold set
does not list. The source does contain that statement; this mismatch warrants
independent label review, not silently changing labels to improve the score.

Full outputs: [first baseline](../../evaluations/results-gemini-baseline.json),
[updated results](../../evaluations/results-gemini.json),
[readable report](../../evaluations/report-gemini.md).

These are initial measurements, not general model validation. The corpus was
used during debugging and is now a regression set, not an untouched held-out
quality assessment. Exact quote matching establishes existence, not entailment.
No independently reviewed labels, Polish-language benchmark, repeated-run
stability estimate, or production-safety claim is provided.

## Policy and application checks

Final packaged backend suite: **77 passed**, no skips, against PostgreSQL.
Evaluation-gate/report tests: **8 passed**. Ruff checks passed.

The live policy check used the real ingestion function on the two repository
policies and called `propose_requirements(..., mode="gemini")`. Northstar produced
three requirements, including retention <=30 days and MFA conditional on
`privileged_access=true`. Orchard produced four requirements, including notice
<=24 hours, a DPA conditional on `personal_data=true`, and manual ethics review.
All seven source references passed exact quote/document/chunk-location validation.
The unapproved outputs are in [policy smoke results](../../evaluations/policy-smoke-gemini.json).
The earlier rejected source-location output is preserved in
[policy probe](../../evaluations/policy-probe-gemini.json).

The real-stack Playwright journey passed with `MODEL_MODE=gemini`: login, create
case/context, upload independent evidence, select approved Northstar policy,
worker analysis with Low/100%, open citation, record a review decision, and
separately approve/create/read a ticket in the local REST simulator.

```bash
docker compose -f compose.test.yaml up --build --abort-on-container-exit \
  --exit-code-from tests --attach tests
PYTHONPATH=backend/src python -m pytest evaluations/test_gate.py
cd frontend
E2E_REAL_API=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
  npm run test:e2e -- tests/e2e/real-stack.spec.ts
```

The browser command makes a real model call when the running stack uses Gemini.
Routine backend and evaluation-gate tests do not contact the provider.

## Local configuration and next quality work

The verified local settings are `MODEL_MODE=gemini`,
`GEMINI_MODEL=gemini-3.5-flash-lite`, and a private `GEMINI_API_KEY`.
Recreate API/worker after changes: `docker compose up -d api worker`.
Demo accounts remain enabled locally. Old reports retain their original model
mode; create a new analysis to obtain a Gemini report.

Next: independently review labels, freeze a larger fresh corpus with Polish and
longer documents, test extraction/applicability/citation semantics separately,
repeat adversarial cases for stability, and agree real-model acceptance thresholds.
Current successful synthetic measurements do not remove the human approval step.
