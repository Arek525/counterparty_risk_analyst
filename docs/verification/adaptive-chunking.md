# Adaptive chunking and formatting robustness

## Decision

Do not replace application chunking on the evidence from this experiment.
Structural and semantic candidates both recover three missed paired-format
queries, but neither meets the improvement threshold frozen before measurement.
Semantic splitting provides no accuracy benefit over structural splitting here
and takes about three times as long to prepare the same documents.

This is a completed comparison with a conditional no-change decision, not a
deployed semantic splitter. Runtime ingestion, indexing, historical source IDs,
database records, model configuration and the UI remain unchanged.

## Corpus and procedure

Measured on 2026-09-15. Eight canonical synthetic documents represent a policy
and an evidence pack for each of four fictional organizations. Aster and
Meridian are English; Orion and Brzeg are Polish. Documents cover account
authentication, deletion, incident notices, encryption, location/support access
and assurance exclusions. Each query requires both the main rule/declaration and
its qualification, separated by an explanatory paragraph.

Each canonical document is rendered as Markdown, continuous prose, hard-wrapped
text and mixed bullet lists/one-column tables. English documents additionally
have real generated text PDFs, parsed through pypdf with page boundaries
preserved. This gives 36 rendered documents and 216 query-layout observations.
The canonical texts are approximately 4,600–5,300 characters each.

**These are not 216 independent examples or eight independently authored company
styles.** Organizations share language-specific generation templates, and layout
variants preserve the same content. This is a controlled formatting stress test.
It improves coverage of line breaks, tables, PDF pages and qualifications, but
does not test arbitrary long enterprise documents, scans, complex multi-column
PDFs or independently reviewed policies.

The corpus and anchors were generated and frozen before retrieval. Development
uses Aster/Orion (108 observations); the confirmation group uses Meridian/Brzeg
(108). Shared templates make the latter a consistency check, not a strong
independent held-out benchmark. No parameter was retuned after scores were seen.

The [protocol](../../evaluations/adaptive-chunking-protocol.md) fixes the methods,
budget and adoption gates. Each candidate has a hard 1,800-character source
ceiling. Structural splitting reuses the prior experiment. Semantic splitting
compares adjacent sentence embeddings using the pinned local E5 model, a fixed
85th-percentile distance threshold with a 0.12 floor, minimum accumulated length
400, and a one-sentence lookback when it fits. This lookback is part of the
semantic candidate and its extra text is counted; the experiment does not
attribute all effects solely to semantic boundary detection.

Queries use cosine ranking within each eligible document. At the fixed budget,
complete chunks are visited in rank order and included when they fit within
4,000 source characters. A hit requires coverage of both designated source spans.
The measurement tolerates whitespace and a line break after a literal hyphen;
it does not invent omitted words or remove missing non-whitespace source gaps.

## Measured results

| Measure | Current | Structure | Semantic + lookback |
|---|---:|---:|---:|
| Full target at 4,000 chars, development | 105/108 (97.2%) | 108/108 | 108/108 |
| Full target at 4,000 chars, confirmation | 108/108 | 108/108 | 108/108 |
| Full target at 4,000 chars, all observations | 213/216 (98.6%) | 216/216 | 216/216 |
| Full target in top 3, all observations | 216/216 | 216/216 | 216/216 |
| Full target in top 8, all observations | 216/216 | 216/216 | 216/216 |
| Rule found without qualifier at 4,000 chars | 0 | 0 | 0 |
| Mean source chars used under 4,000 ceiling | 3,295 | 3,359 | 3,681 |
| Mean source chars in top 8 | 4,927 | 4,931 | 5,417 |
| Chunks across all rendered documents | 116 | 148 | 240 |
| Total split + embedding time, seconds | 14.61 | 14.68 | 44.52 |

Timings are single warm-model passes, excluding model startup and shared query
embedding; they are not a statistically controlled performance benchmark.
Candidate order is fixed. Semantic preparation includes the additional sentence
embeddings required to choose boundaries. No GPU, Gemini request or paid service
was used; the measurement container had networking disabled.

Breakdown of full-target coverage at 4,000 chars:

| Group | Current | Structure | Semantic + lookback |
|---|---:|---:|---:|
| English | 120/120 | 120/120 | 120/120 |
| Polish | 93/96 | 96/96 | 96/96 |
| Policy | 107/108 | 108/108 | 108/108 |
| Evidence | 106/108 | 108/108 | 108/108 |
| Markdown | 48/48 | 48/48 | 48/48 |
| Prose | 47/48 | 48/48 | 48/48 |
| Hard-wrapped text | 48/48 | 48/48 | 48/48 |
| Mixed lists/table | 46/48 | 48/48 | 48/48 |
| Text PDF | 24/24 | 24/24 | 24/24 |

Current misses concern Orion deletion in mixed formatting (policy and evidence)
and Orion incident notice in continuous prose (evidence). Top 3 retrieves those
targets, but fitting whole current chunks inside 4,000 characters omits them.
None of these cases retrieved a rule while concealing its required qualifier.
The maximum baseline accuracy is a ceiling effect: this corpus cannot establish
the required five-point confirmation improvement, and does not justify claiming
that current chunking handles arbitrary documents correctly.

## Gate outcome and implications

Structure wins the development tie, as specified in the protocol. Its improvement
is 2.78 percentage points on development and zero on confirmation, below the
required 5 points on both. Other primary safety/volume/time gates pass. The Atlas
regression check and runtime integration are conditional on these initial gates
passing, so neither was triggered. The prior broader Atlas comparison remains
relevant and already showed some structural retrieval regressions.

The appropriate conclusion is that automatic topic detection has not earned its
added runtime complexity. It is not evidence that semantic chunking can never
help. A further generalization study needs independently varied, substantially
longer policy and evidence documents, with multiple services, cross-references
and exceptions on distant pages, then frozen human-reviewed expected evidence.
That follow-up should be a new versioned experiment, not a silent change to this
corpus or gate to produce a preferred winner.

Both roles here are measured as source retrieval. Actual policy requirement
extraction processes source batches; no LLM extraction/compliance accuracy,
Gemini tokens, billing, or full HTTP request size was measured. Top-8 character
counts include semantic overlap, and must not be called unique source size.

## Verification and reproduction

Five targeted tests passed: topic-boundary/context behavior with controlled
vectors, long unbroken source preservation and bounds, rule-without-qualifier
rejection, actual text-PDF extraction, and line breaks after a hyphen. The last
test first failed against the original matcher, then passed with the correction.
An initial measurement stopped on this matcher defect before completing any
variant; frozen documents, labels and candidate thresholds were not changed.
The final measurement additionally validated every file hash, every source anchor,
all source spans and hard chunk bounds. Ruff lint/format checks passed.

- [Runner and fixture generator](../../evaluations/adaptive_chunking.py)
- [Frozen source documents and query manifest](../../evaluations/adaptive-chunking-corpus/manifest.json)
- [Raw metrics, groups, rankings and fingerprints](../../evaluations/adaptive-chunking-results.json)
- [Targeted tests](../../evaluations/test_adaptive_chunking.py)

With the already built backend image and cached E5 weights, from the repo root:

```bash
docker run --rm --network none \
  -v "$PWD:/repo:ro" \
  -v counterparty-risk-analyst_model-cache:/app/model-cache \
  counterparty-risk-analyst-api:local \
  python /repo/evaluations/adaptive_chunking.py measure \
  --corpus /repo/evaluations/adaptive-chunking-corpus \
  --cache /app/model-cache --output /tmp/adaptive-results.json
```

Metrics print to the terminal. Mount a writable results directory to retain the
JSON output beyond the disposable container. Runtime application tests were not
rerun because the gate rejected an application change.
