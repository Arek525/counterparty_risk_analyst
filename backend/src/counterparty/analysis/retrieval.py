"""Ranking of authorized source chunks with local E5 scores or lexical matching."""

import math
import re
from collections import Counter


def unicode_tokens(text):
    return re.findall(r"[^\W_]+", text.casefold().replace("_", " "))


def retrieve(
    query: str,
    chunks: list[dict],
    variant="hybrid",
    top_k=8,
    semantic_scores: dict[str, float] | None = None,
    algorithm="e5-v1",
) -> list[dict]:
    if algorithm != "e5-v1":
        raise ValueError("Runtime retrieval requires the e5-v1 algorithm")
    if variant not in {"lexical", "hybrid", "semantic"}:
        raise ValueError("Unsupported retrieval variant")
    query_tokens = set(unicode_tokens(query))
    lexical = {}
    for chunk in chunks:
        counts = Counter(unicode_tokens(chunk["text"]))
        lexical[str(chunk["id"])] = sum(math.log1p(counts[token]) for token in query_tokens)
    if variant == "lexical":
        scores = lexical
    else:
        ids = {str(chunk["id"]) for chunk in chunks}
        if (
            semantic_scores is None
            or set(semantic_scores) != ids
            or not all(math.isfinite(value) for value in semantic_scores.values())
        ):
            raise ValueError("Runtime hybrid retrieval requires complete finite semantic scores")
        if variant == "semantic":
            scores = semantic_scores
        else:
            scores = dict.fromkeys(ids, 0.0)
            for weight, ranking in (
                (3, semantic_scores),
                (1, {key: value for key, value in lexical.items() if value > 0}),
            ):
                for rank, key in enumerate(
                    sorted(ranking, key=lambda key: (-ranking[key], key)), 1
                ):
                    scores[key] += weight / (5 + rank)
    ranked = sorted(chunks, key=lambda chunk: (-scores[str(chunk["id"])], str(chunk["id"])))
    return (
        ranked[:top_k]
        if variant == "semantic"
        else [chunk for chunk in ranked if scores[str(chunk["id"])] > 0][:top_k]
    )
