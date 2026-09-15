"""Offline acceptance or explicit bounded Gemini probe for the Northstar development corpus.

PYTHONPATH=backend/src python evaluations/northstar.py --mode demo
PYTHONPATH=backend/src python evaluations/northstar.py --mode gemini --output /tmp/probe.json
No database, storage mutation or automatic fallback. Credentials come only from environment.
"""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from counterparty.analysis import analyze, propose_requirements
from counterparty.analysis.adapters import ModelError
from counterparty.analysis.engine import policy_batches
from counterparty.analysis.schemas import validate_source
from counterparty.bootstrap import resolve_manifest
from counterparty.documents import extract

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "datasets" / "synthetic"
GOLD = json.loads((Path(__file__).parent / "northstar-gold-v1.json").read_text())
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


def corpus(mode="demo"):
    manifest = json.loads((FIXTURES / "policy-manifest.json").read_text())
    policies = [
        chunk
        for name in manifest["documents"]
        for chunk in document_chunks(FIXTURES / "policies" / name, "policy")
    ]
    requirements = resolve_manifest(manifest, policies)
    evidence = document_chunks(FIXTURES / "evidence" / "atlas-assurance-pack.md", "evidence")
    snapshot = {
        "case": {"name": "Atlas development acceptance", "relationship": RELATIONSHIP.copy()},
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
        keys = ["operator", "expected", "severity", "applicability", "evaluation_method"]
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


def evaluate(mode):
    policies, snapshot = corpus(mode)
    result = {
        "dataset_role": GOLD["dataset_role"],
        "mode": mode,
        "policy_chunks": len(policies),
        "policy_input_chars_unbatched": len(json.dumps({"chunks": policies}, ensure_ascii=False)),
        "planned_policy_batches": [len(payload["chunks"]) for payload in policy_batches(policies)],
        "policy_metrics": {},
        "source_hashes": {
            c["filename"]: c["document_sha256"] for c in policies + snapshot["chunks"]
        },
    }
    try:
        if mode == "gemini":
            proposed = propose_requirements(policies, mode, result["policy_metrics"])
        else:
            # Offline seed acceptance does not pretend demo regex is a policy-quality model.
            proposed = snapshot["requirements"]
        result["proposal"] = proposal_coverage(proposed, snapshot["requirements"])
        result["proposed_requirements"] = proposed
        report = analyze(snapshot)
        result["report"] = report
        for fact in report["facts"]:
            validate_source(fact["source"], snapshot["chunks"])
        result["fact_coverage"] = fact_coverage(report)
        actual = {f["requirement_id"]: f["status"] for f in report["findings"]}
        result["atlas_matches_gold"] = (
            not any(result["fact_coverage"].values())
            and report["risk"] == GOLD["atlas"]["risk"]
            and report["completeness"] == GOLD["atlas"]["completeness"]
            and all(
                actual[r["id"]] == ("pass" if r["id"] in GOLD["atlas"]["passes"] else "unknown")
                for r in snapshot["requirements"]
            )
            and [d["type"] for d in report["discrepancies"]] == GOLD["atlas"]["discrepancies"]
        )
    except (ModelError, ValueError) as exc:
        # Adapter errors are sanitized; never include response bodies or request headers.
        result["error"] = str(exc)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["demo", "gemini"], default="demo")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.mode)
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output)
    proposal = result.get("proposal", {})
    passed = (
        "error" not in result
        and result.get("atlas_matches_gold")
        and proposal.get("matched_once") == len(GOLD["controls"])
        and not any(
            proposal.get(key)
            for key in ("missing", "duplicates", "extra_or_internal", "rule_mismatches")
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
