# Adaptive chunking experiment protocol

Frozen before measurements. User authorized a broader comparison and conditional
implementation of the winning method. Existing Northstar/Atlas results are
development evidence, not an independently reviewed benchmark.

## Scope and hypotheses

Use four synthetic organizations, each with a policy and an evidence document;
two in English and two in Polish. Render identical content in Markdown, continuous
prose, hard-wrapped text, and mixed lists/tables. Add real generated text-PDF
extraction for English documents. Formatting variants are paired stress tests,
not independent samples. Generation templates are shared within each language;
the resulting fixtures do not establish cross-company generalization.

For each document, six queries target an exact rule/declaration AND its exception,
scope or evidence limitation. All required spans must be retrieved. Separately
measure the rate where a rule is found but its qualifier is missing. Preserve
literal source text and use whitespace normalization only in quote comparison.
Freeze generated files and query anchors before embedding or ranking.

Candidates, fixed in advance:

1. Current application's line packing, limit 1800 characters.
2. Structure-aware paragraph/sentence packing from the prior experiment, same limit.
3. Local E5 semantic splitting: sentence units, cosine distance between adjacent
   units; cut at the document's 85th percentile of distances, with a minimum
   absolute distance of 0.12, minimum accumulated length 400, hard maximum 1800.
   Keep a one-sentence lookback only if it fits the hard limit. Paragraphs and
   headings are signals in candidate 2, not requirements for candidate 3.

No threshold search or additional candidate after viewing results. No LLM is
called to choose boundaries. Semantic splitting is inference, not fine-tuning.
All document/query vectors use the pinned E5 model and cosine ranking. Search
each document separately to simulate a single eligible policy/counterparty scope.

## Selection gate

Primary: whole-target hit rate at 4000 source characters, greedily packing ranked
complete chunks that fit. Also report top 3, top 8, rule-without-qualifier rate,
source size, indexing time, chunk count and actual budget consumed.

Organization split before measurement: development (Aster, Orion), confirmation
(Meridian, Brzeg). Select the candidate with highest development primary score;
prefer structure on an exact tie because it requires no additional inference.
Implement only if the selected candidate improves over current by at least
5 percentage points on development AND confirmation, does not lower the score
for either language or document role in confirmation, does not increase the
confirmation rule-without-qualifier rate, and passes source/size/location checks.
Also require no regression in the existing Atlas top-8 anchor coverage, and no
increase above 2x current mean top-8 source size or 5x current preparation time.
If no candidate passes, retain the current implementation and report the failure;
do not manufacture a winner or automatically tune on confirmation data.

## Conditional integration

For a structure winner: integrate the verified splitter for new uploads with
source locations, test oversized text, PDFs and exceptions; existing stored
chunks and historical citations remain immutable. For a semantic winner: model
work belongs in the existing worker, never the API; preserve initial source
availability and prohibit rechunking cited data. No broad migration or deletion
is implied. Run targeted tests first, then backend integration and representative
document/index/analysis checks before rebuilding active services.

Actual Gemini extraction quality requires a separate bounded provider check if
runtime chunking changes. Offline comparison alone is not evidence of Gemini
report quality. If unchanged, do not spend provider quota or rebuild the app.

Evidence artifacts remain local; this request does not repeat the completed
earlier publication or computer-shutdown action.
