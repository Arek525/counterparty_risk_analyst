"""Offline development comparison; no database or Gemini calls.

Run in the existing backend image with this repository mounted at /repo and
the existing model cache mounted at /app/model-cache. See the generated report.
"""

# ruff: noqa: E501 -- Keep literal source anchors readable as complete quotations.

import argparse
import ast
import hashlib
import inspect
import json
import re
import statistics
import time
from itertools import pairwise
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np

from counterparty.analysis.engine import analyze, chunk_batches
from counterparty.documents import CHUNK_CHARS, extract
from counterparty.embedding_config import FINGERPRINT, requirement_query
from counterparty.embeddings import LocalEmbedder

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets/synthetic"
# Frozen before measurement. These identify relevant declarations, not proof of
# compliance. All targets are literal, unique substrings of the source document.
ATLAS_ANCHORS = {
    "SEC-01": "MFA is enabled for every privileged account, including supplier support accounts.",
    "SEC-02": "Encryption at rest is enabled across production storage, replicas, logs and backups containing Northstar data.",
    "SEC-03": "Atlas has assigned the Head of Platform Security as the security owner for this service.",
    "SEC-04": "When duties change or employment ends, the personnel event initiates an access review and removal workflow.",
    "SEC-05": "Platform Security triages each finding using severity, exposure and the affected service function.",
    "SEC-06": "The latest independent assurance report covers the production platform and its established operational controls. It excludes the newly acquired support portal.",
    "PRI-01": "DPA is signed for the assessed service before processing begins.",
    "PRI-02": "Retention period is 21 days after service termination or an authenticated deletion request, excluding documented preservation obligations and technically isolated backup cycles.",
    "PRI-03": "Hosting region is EU for primary storage and processing of the assessed service.",
    "PRI-04": "Assurance Operations routes proposed material changes to the customer contact before they take effect under the agreed schedule.",
    "PRI-05": "The service schedule limits the assessed use to customer operations analytics for Northstar.",
    "PRI-06": "Atlas's operations team can locate an account's service records and support access, correction, removal or export instructions.",
    "GOV-01": "Assurance Operations maintains the contact route and coordinates evidence requests.",
    "GOV-02": "Items in this register are described rather than attached. A reviewer does not have their full content merely because their titles appear here.",
    "GOV-03": "Access approval, session records and the relevant contractual safeguards are available for a Privacy review.",
    "GOV-04": "Atlas completed a service recovery exercise and an exit walkthrough during the stated coverage period.",
    "IR-01": "Incident notification is 12 hours after awareness of a suspected or confirmed incident affecting Northstar data, systems, credentials or service delivery.",
    "IR-02": "The incident workspace records observations, actions and decision times. Relevant operational evidence is isolated through a restricted route with an identified custodian.",
    "IR-03": "Containment and recovery updates describe material changes in impact and unresolved risks.",
    "IR-04": "For confirmed incidents, the closure package includes contributing factors, corrective actions, owners and verification status.",
}


def structured_spans(text):
    """ATX headings, paragraphs, sentences, then hard limit; no overlap.

    ponytail: this experiment supports our Markdown corpus, not arbitrary PDF
    layout, fenced-code parsing or linguistic sentence segmentation.
    """
    headings = list(re.finditer(r"(?m)^#{1,6} .*(?:\n|$)", text))
    boundaries = sorted({0, len(text), *(m.start() for m in headings)})
    for section_start, section_end in pairwise(boundaries):
        section = text[section_start:section_end]
        cuts = [section_start]
        cuts += [section_start + m.end() for m in re.finditer(r"\n[ \t]*\n", section)]
        cuts += [section_end]
        units = []
        for a, b in pairwise(cuts):
            if b - a <= CHUNK_CHARS:
                units.append((a, b))
                continue
            sentence_cuts = (
                [a] + [a + m.end() for m in re.finditer(r"(?<=[.!?])\s+", text[a:b])] + [b]
            )
            for c, d in pairwise(sentence_cuts):
                units.extend((i, min(i + CHUNK_CHARS, d)) for i in range(c, d, CHUNK_CHARS))
        start = end = section_start
        for a, b in units:
            if b - start > CHUNK_CHARS:
                if end > start:
                    yield start, end
                start = a
            end = b
        if end > start:
            yield start, end


def chunks_for(path, variant):
    text = path.read_text()
    if variant == "current":
        chunks, _ = extract(path.read_bytes(), path.name)
        spans, cursor = [], 0
        for chunk in chunks:
            start = text.index(chunk["text"], cursor)
            end = start + len(chunk["text"])
            spans.append((start, end))
            cursor = end
    else:
        spans = list(structured_spans(text))
    chunks, previous = [], 0
    for start, end in spans:
        assert not text[previous:start].strip(), "Source content lost"
        previous = end
        raw = text[start:end]
        start += len(raw) - len(raw.lstrip())
        end -= len(raw) - len(raw.rstrip())
        if end <= start:
            continue
        content = text[start:end]
        assert len(content) <= CHUNK_CHARS
        heading_path = []
        for match in re.finditer(r"(?m)^(#{1,6}) (.+)$", text[:start]):
            level, title = len(match[1]), match[2]
            heading_path = [p for p in heading_path if p[0] < level] + [(level, title)]
        heading = " / ".join(title for _, title in heading_path)
        chunks.append(
            {
                "id": str(uuid5(NAMESPACE_URL, f"{variant}:{path.name}:{start}:{end}")),
                "document_id": str(uuid5(NAMESPACE_URL, path.name)),
                "filename": path.name,
                "text": content,
                "embedding_text": f"{heading}\n{content}"
                if variant == "structure_heading"
                else content,
                "start": start,
                "end": end,
                "location": {
                    "line_start": text.count("\n", 0, start) + 1,
                    "line_end": text.count("\n", 0, end - 1) + 1,
                },
                "kind": "evidence",
                "evidence_type": "declaration",
                "document_version": 1,
                "document_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "embedding_model": FINGERPRINT,
            }
        )
    assert not text[previous:].strip()
    assert sum(len(re.sub(r"\s", "", c["text"])) for c in chunks) == len(re.sub(r"\s", "", text))
    return chunks


def hit(chunks, target, texts):
    text = texts[target["filename"]]
    a = text.index(target["quote"])
    b = a + len(target["quote"])
    spans = sorted((c["start"], c["end"]) for c in chunks if c["filename"] == target["filename"])
    cursor = a
    for start, end in spans:
        if end <= cursor:
            continue
        if start > cursor and text[cursor : min(start, b)].strip():
            return False
        cursor = max(cursor, end)
        if cursor >= b:
            return True
    return False


def evaluate(chunks, vectors, queries, query_vectors, texts):
    records, union = [], {}
    for query, vector in zip(queries, query_vectors, strict=True):
        scores = np.asarray(vectors) @ vector
        order = sorted(range(len(chunks)), key=lambda i: (-float(scores[i]), chunks[i]["id"]))
        ranked = [chunks[i] for i in order]
        budget, used = [], 0
        for c in ranked:
            if used + len(c["text"]) <= 4000:
                budget.append(c)
                used += len(c["text"])
        for c in ranked[:8]:
            union[c["id"]] = c
        records.append(
            {
                "id": query["id"],
                "query": query["query"],
                "target": query["target"],
                "hit@3": hit(ranked[:3], query["target"], texts),
                "hit@8": hit(ranked[:8], query["target"], texts),
                "hit@4000chars": hit(budget, query["target"], texts),
                "top3_chars": sum(len(c["text"]) for c in ranked[:3]),
                "top8_chars": sum(len(c["text"]) for c in ranked[:8]),
                "budget_chars": used,
                "ranking": [
                    {
                        "id": c["id"],
                        "file": c["filename"],
                        "lines": c["location"],
                        "score": round(float(scores[i]), 6),
                    }
                    for c, i in zip(ranked, order, strict=True)
                ],
            }
        )
    metrics = {
        key: statistics.mean(r[key] for r in records)
        for key in ("hit@3", "hit@8", "hit@4000chars", "top3_chars", "top8_chars", "budget_chars")
    }
    metrics["targets"] = len(records)
    return {"metrics": metrics, "queries": records}, list(union.values())


def self_check():
    examples = [
        "",
        "a",
        "a" * 4000,
        "# Heading\n\n" + "Sentence. " * 900,
        "# One\n\nFirst.\n\n## Two\n\nSecond.\n",
        "Żółć i zdania.\n" * 400,
    ]
    for text in examples:
        spans = list(structured_spans(text))
        assert "".join(text[a:b] for a, b in spans) == text
        assert all(0 < b - a <= CHUNK_CHARS for a, b in spans)
    text = "Before. Relevant sentence. After."
    target = {"filename": "test", "quote": "Relevant sentence."}
    assert hit([{"filename": "test", "start": 8, "end": 26}], target, {"test": text})
    assert not hit([{"filename": "test", "start": 8, "end": 16}], target, {"test": text})
    assert hit(
        [{"filename": "test", "start": 8, "end": 17}, {"filename": "test", "start": 17, "end": 26}],
        target,
        {"test": text},
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    self_check()
    manifest = json.loads((DATA / "policy-manifest.json").read_text())
    policies = [DATA / "policies" / name for name in manifest["documents"]]
    evidence = DATA / "evidence/atlas-assurance-pack.md"
    paths = [*policies, evidence]
    texts = {p.name: p.read_text() for p in paths}
    query_sets = {
        "atlas": [
            {
                "id": r["id"],
                "query": requirement_query(r),
                "target": {"filename": evidence.name, "quote": ATLAS_ANCHORS[r["id"]]},
            }
            for r in manifest["requirements"]
        ],
        "policy_diagnostic": [
            {"id": r["id"], "query": requirement_query(r), "target": r["source"]}
            for r in manifest["requirements"]
        ],
    }
    for queries in query_sets.values():
        for q in queries:
            assert texts[q["target"]["filename"]].count(q["target"]["quote"]) == 1, q["id"]
    # Freeze full queries/anchors before model initialization or any ranking.
    args.output.with_suffix(".queries.json").write_text(json.dumps(query_sets, indent=2) + "\n")
    model = LocalEmbedder(args.cache)
    query_vectors = {
        key: model.embed([q["query"] for q in queries], "query")
        for key, queries in query_sets.items()
    }
    instruction = next(
        node.value.value
        for node in ast.walk(ast.parse(inspect.getsource(analyze)))
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "instruction" for t in node.targets)
    )
    projected = [
        {k: r[k] for k in ("id", "title", "field", "operator", "expected", "applicability")}
        for r in manifest["requirements"]
    ]
    report = {
        "fingerprint": FINGERPRINT,
        "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "chunk_limit_chars": CHUNK_CHARS,
        "fixed_retrieval_budget_chars": 4000,
        "limitations": "Development-only, 20 Atlas anchor targets and 20 policy targets. Single English supplier. Anchors are not exhaustive relevance labels or compliance proofs. Policy search is diagnostic, not the runtime policy extraction path. No Gemini calls or Gemini token/cost measurements. Heading context is embedding-only. Timing is one warm-model run per variant. No PDF evaluation.",
        "variants": {},
    }
    for variant in ("current", "structure", "structure_heading"):
        start = time.monotonic()
        all_chunks = [c for path in paths for c in chunks_for(path, variant)]
        vectors = model.embed([c["embedding_text"] for c in all_chunks], "passage")
        result = {
            "index_seconds": round(time.monotonic() - start, 3),
            "chunks": len(all_chunks),
            "max_chars": max(len(c["text"]) for c in all_chunks),
            "max_embedding_chars": max(len(c["embedding_text"]) for c in all_chunks),
            "chunks_crossing_heading": sum(
                any(
                    c["start"] < m.start() < c["end"]
                    for m in re.finditer(r"(?m)^#{1,6} ", texts[c["filename"]])
                )
                for c in all_chunks
            ),
            "documents": {p.name: sum(c["filename"] == p.name for c in all_chunks) for p in paths},
        }
        for key, queries in query_sets.items():
            ids = [
                i
                for i, c in enumerate(all_chunks)
                if (c["filename"] == evidence.name) == (key == "atlas")
            ]
            chunks = [all_chunks[i] for i in ids]
            scores = [vectors[i] for i in ids]
            result[key], selected = evaluate(chunks, scores, queries, query_vectors[key], texts)
            if key == "atlas":
                selected.sort(key=lambda c: c["start"])
                payload_chunks = [
                    {
                        k: c[k]
                        for k in (
                            "id",
                            "document_id",
                            "text",
                            "location",
                            "kind",
                            "filename",
                            "document_version",
                            "document_sha256",
                            "embedding_model",
                            "evidence_type",
                        )
                    }
                    for c in selected
                ]
                batches = chunk_batches(payload_chunks, {"requirements": projected}, instruction)
                result["gemini_context_estimate"] = {
                    "selected_chunks": len(selected),
                    "source_chars": sum(len(c["text"]) for c in selected),
                    "batches": len(batches),
                    "max_batch_input_chars": max(
                        len(instruction)
                        + len(
                            json.dumps({"requirements": projected, "chunks": b}, ensure_ascii=False)
                        )
                        for b in batches
                    ),
                    "anchor_coverage": sum(hit(selected, q["target"], texts) for q in queries)
                    / len(queries),
                }
        report["variants"][variant] = result
        print(
            variant,
            json.dumps({k: v for k, v in result.items() if k not in query_sets}),
            flush=True,
        )
        print({k: result[k]["metrics"] for k in query_sets}, flush=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
