"""Explicit real local model evaluation; never run by ordinary pytest."""

import argparse
import hashlib
import json
import math
import re
import statistics
import time
from collections import Counter
from pathlib import Path

from counterparty.analysis.retrieval import retrieve, unicode_tokens
from counterparty.embedding_config import CONFIG, FINGERPRINT, requirement_query
from counterparty.embeddings import LocalEmbedder


def evaluate(corpus, model):
    passages = corpus["passages"]
    vectors = model.embed([p["text"] for p in passages], "passage")
    results = {}
    for composition in ("title-only", "title-field-v1"):
        texts = [
            q["title"] if composition == "title-only" else requirement_query(q)
            for q in corpus["queries"]
        ]
        queries = model.embed(texts, "query")
        for algorithm in (
            "lexical",
            "semantic",
            "old-sum",
            "equal-rrf-k60",
            "weighted-rrf-3-1-k5-v1",
        ):
            records = []
            for query, query_text, vector in zip(
                corpus["queries"], texts, queries, strict=True
            ):
                scores = {
                    p["id"]: sum(a * b for a, b in zip(vector, v, strict=True))
                    for p, v in zip(passages, vectors, strict=True)
                }
                tokenizer = (
                    (lambda text: re.findall(r"[a-z0-9]+", text.lower()))
                    if algorithm == "old-sum"
                    else unicode_tokens
                )
                query_tokens = set(tokenizer(query_text))
                lexical = {}
                for passage in passages:
                    counts = Counter(tokenizer(passage["text"]))
                    lexical[passage["id"]] = sum(
                        math.log1p(counts[t]) for t in query_tokens
                    )
                if algorithm == "lexical":
                    ranking = sorted(
                        (key for key in lexical if lexical[key] > 0),
                        key=lambda key: (-lexical[key], key),
                    )
                elif algorithm == "semantic":
                    ranking = sorted(scores, key=lambda key: (-scores[key], key))
                elif algorithm == "old-sum":
                    combined = {
                        key: value + 2 * max(0, scores[key])
                        for key, value in lexical.items()
                    }
                    ranking = sorted(
                        (key for key in combined if combined[key] > 0),
                        key=lambda key: (-combined[key], key),
                    )
                elif algorithm == "equal-rrf-k60":
                    fused = dict.fromkeys(scores, 0.0)
                    for source in (
                        scores,
                        {key: val for key, val in lexical.items() if val > 0},
                    ):
                        for rank, key in enumerate(
                            sorted(source, key=lambda key: (-source[key], key)), 1
                        ):
                            fused[key] += 1 / (60 + rank)
                    ranking = sorted(fused, key=lambda key: (-fused[key], key))
                else:
                    ranking = [
                        p["id"]
                        for p in retrieve(
                            query_text,
                            passages,
                            top_k=len(passages),
                            semantic_scores=scores,
                        )
                    ]
                gold = set(query["gold"])
                records.append(
                    {
                        "id": query["id"],
                        "ranking": ranking,
                        "recall@3": len(gold & set(ranking[:3])) / len(gold),
                        "recall@5": len(gold & set(ranking[:5])) / len(gold),
                        "mrr": next(
                            (
                                1 / rank
                                for rank, key in enumerate(ranking, 1)
                                if key in gold
                            ),
                            0,
                        ),
                        "missed@3": sorted(gold - set(ranking[:3])),
                        "cosines": scores,
                    }
                )
            results[f"{composition}/{algorithm}"] = {
                metric: statistics.mean(r[metric] for r in records)
                for metric in ("recall@3", "recall@5", "mrr")
            } | {"queries": records}
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(__file__).with_name("multilingual-retrieval.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "output/semantic-retrieval.json",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    model = LocalEmbedder(args.cache)
    startup = time.monotonic() - start
    raw = args.corpus.read_bytes()
    corpus = json.loads(raw)
    results = evaluate(corpus, model)
    timings = []
    for _ in range(20):
        start = time.monotonic()
        model.embed(["Require multi factor authentication for administrators"], "query")
        timings.append((time.monotonic() - start) * 1000)
    # Tail-only content is deliberately beyond 512 tokens. This verifies retention,
    # not an assertion that averaging long passages always retrieves a small detail.
    tail = " We screen suppliers against sanctions lists before signing contracts."
    long_text = "Office furniture and cafeteria arrangements. " * 180 + tail
    windows = model.windows(long_text, "passage")
    assert len(windows) > 2 and len(windows[-1]) <= 512
    assert model.pad_id == 1
    assert all(
        window[1 : 1 + len(model.prefixes["passage"])] == model.prefixes["passage"]
        for window in windows
    )
    query = model.embed(["Screen suppliers for sanctions"], "query")[0]
    values = model.embed(
        [long_text, "Office furniture and cafeteria arrangements. " * 180, tail],
        "passage",
    )
    cosines = [
        sum(a * b for a, b in zip(query, value, strict=True)) for value in values
    ]
    output = {
        "corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "config": CONFIG,
        "fingerprint": FINGERPRINT,
        "startup_seconds": startup,
        "warm_query_median_ms": statistics.median(timings),
        "tail_probe": {
            "windows": len(windows),
            "long_with_tail_cosine": cosines[0],
            "long_without_tail_cosine": cosines[1],
            "tail_only_cosine": cosines[2],
        },
        "results": results,
        "limitations": corpus["purpose"]
        + " This compares candidate ranking, not compliance, entailment, or LLM extraction.",
    }
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                k: {m: v[m] for m in ("recall@3", "recall@5", "mrr")}
                for k, v in results.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
