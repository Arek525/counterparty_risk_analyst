# Real-model evaluation status

Status: **pending credentials and explicit model selection**. No real-provider
requests have been made for this release. No real-model accuracy, semantic
entailment, Polish-language quality, latency or cost result is claimed.

Required local settings: `GEMINI_API_KEY` and `GEMINI_MODEL`. The model must be
available to that account; its quotas, pricing and data-processing terms need
review before enabling calls. The application does not enable billing or provide
a paid fallback. Deterministic demo results are recorded separately.

The runner `python evaluations/run.py --mode gemini` writes a machine-readable
`results-gemini.json`. Without settings it exits 2 with `pending_credentials`.
With settings it evaluates the two retrieval variants on the frozen synthetic
corpus, records token counts and measured time, and stops on provider failure or
quota exhaustion. Unknown provider cost remains null.

Before treating a model as validated, independently review the gold labels, inspect
whether each cited quote actually supports its finding (exact quote matching alone
is insufficient), expand the corpus, agree thresholds and rerun. A tiny synthetic
set cannot establish general compliance, multilingual or production reliability.
