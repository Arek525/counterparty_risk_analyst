"""Shared fixtures for historical analysis regression tests; no CLI or provider runner."""

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from counterparty.documents import extract

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "datasets" / "synthetic"
GOLD = json.loads((Path(__file__).parent / "fixtures" / "northstar-gold.json").read_text())
RELATIONSHIP = {
    "personal_data": True,
    "privileged_access": True,
    "business_criticality": "high",
    "purpose": "Hosted customer operations analytics",
    "data_shared": "Synthetic customer contact and usage data",
    "system_access": "Privileged support access to the analytics administration console",
}


def document_chunks(path: Path, kind: str) -> list[dict]:
    raw = path.read_bytes()
    chunks, _ = extract(raw, path.name)
    digest = hashlib.sha256(raw).hexdigest()
    document_id = str(uuid5(NAMESPACE_URL, f"{path.name}:{digest}"))
    return [
        {
            **chunk,
            "id": str(uuid5(NAMESPACE_URL, f"{document_id}:{index}")),
            "document_id": document_id,
            "filename": path.name,
            "kind": kind,
            "evidence_type": "declaration",
            "document_sha256": digest,
            "document_version": 1,
        }
        for index, chunk in enumerate(chunks)
    ]


def resolve_manifest(manifest: dict, chunks: list[dict]) -> list[dict]:
    """Resolve curated literal citations; ambiguous edits fail the entire transaction."""
    from counterparty.analysis import validate_requirements
    from counterparty.analysis.sources import source

    requirements = []
    for entry in manifest["requirements"]:
        citation = entry["source"]
        matches = [
            chunk
            for chunk in chunks
            if chunk.get("filename") == citation["filename"] and citation["quote"] in chunk["text"]
        ]
        if len(matches) != 1 or matches[0]["text"].count(citation["quote"]) != 1:
            raise ValueError(f"Curated citation must resolve exactly once: {entry['id']}")
        requirements.append({**entry, "source": source(matches[0], citation["quote"])})
    return validate_requirements(requirements, chunks)


def corpus(mode="demo"):
    manifest = GOLD["legacy_manifest"]
    policies = [
        chunk
        for name in manifest["documents"]
        for chunk in document_chunks(FIXTURES / "policies" / name, "policy")
    ]
    requirements = resolve_manifest(manifest, policies)
    evidence = document_chunks(FIXTURES / "evidence" / "atlas-assurance-pack.md", "evidence")
    snapshot = {
        "case": {
            "name": "Atlas development acceptance",
            "relationship": RELATIONSHIP.copy(),
        },
        "policy": {"name": manifest["name"], "version": 1},
        "requirements": requirements,
        "chunks": evidence,
        "model_mode": mode,
    }
    return policies, snapshot


def proposal_coverage(proposed, curated):
    """Match by supplier-clause citation, never require model-invented manual IDs/field names.

    Exact semantic rule fields are separately reported. Quote containment locates a
    candidate; it is not independent proof that a shortened quote entails the whole rule.
    """
    matches, extras = {r["id"]: [] for r in curated}, []
    for req in proposed:
        source = req["source"]
        candidates = [
            r
            for r in curated
            if source["document_id"] == r["source"]["document_id"]
            and source["chunk_id"] == r["source"]["chunk_id"]
            and (source["quote"] in r["source"]["quote"] or r["source"]["quote"] in source["quote"])
        ]
        if len(candidates) == 1:
            matches[candidates[0]["id"]].append(req)
        else:
            extras.append(req["id"])
    rules = []
    for gold in curated:
        found = matches[gold["id"]]
        if len(found) != 1:
            continue
        keys = [
            "operator",
            "expected",
            "severity",
            "applicability",
            "evaluation_method",
        ]
        if gold["evaluation_method"] == "deterministic":
            keys.append("field")
        differences = {key: found[0][key] for key in keys if found[0][key] != gold[key]}
        if differences:
            rules.append({"id": gold["id"], "differences": differences})
    return {
        "matched_once": sum(len(items) == 1 for items in matches.values()),
        "missing": [key for key, items in matches.items() if not items],
        "duplicates": [key for key, items in matches.items() if len(items) > 1],
        "extra_or_internal": extras,
        "rule_mismatches": rules,
        "manual_field_names": {
            key: items[0]["field"]
            for key, items in matches.items()
            if len(items) == 1 and items[0]["evaluation_method"] == "manual"
        },
    }


def fact_coverage(report):
    expected = GOLD["atlas"]["facts"]
    observed = {}
    for fact in report["facts"]:
        observed.setdefault(fact["field"], []).append(fact["value"])
    return {
        "missing": [field for field in expected if field not in observed],
        "cardinality": {
            field: len(values) for field, values in observed.items() if len(values) != 1
        },
        "incorrect": {
            field: values
            for field, values in observed.items()
            if field not in expected
            or any(
                value != expected[field]
                or isinstance(value, bool) != isinstance(expected[field], bool)
                for value in values
            )
        },
    }
