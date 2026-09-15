# Long-contract comparison v1

Freeze documents and gold anchors before measuring. Three separately authored
synthetic service schedules plus amendments incorporate the four existing
Northstar standards as shared contractual annexes. These are original project
fixtures, not real legal instruments or independent external-company documents.
No repeated filler is added to reach length. Report actual words, characters,
generated PDF pages and shared-annex proportion. Reject fixtures under 30,000
characters. Render two presentations per contract: Markdown plus actual text PDF
for English; Markdown plus hard-wrapped TXT for Polish. Six presentations remain
three contracts, not six independent agreements.

Questions target service-specific conditions, not generic annex defaults. Each
requires two designated literal anchors, including overrides, exclusions,
definitions or dependencies. Some qualifiers are in a final amendment separated
from the main provision by all four annexes. Label those cross-reference cases
before scoring and report them separately from local qualifications.

Methods are the unchanged current, structure and semantic-with-lookback candidates
from adaptive_chunking.py: 1800 source chars, semantic adjacent sentence distance
85th percentile with 0.12 floor, minimum 400, one sentence lookback when it fits.
No retuning or new candidate after results. Use real pinned local E5, cosine
ranking, top 3/top 8 and greedily packed 4000-character source budget. Primary
score requires all anchors. Count rule-without-qualifier failures separately.
Measure full source preservation, split+embedding latency, source/context length,
and union of top 8 across all contract questions. Reuse actual chunk_batches to
simulate extraction payload sizes and count batches; no Gemini calls or token
cost claims. Probe policy_batches separately to establish whether the application's
policy-proposal path accepts each presentation; rejection is a reported product
limitation, not an exception to hide.

Recommendation gate: at least 5 percentage points primary gain over current,
no contract-level or presentation-level regression, no increase in rule-only
failures, source/size guards pass, <=5x preparation time and <=2x mean top-8 source
chars. Prefer structure on a tie. With only three contracts and shared annexes,
even passing is a reason for staged validation, not proof of universal quality.
No implementation or database mutation in this requested comparison/report.
The previous small-corpus artifacts and criteria remain unchanged.
