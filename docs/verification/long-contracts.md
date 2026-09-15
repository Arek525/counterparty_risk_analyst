# Long-contract chunking comparison

Semantic splitting earns further budget-aware retrieval validation, but does not
justify an isolated runtime splitter replacement. Its fixed-budget context score
improves substantially while its top-8 score regresses. Production is unchanged.

## Results and recommendation

| Measure | Current | Structure | Semantic + lookback |
|---|---:|---:|---:|
| Both anchors, 4,000 source chars | 22/36 (61.1%) | 22/36 (61.1%) | 28/36 (77.8%) |
| Both anchors, top 3 | 26/36 | 24/36 | 27/36 |
| Both anchors, top 8 | 35/36 | 35/36 | 32/36 |
| Rule without qualifier, 4,000 chars | 5/36 | 6/36 | 3/36 |
| Local qualifications, 4,000 chars | 16/20 | 16/20 | 18/20 |
| Distant amendment pairs, 4,000 chars | 6/16 | 6/16 | 10/16 |
| Distant amendment pairs, top 8 | 15/16 | 15/16 | 12/16 |
| Mean source chars, top 8 | 11,364 | 10,249 | 8,239 |
| Chunks across six presentations | 265 | 327 | 490 |
| Split + embedding seconds | 35.24 | 43.44 | 103.96 |
| Maximum chunk chars | 1,798 | 1,800 | 1,798 |

Full-context coverage at 4,000 characters by contract and format:

| Group | Current | Structure | Semantic + lookback |
|---|---:|---:|---:|
| Cedar | 5/12 | 4/12 | 7/12 |
| Lumen | 9/12 | 10/12 | 12/12 |
| Warta | 8/12 | 8/12 | 9/12 |
| Markdown | 13/18 | 13/18 | 13/18 |
| PDF | 5/12 | 5/12 | 10/12 |
| Wrapped TXT | 4/6 | 4/6 | 5/6 |

Semantic passes the frozen preliminary gate: +16.7 percentage points under the
fixed budget, no per-file/per-contract regression on that metric, fewer rule-only
selections and 2.95x preparation time. Structural fails: no aggregate gain,
Cedar/PDF regressions and more rule-only selections. Passing the gate is not an
instruction to deploy: the protocol explicitly requires further staged validation.

The top-8 regression is material because runtime selects top 8 per requirement
before taking their union. More, smaller chunks are not equivalent to the same
number of larger chunks. Cedar's overseas-support baseline/amendment are covered
at ranks 4/9 in the current PDF, and 12/10 in the semantic PDF. Warta's exit pair
needs rank 9 with semantic splitting in both layouts. A neighboring sentence
cannot bridge an amendment tens of thousands of characters away. These are
per-query diagnostics; the multi-requirement union can recover text selected by
another query, so these failures are not measured final report errors.

The next justified increment is a frozen comparison of retrieval by text/token
budget, hybrid ranking and explicit amendment/section context, followed by real
requirement extraction and fact-quality evaluation. Include current chunking as
a control so retrieval gains are not incorrectly attributed to the splitter.
More independently authored and reviewed documents are needed before generalizing
beyond these shared-annex fixtures. No such implementation occurred here.

## Actual batch-planner diagnostics

| Presentation | Current union chars / fact batches | Structure | Semantic |
|---|---:|---:|---:|
| Cedar MD | 19,516 / 2 | 21,230 / 2 | 18,010 / 2 |
| Cedar PDF | 18,400 / 2 | 17,657 / 2 | 15,402 / 2 |
| Lumen MD | 20,731 / 2 | 16,178 / 1 | 15,551 / 2 |
| Lumen PDF | 14,009 / 1 | 14,554 / 1 | 14,574 / 1 |
| Warta MD | 12,577 / 1 | 11,490 / 1 | 11,531 / 1 |
| Warta TXT | 14,233 / 1 | 12,558 / 1 | 11,505 / 1 |

Six questions together select approximately 11.5–21.2 thousand source characters
from each approximately 63-thousand-character document. Fact-planner requests
remain bounded at 25,000 serialized input characters including instructions and
metadata. Smaller source text does not always mean fewer batches, because every
chunk carries metadata and every batch repeats instructions/requirements.

When the same full documents are treated as **company policies for requirement
proposal**, Markdown planning succeeds with five batches for current/structure
and six for semantic. Both PDFs and wrapped TXT fail for every candidate with:

> Policy split lacks explicit section context; split the document by section

This is an existing planner limitation: it requires recognized Markdown section
context when a policy needs another batch. Upload/extraction/indexing and policy
proposal are different stages. These documents do not show that arbitrary long
uploaded policies already work end to end. A splitter swap does not fix this
context requirement; addressing it deserves a separate bounded increment.

## Verification

Six targeted tests pass, including the PDF punctuation/page-boundary regression.
Ruff lint and formatting pass. All six current candidate renditions were separately
compared against actual `documents.extract` on their original files: chunk texts
match exactly. The completed measurement validates all document hashes, unique
gold anchors, full non-whitespace source preservation and 1,800-character bounds.
All recorded fact batches fit the existing planner bounds. Artifact hashes were
checked again after copying results into the repository. No application code was
changed, and application integration/LLM tests were not run for this experiment.

## Scope and reproducibility

Offline diagnostic measured on 2026-09-15. No Gemini requests, database writes,
runtime changes or reindexing. The container had networking disabled and used
the application's cached, pinned multilingual E5 model. This is a source-retrieval
experiment, not a measured compliance decision or legal interpretation benchmark.

Three authored synthetic service agreements incorporate the four existing
Northstar standards, followed by signed amendments: Cedar payroll, Lumen fleet
analytics, and Warta document archiving. Each contains 62–64 thousand characters
and approximately 8.4–8.9 thousand words. English PDF renditions each have 27 pages;
Warta has a wrapped TXT rendition alongside Markdown. Shared annexes constitute
79.5–81.5% of each canonical agreement. These are three contracts with six
presentations, not six independent company styles. The bilingual Warta document
has Polish operating terms and English incorporated annexes.

Eighteen questions, six per agreement, give 36 paired presentation observations.
Each has two literal gold anchors frozen before ranking. Sixteen observations
require combining a main provision with a distant amendment. The remaining
twenty concern local scope/exceptions. Requiring both baseline and amendment is
a strict context diagnostic: a self-contained amendment could suffice for a
particular answer, so this metric must not be called answer accuracy. No human
independent gold review was performed. Scans, OCR and complex PDF layouts are
outside this experiment. PDF pages preserve ordinary text, paragraphs and line
wrapping; visual headings do not contain Markdown hash markers.

The unchanged candidates are current line/character packing, structural
heading/paragraph/sentence packing, and adjacent-sentence E5 topic boundaries
with one-sentence lookback. All retain source text and locations with a hard
1,800-character ceiling. The semantic candidate's overlap is counted in its
embedding and retrieval volume. There is no parameter tuning after scoring.

Ranking uses cosine similarity within each eligible document. The application
also supports lexical/hybrid retrieval; these scores isolate its semantic
component and do not evaluate default hybrid retrieval end to end. We report
complete anchor coverage in top 3, top 8 and a fixed 4,000-source-character budget.
The latter greedily includes whole chunks in rank order when they fit; it is a
controlled comparison budget, not the application's request limit.

For each document, the union of top 8 across its six questions is deduplicated,
source-ordered and passed to the actual `chunk_batches` planner with source
metadata and six projected diagnostic requirements. Serialized input includes
the existing fact instruction. This estimates batch planning for those questions;
it does not measure Gemini tokens, billing, extraction or approved-policy coverage.
The actual `policy_batches` planner is probed separately on the entire document.

The predeclared recommendation gate requires at least five percentage points
more complete context under the fixed budget, no per-contract or per-file
regression, no increase in rule-without-qualifier failures, preserved source and
chunk bounds, at most five times preparation latency and twice mean top-8 text.
Timings are single warm-model passes in fixed candidate order, excluding shared
query embeddings and startup; they are approximate, not controlled performance
measurements. Even a pass requires subsequent application-level validation.

## Artifacts

- [Frozen protocol](../../evaluations/long-contracts/protocol.md)
- [Authored questions and gold](../../evaluations/long-contracts/queries.json)
- [Full documents and manifest](../../evaluations/long-contracts/corpus/manifest.json)
- [Generator and runner](../../evaluations/long_contracts.py)
- [Results](../../evaluations/long-contracts/results.json)
- [PDF encoding guard](../../evaluations/test_long_contracts.py)

With the existing image and model cache, run from the repository root:

```bash
docker run --rm --network none \
  -v "$PWD:/repo:ro" \
  -v counterparty-risk-analyst_model-cache:/app/model-cache \
  counterparty-risk-analyst-api:local \
  python /repo/evaluations/long_contracts.py measure \
  --corpus /repo/evaluations/long-contracts/corpus --output /tmp/results.json
```

Metrics print to the terminal; mount a writable directory and change `--output`
to retain JSON outside the disposable container. The results record hashes of
the runner, both reused candidate helpers, protocol, gold and corpus manifest;
individual documents are hash-checked before measurement. Generation stopped
before ranking when the PDF font's implicit encoding changed ASCII apostrophes
to curly apostrophes. An explicit WinAnsi font encoding fixed that presentation
defect; a new two-page regression test verifies exact punctuation. Gold wording
and chunk candidates were not changed to accommodate scores.
