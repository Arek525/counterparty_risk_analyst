"""Hybrid ranking of authorized chunks using E5 cosine scores and lexical matches."""

import math
import re
from collections import Counter


def unicode_tokens(text):
    return re.findall(r"[^\W_]+", text.casefold().replace("_", " "))


def retrieve(
    query: str,
    chunks: list[dict],
    *,
    semantic_scores: dict[str, float],
    top_k=8,
) -> list[dict]:
    ids = {str(chunk["id"]) for chunk in chunks}
    if (
        semantic_scores is None
        or set(semantic_scores) != ids
        or not all(math.isfinite(value) for value in semantic_scores.values())
    ):
        raise ValueError("Hybrid retrieval requires complete finite semantic scores")
    query_tokens = set(unicode_tokens(query))
    lexical = {}
    for chunk in chunks:
        counts = Counter(unicode_tokens(chunk["text"]))
        lexical[str(chunk["id"])] = sum(math.log1p(counts[token]) for token in query_tokens)
    scores = dict.fromkeys(ids, 0.0)
    for weight, ranking in (
        (3, semantic_scores),
        (1, {key: value for key, value in lexical.items() if value > 0}),
    ):
        for rank, key in enumerate(sorted(ranking, key=lambda key: (-ranking[key], key)), 1):
            scores[key] += weight / (5 + rank)
    return sorted(chunks, key=lambda chunk: (-scores[str(chunk["id"])], str(chunk["id"])))[:top_k]
