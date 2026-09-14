"""Run: PYTHONPATH=backend/src python evaluations/run.py [--mode gemini]."""

import argparse
import json
import os
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

from counterparty.analysis import analyze
from counterparty.analysis.adapters import ModelError
from counterparty.analysis.engine import retrieve

ROOT = Path(__file__).resolve().parent


def build_snapshot(case, mode):
    requirements = []
    for index, item in enumerate(case["requirements"]):
        requirements.append(
            {
                "id": f"r{index}",
                "title": item["field"],
                "applicability": {},
                "evaluation_method": "deterministic",
                **item,
            }
        )
    chunks = [
        {
            "id": f"e{i}",
            "document_id": f"doc{i}",
            "location": {"line_start": 1},
            "kind": "evidence",
            "evidence_type": "declaration",
            "text": text,
        }
        for i, text in enumerate(case["texts"])
    ]
    return {
        "case": {
            "id": case["id"],
            "name": "Synthetic evaluation",
            "relationship": case.get("relationship", {}),
        },
        "policy": {"id": "held-out", "name": "Held-out synthetic"},
        "requirements": requirements,
        "chunks": chunks,
        "model_mode": mode,
    }


def fact_key(field, value):
    if isinstance(value, bool):
        return field, str(value)
    if isinstance(value, (int, float)):
        return field, str(float(value))
    return field, str(value)


def evaluate(cases, variant, mode):
    statuses_correct = statuses_total = risk_correct = supported = citations = 0
    facts_correct = facts_predicted = facts_gold = hits = relevant_total = 0
    durations, completeness_errors, case_results = [], [], []
    total_input = total_output = 0
    for case in cases:
        snap = build_snapshot(case, mode)
        report = analyze(snap, variant)
        actual = [f["status"] for f in report["findings"]]
        statuses_correct += sum(
            a == b for a, b in zip(actual, case["expected_statuses"], strict=True)
        )
        statuses_total += len(actual)
        risk_correct += report["risk"] == case["expected_risk"]
        completeness_errors.append(abs(report["completeness"] - case["expected_completeness"]))
        predicted = {fact_key(f["field"], f["value"]) for f in report["facts"]}
        gold = {fact_key(f, v) for f, v in case["expected_facts"]}
        facts_correct += len(predicted & gold)
        facts_predicted += len(predicted)
        facts_gold += len(gold)
        for req, relevant in zip(snap["requirements"], case["relevant"], strict=True):
            retrieved = {
                c["id"]
                for c in retrieve(
                    req["title"] + " " + req["field"], snap["chunks"], variant, top_k=3
                )
            }
            expected = {f"e{index}" for index in relevant}
            hits += len(retrieved & expected)
            relevant_total += len(expected)
        eligible = {c["id"]: c for c in snap["chunks"]}
        for finding in report["findings"]:
            for cite in finding["evidence"]:
                citations += 1
                original = eligible.get(cite["chunk_id"])
                supported += bool(
                    original
                    and cite["quote"] in original["text"]
                    and cite["document_id"] == original["document_id"]
                    and cite["location"] == original["location"]
                )
        durations.append(report["metrics"]["duration_ms"])
        total_input += report["metrics"]["input_tokens"]
        total_output += report["metrics"]["output_tokens"]
        case_results.append(
            {
                "id": case["id"],
                "expected_statuses": case["expected_statuses"],
                "actual_statuses": actual,
                "expected_risk": case["expected_risk"],
                "actual_risk": report["risk"],
                "report": report,
            }
        )
    return {
        "variant": variant,
        "cases": len(cases),
        "status_accuracy": statuses_correct / statuses_total,
        "risk_accuracy": risk_correct / len(cases),
        "extraction_precision": facts_correct / max(1, facts_predicted),
        "extraction_recall": facts_correct / max(1, facts_gold),
        "retrieval_recall_at_3": hits / max(1, relevant_total),
        "citation_resolution_rate": supported / max(1, citations),
        "citation_count": citations,
        "completeness_mean_absolute_error": statistics.mean(completeness_errors),
        "mean_duration_ms": statistics.mean(durations),
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost_usd": 0.0 if mode == "demo" else None,
        "results": case_results,
    }


def regression_gate(report):
    """Fixed demo regression criteria; passing is never a real-model quality claim."""
    failures = []
    if report.get("mode") != "demo":
        failures.append("The fixed regression gate applies only to demo mode")
    if report.get("dataset_version") != "synthetic-held-out-v1":
        failures.append(
            "Unexpected dataset version; review criteria before replacing the fixed set"
        )
    variants = {row["variant"]: row for row in report.get("variants", [])}
    if set(variants) != {"lexical", "hybrid"}:
        failures.append("Both lexical and hybrid measurements are required")
    hybrid = variants.get("hybrid", {})
    for metric in ("status_accuracy", "risk_accuracy"):
        if not hybrid.get(metric, 0) >= 0.9:
            failures.append(f"hybrid {metric} must be at least 0.9")
    for name, row in variants.items():
        if row.get("citation_resolution_rate") != 1.0 or row.get("citation_count", 0) <= 0:
            failures.append(f"{name} citation resolution must equal 1.0 with nonempty evidence")
        results = row.get("results", [])
        if len(results) != 10 or row.get("cases") != 10:
            failures.append(f"{name} must evaluate all ten fixed cases")
        adversarial = [case for case in results if case["id"] == "malicious-appendix"]
        if len(adversarial) != 1:
            failures.append(f"{name} injection case missing or duplicated")
            continue
        case = adversarial[0]
        values = {
            (fact["field"], fact_key(fact["field"], fact["value"])[1])
            for fact in case["report"]["facts"]
        }
        if (
            case["actual_statuses"] != ["fail"]
            or case["actual_risk"] != "High"
            or values != {("retention_days", "365.0")}
        ):
            failures.append(f"{name} injection changed a fact, finding or risk")
    return {
        "checked": True,
        "passed": not failures,
        "failures": failures,
        "thresholds": {
            "hybrid_status_accuracy": 0.9,
            "hybrid_risk_accuracy": 0.9,
            "citation_resolution_rate": 1.0,
            "injection_overrides": 0,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["demo", "gemini"], default="demo")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail on fixed-set demo regression thresholds (no model calls)",
    )
    args = parser.parse_args()
    if args.check and args.mode != "demo":
        parser.error("--check only supports demo mode; real-model evaluation is separate")
    dataset = json.loads((ROOT / "held_out.json").read_text())
    output = ROOT / f"results-{args.mode}.json"
    report = {
        "dataset_version": dataset["version"],
        "mode": args.mode,
        "model": os.getenv("GEMINI_MODEL") if args.mode == "gemini" else "demo",
        "timestamp": datetime.now(UTC).isoformat(),
        "real_model_quality_validated": False,
    }
    if args.mode == "gemini" and not (os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_MODEL")):
        report.update(
            status="pending_credentials",
            reason="Set GEMINI_API_KEY and explicitly select GEMINI_MODEL; no calls made.",
        )
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(report["reason"])
        return 2
    try:
        report["variants"] = [
            evaluate(dataset["cases"], variant, args.mode) for variant in ["lexical", "hybrid"]
        ]
        report["status"] = "completed"
        report["real_model_evaluated"] = args.mode == "gemini"
    except (ModelError, ValueError, KeyError, TypeError) as exc:
        report.update(
            status="failed",
            reason=f"Evaluation stopped: {type(exc).__name__}. Inspect configuration; no fallback.",
        )
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(report["reason"], file=sys.stderr)
        return 1
    if args.check:
        report["regression_gate"] = regression_gate(report)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    write_markdown(report)
    print(
        json.dumps(
            [{k: v for k, v in row.items() if k != "results"} for row in report["variants"]],
            indent=2,
        )
    )
    if args.check and not report["regression_gate"]["passed"]:
        print(
            "Regression gate failed: " + "; ".join(report["regression_gate"]["failures"]),
            file=sys.stderr,
        )
        return 1
    return 0


def write_markdown(report):
    lines = [
        "# Synthetic analysis evaluation",
        "",
        f"Dataset: `{report['dataset_version']}`. Mode: `{report['mode']}`. "
        f"Model: `{report['model']}`. Cases per variant: {report['variants'][0]['cases']}.",
        "",
        "| Variant | Extraction P/R | Status accuracy | Risk accuracy | Retrieval recall@3 "
        "| Exact citation resolution | Completeness MAE | Mean ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["variants"]:
        lines.append(
            f"| {row['variant']} | {row['extraction_precision']:.1%}/"
            f"{row['extraction_recall']:.1%} | {row['status_accuracy']:.1%} | "
            f"{row['risk_accuracy']:.1%} | {row['retrieval_recall_at_3']:.1%} | "
            f"{row['citation_resolution_rate']:.1%} | "
            f"{row['completeness_mean_absolute_error']:.1f} | {row['mean_duration_ms']:.2f} |"
        )
    lines.extend(
        [
            "",
            (
                "These are measured deterministic demo results "
                "on ten hand-authored synthetic cases."
                if report["mode"] == "demo"
                else "These are measured real-model results on ten hand-authored synthetic cases."
            )
            + " They do not establish general LLM quality, legal interpretation, multilingual "
            "extraction, semantic entailment, or production safety. Hash embeddings are a local "
            "demonstration, not a trained semantic embedding model. Exact citation resolution "
            "proves a quote exists, not that it supports an arbitrary model interpretation.",
            "",
            "The lexical baseline intentionally misses synonym-only evidence. Hybrid adds "
            "deterministic hash similarity and explicit aliases; this tiny regression set is not "
            "evidence of general semantic quality. Expected outputs were authored separately "
            "from the application demo documents. No statistical significance or independently "
            "reviewed gold labels are claimed. Human review of labels and a larger frozen "
            "corpus remain necessary.",
            "",
            "Real-model evaluation is separate: `PYTHONPATH=backend/src python evaluations/run.py "
            "--mode gemini`. Without credentials and a selected model it writes pending status "
            "and exits 2. Calls have bounded input/output, timeout, retries and concurrency; "
            "quota exhaustion stops. Provider cost is unknown (null), never reported as free. "
            "Check account pricing, quotas and data terms before enabling credentials. "
            "No paid fallback or billing activation is implemented.",
            "",
            "Demo regression target for this fixed set: hybrid status/risk accuracy >= 90%, "
            "citation resolution 100%, no adversarial instruction override. These are demo "
            "regression targets chosen after baseline, not accepted real-model quality "
            "thresholds. See JSON for individual cases and measurements.",
        ]
    )
    (ROOT / f"report-{report['mode']}.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
