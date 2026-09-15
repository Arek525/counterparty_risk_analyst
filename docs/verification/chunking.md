# Chunk boundary comparison

Measured on 2026-09-15 using the pinned local multilingual E5 model. This is an
offline development experiment, not a deployed ingestion change. No database,
application document, historical citation or provider configuration was changed.
The container had networking disabled; no Gemini calls were made.

## Method

Compare three variants with the same 1,800-character source-text ceiling:

- `current`: the application's existing complete-line packing, including hard
  splitting of exceptionally long lines.
- `structure`: start a new section at each Markdown ATX heading; pack complete
  paragraphs within that section, falling back to sentence boundaries and then
  hard splitting for oversized text. No overlapping chunks or neighbor expansion.
- `structure_heading`: identical structural chunks, with the ancestor heading
  path prepended only to the embedding input. Quoted source text and simulated
  Gemini document payloads remain original substrings.

This tests document structure heuristics, not an AI that detects topic changes.
There is no new dependency. All variants use the same E5 inference, query
composition and cosine ranking. Source and script hashes are in the raw results.

Twenty queries use the existing Northstar requirement titles and fields to search
the full Atlas assurance pack. Their expected literal anchors were selected from
the source and frozen before ranking. These are relevant passages for review,
including evidence limitations; finding one does not prove a control passes.
Twenty additional queries search the four complete Northstar policy documents
using the existing curated supplier-clause anchors. Policy search is a secondary
diagnostic: runtime policy extraction processes source batches rather than this
retrieval exercise. The two tasks must not be pooled into a headline score.

Hit rate means the selected source spans cover the whole designated quote. It
does not require the same chunk IDs between variants. Coverage may span adjacent
selected chunks. Unselected non-whitespace gaps cause a miss. We also use a fixed
4,000-source-character budget: visit results in rank order and include a complete
chunk when it fits the remaining allowance. Unused capacity is reported. This
reduces the advantage of simply returning larger chunks; it does not equate
Gemini tokens or annotate every potentially relevant alternative passage.

## Results

Atlas evidence retrieval, 20 query/anchor pairs:

| Metric | Current | Structure | Structure + heading |
|---|---:|---:|---:|
| Target found in top 3 | 18/20 (90%) | 16/20 (80%) | 17/20 (85%) |
| Target found in top 8 | 20/20 (100%) | 19/20 (95%) | 19/20 (95%) |
| Target found within 4,000 chars | 17/20 (85%) | 15/20 (75%) | 16/20 (80%) |
| Mean source chars in top 3 | 4,839 | 4,601 | 4,666 |
| Mean source chars in top 8 | 12,594 | 12,036 | 12,185 |
| Mean used fixed budget | 3,352 | 3,740 | 3,744 |

Policy search diagnostic, 20 query/anchor pairs:

| Metric | Current | Structure | Structure + heading |
|---|---:|---:|---:|
| Target found in top 3 | 19/20 (95%) | 19/20 (95%) | 20/20 (100%) |
| Target found in top 8 | 20/20 | 20/20 | 20/20 |
| Target found within 4,000 chars | 18/20 (90%) | 19/20 (95%) | 19/20 (95%) |

Across all five files, the current variant produces 49 chunks, while both
structural variants produce 62. The largest source chunk is respectively 1,796
and 1,730 characters; the largest heading-enriched embedding input is 1,793.
Current packing has 42 chunks with an internal heading boundary; structural
packing has zero. Structural boundaries are therefore more consistent with
sections, but this did not improve the primary Atlas retrieval task.

Representative changes at top 3:

- Advance notice of subprocessor changes (`PRI-04`) improves with structure.
- The designated purpose-limitation passage (`PRI-05`) drops out with structure.
- The warning that listed assurance records are not attached (`GOV-02`) drops out
  even at top 8. This is a miss of the designated limitation, not proof that all
  selected alternative passages are irrelevant.
- Adding headings restores the encryption declaration (`SEC-02`) lost by the
  structure-only variant and helps find the policy purpose-limitation clause.

One warm-model indexing pass over all five files took 5.87 / 7.09 / 7.18 seconds.
These are indicative single-run timings, not statistically compared benchmarks.

## Gemini context simulation

The application combines and deduplicates top 8 results for all 20 requirements.
On this corpus, that union includes **every Atlas chunk in every variant**:

| Metric | Current | Structure | Structure + heading |
|---|---:|---:|---:|
| Selected Atlas chunks | 14/14 | 16/16 | 16/16 |
| Selected source chars | 22,051 | 22,046 | 22,046 |
| Planned extraction batches | 2 | 2 | 2 |
| Largest simulated batch input, chars | 23,250 | 23,058 | 23,058 |
| Designated anchors present in union | 20/20 | 20/20 | 20/20 |

The five-character difference comes from boundary whitespace trimming. Simulation
uses the actual analysis instruction, projected requirements, source metadata
shape and `chunk_batches` function. IDs are deterministic experimental IDs.
Counts cover instruction plus serialized input, not the full HTTP envelope,
schema or provider tokenization. Two batches describe initial planned requests,
not retries or measured Gemini usage. No extraction/report quality comparison was
performed. Both variants retain the prompt-injection test appendix in the union;
retrieval is not an authorization or prompt-injection filter.

For this document and 20 requirements, retrieval does not save source-text volume
relative to sending the full document in bounded batches. Chunking remains useful
for provenance, ranking and larger corpora, but those benefits must not be
misreported as measured token savings here.

## Decision and limits

Keep current application chunking pending broader evidence. The hypothesis that
structure alone improves our current counterparty retrieval is not supported by
this experiment, although the policy diagnostic improves with heading context.
The next useful experiment would freeze additional long counterparty documents,
including multi-paragraph dependencies, before comparing retrieval budgets and
bounded neighbor expansion. This result does not establish that character
chunking is generally superior.

This corpus is English Markdown, with one synthetic supplier, largely one
paragraph per source line. Expected anchors were authored by the implementation
agent, not independently reviewed, and do not exhaust all relevant evidence.
No PDF layout, multilingual generalization, production replacement, migration,
reindexing or actual Gemini assessment was tested. Structural parsing is an
experimental heuristic, not a general Markdown parser. All three variants and
all regressions are reported without retuning thresholds after measurement.

## Reproduction and checks

Script: [chunking_comparison.py](../../evaluations/chunking_comparison.py).
Frozen query/anchor pairs: [chunking-results.queries.json](../../evaluations/chunking-results.queries.json).
Full rankings and hashes: [chunking-results.json](../../evaluations/chunking-results.json).

From the repository root with the existing backend image and prepared model cache:

```bash
docker run --rm --network none \
  -v "$PWD:/repo:ro" \
  -v counterparty-risk-analyst_model-cache:/app/model-cache \
  counterparty-risk-analyst-api:local \
  python /repo/evaluations/chunking_comparison.py \
  --cache /app/model-cache --output /tmp/chunking-results.json
```

This command prints metrics; its `/tmp` outputs disappear with the disposable
container. Mount a writable results directory to retain generated JSON files.
Offline execution requires an already populated model cache.

The script checks empty input, oversized lines, paragraph/sentence fallback,
Unicode text, maximum source size, complete non-whitespace source preservation,
unique source anchors and positive/negative coverage cases. The full experiment
passed these checks. Ruff lint and formatting checks passed. Runtime code was
unchanged, so application integration tests were not rerun.
