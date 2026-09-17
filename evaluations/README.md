# Evaluation

This directory contains one reproducible local retrieval benchmark and an explicit
live-provider smoke check. Historical regression fixtures live under `backend/tests/`.
All documents and labels are synthetic. There is not yet an independently reviewed
quality evaluation of the complete semantic-v2 pipeline.

## Local retrieval benchmark

- [multilingual-retrieval.json](multilingual-retrieval.json): 24 passages and 12
  bilingual queries with expected relevant passages.
- [semantic_retrieval.py](semantic_retrieval.py): compares lexical, semantic and
  hybrid ranking using the pinned multilingual E5 model.
- [results-semantic.json](results-semantic.json): recorded development measurement.
- [Method and limitations](../docs/retrieval.md): preprocessing,
  metrics and interpretation. This measures retrieval, not LLM assessment quality.
- [real_embedding_check.py](real_embedding_check.py): real model/cache and database
  integration checks, separate from ordinary tests.

With the backend dependencies installed and a model cache available:

```bash
PYTHONPATH=backend/src python evaluations/semantic_retrieval.py --cache /path/to/model-cache
```

The command may download public model weights if absent; it does not call Gemini.
New results go to ignored `evaluations/output/`, preserving the recorded baseline.
The synthetic labels informed development and have not received independent human
review. They are not an untouched held-out test or evidence of generalization.

## Explicit current-pipeline smoke check

[semantic_smoke.mjs](semantic_smoke.mjs) runs a small source-grounded extraction and
assessment scenario through a running application configured for Gemini. It makes
real provider calls and creates synthetic records. It is never run by ordinary CI.

```bash
mkdir -p evaluations/output
node evaluations/semantic_smoke.mjs evaluations/output/semantic-smoke.json
```

This verifies a bounded integration example, not broad model quality. Routine
whole-application demo verification is in `frontend/tests/e2e/real-stack.spec.ts`.

## Recorded application example

The [seed fixture](../datasets/synthetic/gemini-example.json) contains real Gemini
requirements and findings for the bundled Northstar/Atlas documents, plus source
hashes, capture date, model, prompt version, extraction/assessment usage and retrieval
provenance. The application seed imports it without provider calls. It is a reviewed
development example, not gold labels or an independent model-quality measurement.
The initial capture exposed an incorrect maximum-deadline interpretation; prompt v4
clarified bound direction and the entire report was regenerated using the same
extracted requirements. This example therefore informed prompt development.
