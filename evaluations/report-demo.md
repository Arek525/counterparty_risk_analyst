# Synthetic analysis evaluation

Dataset: `synthetic-held-out-v1`. Mode: `demo`. Cases: 10.

| Variant | Extraction P/R | Status accuracy | Risk accuracy | Retrieval recall@3 | Exact citation resolution | Completeness MAE | Mean ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical | 100.0%/100.0% | 91.7% | 90.0% | 90.9% | 100.0% | 10.0 | 0.34 |
| hybrid | 100.0%/100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.0 | 0.18 |

These are measured deterministic demo results on ten hand-authored synthetic cases. They do not validate a real LLM, legal interpretation, multilingual extraction, semantic entailment, or production safety. Hash embeddings are a local demonstration, not a trained semantic embedding model. Exact citation resolution proves a quote exists, not that it supports an arbitrary model interpretation.

The lexical baseline intentionally misses synonym-only evidence. Hybrid adds deterministic hash similarity and explicit aliases; this tiny regression set is not evidence of general semantic quality. Expected outputs were authored separately from the application demo documents. No statistical significance or independently reviewed gold labels are claimed. Human review of labels and a larger frozen corpus remain necessary.

Real-model evaluation is separate: `PYTHONPATH=backend/src python evaluations/run.py --mode gemini`. Without credentials and a selected model it writes pending status and exits 2. Calls have bounded input/output, timeout, retries and concurrency; quota exhaustion stops. Provider cost is unknown (null), never reported as free. Check account pricing, quotas and data terms before enabling credentials. No paid fallback or billing activation is implemented.

Baseline acceptance target for this fixed regression set: hybrid status/risk accuracy >= 90%, citation resolution 100%, no adversarial instruction override. These are regression targets chosen after baseline, not universal model quality thresholds. See JSON for individual cases and measurements.
