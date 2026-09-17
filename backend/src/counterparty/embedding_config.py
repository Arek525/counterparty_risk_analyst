"""Recorded embedding/retrieval contract; changes invalidate persisted index fingerprints."""

import hashlib
import json

MODEL_ID = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
ARTIFACTS = {
    "model.onnx": {
        "bytes": 470268510,
        "sha256": "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665",
    },
    "tokenizer.json": {
        "bytes": 17082730,
        "sha256": "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
    },
}
CONFIG = {
    "model": MODEL_ID,
    "revision": REVISION,
    "artifacts": ARTIFACTS,
    "dimension": 384,
    "runtime": "onnxruntime-1.30.0-cpu-fp32",
    "tokenizer": "tokenizers-0.23.2",
    "prefixes": {"query": "query: ", "passage": "passage: "},
    "max_tokens": 512,
    "window_overlap": 64,
    "windowing": "complete-content-tokens-repeat-prefix-v2-no-double-boundary",
    "pooling": "masked-mean-l2-then-window-mean-l2",
    "query_composition": "title-field-v1",
    "retrieval": "e5-v1",
    # Historical algorithm descriptions retained for stable fingerprints, not runtime options.
    "algorithms": {
        "semantic": "cosine-v1",
        "hybrid": "weighted-rrf-3-1-k5-v1",
        "lexical": "unicode-log-count-v1",
    },
    "rrf_k": 5,
    "rrf_semantic_weight": 3,
    "rrf_lexical_weight": 1,
    "lexical": "unicode-log-count-v1",
    "top_k": 8,
    "backend": "pgvector-exact",
    "max_chunks": 500,
}
FINGERPRINT = hashlib.sha256(
    json.dumps(CONFIG, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


def requirement_query(requirement):
    return requirement["title"] + " " + requirement["field"].replace("_", " ")
