"""Frozen long-contract diagnostic. Offline only; reuse unchanged candidate splitters."""

import argparse
import ast
import hashlib
import inspect
import io
import json
import re
import textwrap
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np
from adaptive_chunking import (
    anchor_span,
    covered,
    source_pages,
    split_document,
    summarize,
    text_pdf,
)
from counterparty.analysis.adapters import ModelError
from counterparty.analysis.engine import analyze, chunk_batches, policy_batches
from counterparty.embedding_config import FINGERPRINT
from counterparty.embeddings import LocalEmbedder
from pypdf import PdfWriter
from pypdf.generic import NameObject

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evaluations/long-contracts"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contract_pdf(text):
    # Explicit encoding keeps apostrophes identical to the authored source.
    writer = PdfWriter(clone_from=io.BytesIO(text_pdf(text)))
    for page in writer.pages:
        page["/Resources"]["/Font"]["/F1"][NameObject("/Encoding")] = NameObject(
            "/WinAnsiEncoding"
        )
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def freeze(directory):
    directory.mkdir(parents=True, exist_ok=True)
    assert not list(directory.iterdir()), "Refusing to replace frozen corpus"
    annexes = "\n\n".join(
        f"# Incorporated annex {i}\n\n{p.read_text()}"
        for i, p in enumerate(
            sorted((ROOT / "datasets/synthetic/policies").glob("*.md")), 1
        )
    )
    manifest = []
    for company, questions in json.loads(
        (FIXTURES / "queries.json").read_text()
    ).items():
        core = (FIXTURES / f"{company}.md").read_text()
        assert core.count("<!-- ANNEXES -->") == 1
        value = core.replace("<!-- ANNEXES -->", annexes)
        assert len(value) >= 30000
        for layout in ("markdown", "wrapped" if company == "warta" else "pdf"):
            rendered = value
            if layout != "markdown":
                rendered = re.sub(r"(?m)^#{1,6} ", "", rendered)
                rendered = "\n\n".join(
                    textwrap.fill(
                        p, width=74, break_long_words=False, break_on_hyphens=False
                    )
                    for p in rendered.split("\n\n")
                )
            if layout == "pdf":
                rendered = rendered.translate(
                    str.maketrans(
                        {"–": "-", "—": "-", "’": "'", "“": '"', "”": '"', "→": "->"}
                    )
                )
            suffix = {"markdown": "md", "pdf": "pdf", "wrapped": "txt"}[layout]
            path = directory / f"{company}.{suffix}"
            path.write_bytes(
                contract_pdf(rendered) if layout == "pdf" else rendered.encode()
            )
            pages = source_pages(path)
            text = "\n".join(p for p, _ in pages)
            queries = [
                {"id": q[0], "cross_reference": q[1], "query": q[2], "anchors": q[3:]}
                for q in questions
            ]
            for query in queries:
                for quote in query["anchors"]:
                    anchor_span(text, quote)
            manifest.append(
                {
                    "file": path.name,
                    "contract": company,
                    "layout": layout,
                    "sha256": digest(path),
                    "source_chars": len(text),
                    "words": len(text.split()),
                    "pdf_pages": len(pages) if layout == "pdf" else None,
                    "shared_annex_fraction_canonical": len(annexes) / len(value),
                    "queries": queries,
                }
            )
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            [{k: v for k, v in d.items() if k != "queries"} for d in manifest], indent=2
        )
    )


def measure(directory, output):
    corpus = json.loads((directory / "manifest.json").read_text())
    for doc in corpus:
        assert digest(directory / doc["file"]) == doc["sha256"]
        text = "\n".join(p for p, _ in source_pages(directory / doc["file"]))
        for query in doc["queries"]:
            for quote in query["anchors"]:
                anchor_span(text, quote)
    model = LocalEmbedder("/app/model-cache")
    queries = sorted({q["query"] for doc in corpus for q in doc["queries"]})
    vectors = dict(zip(queries, model.embed(queries, "query"), strict=True))
    instruction = next(
        node.value.value
        for node in ast.walk(ast.parse(inspect.getsource(analyze)))
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "instruction" for t in node.targets)
    )
    result = {
        "fingerprint": FINGERPRINT,
        "hashes": {
            str(p.relative_to(ROOT)): digest(p)
            for p in (
                Path(__file__),
                FIXTURES / "protocol.md",
                FIXTURES / "queries.json",
                ROOT / "evaluations/adaptive_chunking.py",
                ROOT / "evaluations/chunking_comparison.py",
            )
        },
        "manifest_sha256": digest(directory / "manifest.json"),
        "variants": {},
    }
    for variant in ("current", "structure", "semantic"):
        records, documents = [], []
        for doc in corpus:
            started = time.monotonic()
            text, chunks = split_document(directory / doc["file"], variant, model)
            values = np.asarray(model.embed([c["text"] for c in chunks], "passage"))
            seconds = time.monotonic() - started
            union = set()
            for query in doc["queries"]:
                targets = [anchor_span(text, quote) for quote in query["anchors"]]
                scores = values @ vectors[query["query"]]
                order = sorted(
                    range(len(chunks)),
                    key=lambda i: (-float(scores[i]), chunks[i]["start"]),
                )
                ranked = [chunks[i] for i in order]
                union.update(order[:8])
                selected, used = [], 0
                for chunk in ranked:
                    if used + len(chunk["text"]) <= 4000:
                        selected.append(chunk)
                        used += len(chunk["text"])
                found = [covered(text, selected, target) for target in targets]
                records.append(
                    {
                        **{k: doc[k] for k in ("file", "contract", "layout")},
                        "id": query["id"],
                        "cross_reference": query["cross_reference"],
                        "hit@3": all(covered(text, ranked[:3], t) for t in targets),
                        "hit@8": all(covered(text, ranked[:8], t) for t in targets),
                        "hit@4000": all(found),
                        "rule_without_qualifier": found[0] and not found[1],
                        "budget_chars": used,
                        "top8_chars": sum(len(c["text"]) for c in ranked[:8]),
                        "anchor_distance_chars": targets[1][0] - targets[0][1],
                        "anchors_found_under_budget": found,
                        "anchors_covered_at_rank": [
                            next(
                                n
                                for n in range(1, len(ranked) + 1)
                                if covered(text, ranked[:n], t)
                            )
                            for t in targets
                        ],
                        "ranking": [c["location"] for c in ranked],
                    }
                )
            payload = [
                {
                    "id": str(uuid5(NAMESPACE_URL, f"{doc['file']}/{variant}/{i}")),
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
                for i, c in enumerate(chunks)
            ]
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
            selected = [payload[i] for i in sorted(union)]
            batches = chunk_batches(selected, base, instruction)
            try:
                policy_probe = {
                    "batches": len(
                        policy_batches([{**c, "kind": "policy"} for c in payload])
                    )
                }
            except ModelError as error:
                policy_probe = {"error": str(error)}
            documents.append(
                {
                    "file": doc["file"],
                    "chunks": len(chunks),
                    "seconds": seconds,
                    "max_chunk_chars": max(len(c["text"]) for c in chunks),
                    "embedded_chars": sum(len(c["text"]) for c in chunks),
                    "selected_union_chunks": len(selected),
                    "selected_union_chars": sum(len(c["text"]) for c in selected),
                    "fact_batches": len(batches),
                    "batch_input_chars": [
                        len(instruction)
                        + len(json.dumps({**base, "chunks": b}, ensure_ascii=False))
                        for b in batches
                    ],
                    "policy_probe": policy_probe,
                }
            )
            print(variant, doc["file"], round(seconds, 2), flush=True)
        groups = {
            f"{field}/{value}": summarize([r for r in records if r[field] == value])
            for field in ("contract", "layout", "file", "cross_reference")
            for value in sorted({r[field] for r in records})
        }
        result["variants"][variant] = {
            "all": summarize(records),
            "groups": groups,
            "documents": documents,
            "rows": records,
        }
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(variant, json.dumps(summarize(records)), flush=True)
    baseline = result["variants"]["current"]
    result["gates"] = {}
    for name in ("structure", "semantic"):
        candidate = result["variants"][name]
        failures = []
        if candidate["all"]["hit@4000"] - baseline["all"]["hit@4000"] < 0.05 - 1e-9:
            failures.append("Less than 5 percentage points gain")
        for group, score in candidate["groups"].items():
            if (
                group.startswith(("contract/", "file/"))
                and score["hit@4000"] < baseline["groups"][group]["hit@4000"]
            ):
                failures.append(f"Regression in {group}")
        if (
            candidate["all"]["rule_without_qualifier"]
            > baseline["all"]["rule_without_qualifier"]
        ):
            failures.append("More rule-only selections")
        if candidate["all"]["top8_chars"] > 2 * baseline["all"]["top8_chars"]:
            failures.append("Context exceeds 2x baseline")
        if sum(d["seconds"] for d in candidate["documents"]) > 5 * sum(
            d["seconds"] for d in baseline["documents"]
        ):
            failures.append("Preparation exceeds 5x baseline")
        result["gates"][name] = {"pass": not failures, "failures": failures}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["gates"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("freeze", "measure"))
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.corpus)
    else:
        assert args.output is not None
        measure(args.corpus, args.output)
