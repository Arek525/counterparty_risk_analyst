# Local multilingual retrieval — historical experiment

This records the 2026-09-15 implementation and experiment. New semantic-v2 runs
now use hybrid retrieval only; the rankings below describe the historical experiment, not a new comparison
of the current full assessment pipeline.

Verified 2026-09-15 using the actual public model on CPU, with no provider key or
paid API calls. This evaluates retrieval candidates, not compliance, entailment,
legal correctness or multilingual fact extraction. Demo extraction remains English.

## Model and preprocessing contract

The worker uses `intfloat/multilingual-e5-small`, pinned revision
`614241f622f53c4eeff9890bdc4f31cfecc418b3`, ONNX Runtime 1.30.0 CPU, tokenizers 0.23.2
and NumPy 2.5.3. The two official artifacts total 487,351,240 bytes. SHA256 values,
byte counts, prefixes, runtime, dimensions, pooling, windowing, query composition
and scoring versions are defined in `counterparty.embedding_config.CONFIG`.
The SHA256 fingerprint of that canonical JSON is
`800ce15e8c69d74e89ab87bc2965eff571505bbdaf79c8570a8cdacbb60597e3`.

Sources: [pinned model card](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md),
[official ONNX artifacts](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3/onnx).

Each query receives `query: ` and each passage receives `passage: `. Masked mean
pooling includes the non-padding tokens, then L2 normalization produces 384 dimensions.
The actual tokenizer pad ID is 1. Long original source chunks retain their IDs and
are encoded as overlapping complete-token windows (512 tokens including special
and prefix tokens, 64 content-token overlap). Every window repeats the role prefix;
normalized window vectors are averaged and normalized again. No decode/re-encode
or silent tail truncation occurs. This averaging can dilute a small decisive detail;
window-level retrieval would require a separate measured change.

A real parity check exposed a tokenizer subtlety during implementation: encoding
`passage: ` separately produced an extra word-boundary token. The final code strips
only the prefix's trailing whitespace before combining its IDs with separately
encoded content IDs. Exact short-sequence equality with the official combined
string is now checked for both roles, English/Polish, punctuation and leading whitespace.
Intermediate scores from the incorrect preprocessing are debugging evidence only.

## Frozen development comparison

The agent-authored synthetic corpus was fixed before measurements: 24 passages and
12 queries, EN→PL and PL→EN, paraphrases, marketing/training distractors and an injected
instruction. Negated/contradictory operational statements are relevant candidate
evidence. Another agent inspected the fixed labels before scoring; no independent
human label review occurred. Corpus SHA256:
`76ec5a1d9695315b7cb6c4086189c04b500ea3907d7bdf847a633c536c8ac9ec`.

Two query compositions were measured: title alone, and title plus the field name
with underscores replaced by spaces. The table below uses the latter, selected on
this development set. RRF means reciprocal rank fusion; the hybrid sums semantic
rank weight 3 and positive lexical rank weight 1, with denominator `5 + rank`.
Lexical ranking uses Unicode words and log token counts. Equal RRF and the older
sum are comparison candidates only; old-sum retains its historical ASCII lexer.

| Ranking | Recall@3 | Recall@5 | MRR |
|---|---:|---:|---:|
| Lexical |20.8%|37.5%|0.323|
| Semantic cosine, historical selection |66.7%|75.0%|0.756|
| Old lexical +2×positive cosine |25.0%|33.3%|0.380|
| Equal RRF, k60 |29.2%|37.5%|0.421|
| Weighted RRF,3:1,k5 (hybrid) |62.5%|70.8%|0.593|

Semantic title-only scored62.5%/66.7%/0.590. The title+field semantic ranking wins
all three reported metrics against weighted hybrid on this fixed set. This experiment does not establish hybrid superiority. No further
weight tuning followed. The application retrieves up to 8 chunks per requirement;
@3/@5 are diagnostic ranking metrics, not application limits. Full rankings,
cosines and missed gold IDs are in
[results-semantic.json](../evaluations/results-semantic.json).

These labels and measurements informed selection, so this is development
calibration, not held-out validation. Semantic ranking still misses relevant
contradictions and cross-language sources; similarity is not a finding or confidence.

## Reproduction and integration checks

The benchmark runner and frozen inputs are listed in the
[evaluation guide](../evaluations/README.md). Run the benchmark with the backend dependencies and the pinned model cache as
described there. An absent cache requires a public download; no Gemini key is needed.

`real_embedding_check.py` separately checks tokenizer parity, complete long-text
window coverage, offline cache reuse and agreement between direct cosine and
application-scoped pgvector retrieval. It requires a disposable PostgreSQL test
server and model cache; it is not a compliance-quality benchmark.

The ordinary backend suite tests indexing state transitions, stale-claim fencing,
source scoping and immutable retrieval snapshots without downloading weights.
Current end-to-end workflow verification lives in the browser test suite. Historical
model measurements do not substitute for independently reviewed semantic-v2 findings.
