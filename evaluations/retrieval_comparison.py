"""Development probe: fixed budgets, actual hybrid ranking, bounded amendment hint.

Run once without retuning. Existing long-contract gold and Atlas regression gold
are unchanged. Prefer a simpler method with equivalent coverage; compare query
coverage AND the union supplied to extraction. No Gemini or application writes.
"""

import argparse
import ast
import inspect
import json
import re
import statistics
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np
from adaptive_chunking import anchor_span, covered, source_pages, split_document
from counterparty.analysis.engine import analyze, chunk_batches, retrieve
from counterparty.embedding_config import FINGERPRINT
from counterparty.embeddings import LocalEmbedder
from long_contracts import ROOT, digest

BUDGETS = (4000, 8000, 12000)


def amendment_spans(text):
    # ponytail: short isolated headings, not a general PDF layout parser.
    # The hint never establishes legal precedence; it only selects source text.
    headings = []
    for match in re.finditer(r"\S[\s\S]*?(?=\n[ \t]*\n|\Z)", text):
        title = match[0].strip().lstrip("# ")
        if len(title) <= 120 and not re.search(r"[.!?;]$", title):
            headings.append((match.start(), title))
    return [
        (start, headings[i + 1][0] if i + 1 < len(headings) else len(text))
        for i, (start, title) in enumerate(headings)
        if re.search(
            r"\b(amendment|addendum|rider|variation|change schedule|aneks|protokół)\b",
            title,
            re.IGNORECASE,
        )
    ]


def select_context(ranked, mode, budget, amendments):
    if mode == "top8":
        return ranked[:8]
    priority = []
    if mode == "amendment":
        priority = next(
            (
                [c]
                for c in ranked
                if any(c["start"] < b and c["end"] > a for a, b in amendments)
            ),
            [],
        )
    selected, ids, used = [], set(), 0
    for chunk in [*priority, *ranked]:
        if chunk["id"] not in ids and used + len(chunk["text"]) <= budget:
            selected.append(chunk)
            ids.add(chunk["id"])
            used += len(chunk["text"])
    assert used <= budget
    return selected


def summary(rows):
    return {
        "n": len(rows),
        "hits": sum(r["hit"] for r in rows),
        "rule_only": sum(r["rule_only"] for r in rows),
        "mean_chars": statistics.mean(r["chars"] for r in rows),
    }


def run(output):
    directory = ROOT / "evaluations/long-contracts/corpus"
    corpus = json.loads((directory / "manifest.json").read_text())
    for doc in corpus:
        doc["path"] = directory / doc["file"]
        doc["group"] = "long"
    atlas = ROOT / "datasets/synthetic/evidence/atlas-assurance-pack.md"
    corpus.append(
        {
            "path": atlas,
            "file": atlas.name,
            "sha256": digest(atlas),
            "contract": "atlas",
            "group": "atlas",
            "layout": "markdown",
            "queries": [
                {
                    "id": q["id"],
                    "query": q["query"],
                    "anchors": [q["target"]["quote"]],
                    "cross_reference": False,
                }
                for q in json.loads(
                    (ROOT / "evaluations/chunking-results.queries.json").read_text()
                )["atlas"]
            ],
        }
    )
    for doc in corpus:
        assert digest(doc["path"]) == doc["sha256"]
        text = "\n".join(p for p, _ in source_pages(doc["path"]))
        for query in doc["queries"]:
            for anchor in query["anchors"]:
                anchor_span(text, anchor)
    model = LocalEmbedder("/app/model-cache")
    queries = sorted({q["query"] for doc in corpus for q in doc["queries"]})
    query_vectors = dict(zip(queries, model.embed(queries, "query"), strict=True))
    instruction = next(
        node.value.value
        for node in ast.walk(ast.parse(inspect.getsource(analyze)))
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "instruction" for t in node.targets)
    )
    result = {
        "fingerprint": FINGERPRINT,
        "protocol": "3 unchanged splitters x actual semantic/hybrid ranking x top8/budgets4000,8000,12000/one-amendment-first at those budgets; development comparison, no retuning or automatic deployment",
        "hashes": {
            str(p.relative_to(ROOT)): digest(p)
            for p in (
                Path(__file__),
                directory / "manifest.json",
                ROOT / "evaluations/chunking-results.queries.json",
                ROOT / "evaluations/adaptive_chunking.py",
                ROOT / "evaluations/chunking_comparison.py",
                ROOT / "backend/src/counterparty/analysis/engine.py",
            )
        },
        "source_hashes": {doc["file"]: doc["sha256"] for doc in corpus},
        "preparation": [],
        "methods": {},
    }
    for splitter in ("current", "structure", "semantic"):
        for doc in corpus:
            started = time.monotonic()
            text, chunks = split_document(doc["path"], splitter, model)
            for i, c in enumerate(chunks):
                c["id"] = str(uuid5(NAMESPACE_URL, f"{doc['file']}/{splitter}/{i}"))
            embeddings = np.asarray(model.embed([c["text"] for c in chunks], "passage"))
            result["preparation"].append(
                {
                    "splitter": splitter,
                    "file": doc["file"],
                    "seconds": time.monotonic() - started,
                    "chunks": len(chunks),
                    "amendments": amendment_spans(text),
                }
            )
            targets = {
                q["id"]: [anchor_span(text, a) for a in q["anchors"]]
                for q in doc["queries"]
            }
            scores = {
                q["id"]: dict(
                    zip(
                        (c["id"] for c in chunks),
                        map(float, embeddings @ query_vectors[q["query"]]),
                        strict=True,
                    )
                )
                for q in doc["queries"]
            }
            payload = {
                c["id"]: {
                    "id": c["id"],
                    "document_id": str(uuid5(NAMESPACE_URL, doc["file"])),
                    "text": c["text"],
                    "location": c["location"],
                    "kind": "evidence",
                    "filename": doc["file"],
                    "document_version": 1,
                    "document_sha256": doc["sha256"],
                    "embedding_model": FINGERPRINT,
                    "evidence_type": "declaration",
                }
                for c in chunks
            }
            base = {
                "requirements": [
                    {
                        "id": q["id"],
                        "title": q["query"],
                        "field": "manual",
                        "operator": "manual",
                        "expected": None,
                        "applicability": {},
                    }
                    for q in doc["queries"]
                ]
            }
            for ranking in ("semantic", "hybrid"):
                ranked = {
                    q["id"]: retrieve(
                        q["query"],
                        chunks,
                        ranking,
                        top_k=len(chunks),
                        semantic_scores=scores[q["id"]],
                        algorithm="e5-v1",
                    )
                    for q in doc["queries"]
                }
                for mode, budget in [
                    ("top8", None),
                    *((m, b) for m in ("budget", "amendment") for b in BUDGETS),
                ]:
                    name = f"{splitter}/{ranking}/{mode}/{budget or 8}"
                    method = result["methods"].setdefault(
                        name, {"rows": [], "documents": []}
                    )
                    union = {}
                    for q in doc["queries"]:
                        selected = select_context(
                            ranked[q["id"]], mode, budget, amendment_spans(text)
                        )
                        union.update({c["id"]: c for c in selected})
                        found = [covered(text, selected, a) for a in targets[q["id"]]]
                        method["rows"].append(
                            {
                                "file": doc["file"],
                                "group": doc["group"],
                                "contract": doc["contract"],
                                "id": q["id"],
                                "cross_reference": q["cross_reference"],
                                "hit": all(found),
                                "rule_only": len(found) > 1
                                and found[0]
                                and not all(found[1:]),
                                "chars": sum(len(c["text"]) for c in selected),
                                "selected_ids": [c["id"] for c in selected],
                                "found": found,
                            }
                        )
                    union_chunks = sorted(union.values(), key=lambda c: c["start"])
                    batches = chunk_batches(
                        [payload[c["id"]] for c in union_chunks], base, instruction
                    )
                    method["documents"].append(
                        {
                            "file": doc["file"],
                            "group": doc["group"],
                            "union_hits": sum(
                                all(covered(text, union_chunks, a) for a in t)
                                for t in targets.values()
                            ),
                            "queries": len(targets),
                            "union_chars": sum(len(c["text"]) for c in union_chunks),
                            "batches": len(batches),
                            "serialized_chars": sum(
                                len(instruction)
                                + len(
                                    json.dumps(
                                        {**base, "chunks": b}, ensure_ascii=False
                                    )
                                )
                                for b in batches
                            ),
                        }
                    )
            print(splitter, doc["file"], flush=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for method in result["methods"].values():
        method["groups"] = {
            group: summary([r for r in method["rows"] if r["group"] == group])
            for group in ("long", "atlas")
        }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for name, method in result["methods"].items():
        print(name, method["groups"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
