# Local multilingual retrieval

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
| Semantic cosine, **new default** |66.7%|75.0%|0.756|
| Old lexical +2×positive cosine |25.0%|33.3%|0.380|
| Equal RRF, k60 |29.2%|37.5%|0.421|
| Weighted RRF,3:1,k5 (**hybrid option**) |62.5%|70.8%|0.593|

Semantic title-only scored62.5%/66.7%/0.590. The title+field semantic default wins
all three reported metrics against weighted hybrid on this fixed set. The hybrid
option is retained for explicit comparisons, not claimed superior. No further
weight tuning followed. The application retrieves up to 8 chunks per requirement;
@3/@5 are diagnostic ranking metrics, not application limits. Full rankings,
cosines and missed gold IDs are in
[results-semantic.json](../../evaluations/results-semantic.json).

These labels and measurements informed selection, so this is development
calibration, not held-out validation. Semantic ranking still misses relevant
contradictions and cross-language sources; similarity is not a finding or confidence.

## Checks and reproduction

The packaged backend suite passed 121 tests using disposable PostgreSQL, no model
artifact download and no provider calls. A subsequently added negative-cosine
regression passed with the eight focused embedding tests. Focused checks cover partial cache
rejection/offline reuse, token coverage, finite unit vectors, pending/ready/error
transitions, stale-claim fencing, reindex authorization, exact source scope,
write-once database triggers, model-unavailable lexical/no-evidence work and review
resume, persistent child reuse and forced timeout/dead-child recovery. Existing
ownership/checkpointer, decision and ticket tests remain passing.

The separate real check validated 1987 content tokens reconstructed from 5 windows,
actual pad 1, short-input tokenizer parity and offline cache construction with all
HTTP streaming forbidden. Real model → document indexing → application-scoped
pgvector → durable retrieval snapshot matched direct cosine within 1.07e-8.

With an already populated worker cache, the following explicit checks use no
provider credentials. The first command reuses the runtime cache volume; the second
creates and drops only a uniquely named database on the disposable test server.
Replace the Compose-prefixed volume name if using a different project name.
Keep the default container user so it can open the cache lock. The first command
writes its JSON inside the container, redirects the summary to stderr, and lets
the host save the complete JSON at `/tmp/counterparty-retrieval.json`.

```bash
docker compose run --rm --no-deps \
  -v "$PWD/evaluations:/evaluations:ro" worker sh -c '
    python /evaluations/semantic_retrieval.py --cache /app/model-cache \
      --output /tmp/counterparty-retrieval.json >&2 &&
    cat /tmp/counterparty-retrieval.json
  ' > /tmp/counterparty-retrieval.json

docker compose -f compose.test.yaml run --rm \
  -v counterparty-risk-analyst_model-cache:/models tests \
  python /evaluations/real_embedding_check.py --cache /models
```

The real-model script is separate from ordinary pytest. First-run network download,
full-stack resource measurements, browser journey and live migration provenance
are recorded by the integration verification; microbenchmarks below are not substitutes
for those checks.

An isolated process using the final preprocessing loaded its verified OS-warm cache
and model in 2.87 s. Median of 20 warm single-query calls was 6.68 ms, batch size 8,
2 intra-op threads, sequential CPU execution with spinning disabled. The tail probe
used 4 windows: a sanctions sentence appended to unrelated office prose changed cosine
from 0.7936 to 0.8145; the sentence alone scored 0.8783. This demonstrates retention
and dilution, not guaranteed recovery of any tail detail.

At semantic@3 the missing relevant IDs were: q01:p02, q04:p09/p10, q05:p12/p13,
q06:p15/p16, q08:p21. The cross-language misses are a concrete limitation of this
small model/configuration and remain in the unchanged evaluation labels.


## Full-stack cache and resource observations

The corrected runtime independently downloaded the complete 487,351,240 bytes from
an empty cache: preparing→ready 35.86 s. Five documents (four professional policies
plus Atlas evidence), 49 chunks, all reached ready 7.24 s later. An interrupted earlier
development download was discarded before this complete cold-cache measurement.

A 475,500-character synthetic document produced exactly 500 chunks. Upload took 107.4 ms;
index status moved pending→indexing→ready in 33.08 s overall. During indexing, 60 API
case-list requests had median 7.34 ms and p95 10.32ms. These local sequential samples
measure responsiveness under this one indexing task, not load-test capacity.

| Observation during 500-chunk indexing | Measurement |
|---|---:|
| Worker sampled Docker memory maximum |1267.712MiB|
| Worker sampled CPU maximum |198.71% (approximately two cores)|
| API sampled Docker memory maximum |95.61MiB|
| Worker cgroup `memory.peak` |1,855,229,952bytes|

Docker's sampled usage and kernel cgroup peak have different accounting and
sampling; they are not interchangeable RSS measurements. No GPU or paid service
participated in these indexing checks.

A fresh separate container with `--network none`, reusing the cache and with
`httpx.Client.send` forbidden, loaded and validated the model in 8.106 s with zero
HTTP attempts. Its 20 warm queries had median 6.277 ms; process peak RSS was 1,201,968 KiB.
It returned 384-dimensional unit vectors. A small English/Polish smoke pair scored
0.83238 versus 0.74942 for an unrelated passage; this is a smoke check, not another
quality benchmark. The cache constructor verified both artifact SHA256 values.

The old run's immutable input/report, 49 source chunks (IDs/text/locations) and the
human decision matched their pre-migration hashes after migration, reindex and the
large upload. The API process imported neither ONNX Runtime nor tokenizers.

A live worker restart followed by reindexing the same policy reached ready in
4.146 s through pending/preparing/ready, reusing the persistent cache. The final
browser journey passed in 14.2 s against the real stack: default semantic retrieval,
Gemini extraction, the expected 30% completeness and Unable to assess risk, source
viewing, human request for information, separate ticket approval and execution.
The saved run was completed with the final config/fingerprint; two Gemini calls
used 9,939 input and 1,495 output tokens, took 5,162.56 ms, and required zero citation
corrections. Provider cost remains unknown (`null`). This verifies the workflow on
that synthetic case, not general provider quality or billing cost.
