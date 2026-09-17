"""Explicit, resumable component evaluation; no provider calls without --live.

Uses production parsing, E5, pgvector scores, prompts and source validation.
The full-document arm replaces only the ranking step inside this isolated process.
Model timing excludes the HTTP API/worker queue; no application records are touched.
"""

import argparse
import hashlib
import inspect
import json
import math
import os
import statistics
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx
from counterparty.analysis import semantic
from counterparty.analysis.schemas import quote_matches, validate_source
from counterparty.documents import extract
from counterparty.embedding_config import CONFIG, FINGERPRINT
from counterparty.embeddings import LocalEmbedder
from counterparty.schemas import Relationship
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent


class BudgetExceeded(RuntimeError):
    pass


def save(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def load_cases(split, selected):
    families = [
        json.loads(p.read_text())
        for p in sorted((ROOT / "cases" / split).glob("*.json"))
    ]
    if not families:
        raise ValueError("No case files found")
    known = {c["id"] for f in families for c in f["cases"]}
    if set(selected) - known:
        raise ValueError("Unknown case selection")
    for family in families:
        family["cases"] = [
            c for c in family["cases"] if not selected or c["id"] in selected
        ]
    return [f for f in families if f["cases"]]


def chunks_for(documents):
    result = []
    for doc in documents:
        if hashlib.sha256(doc["text"].encode()).hexdigest() != doc["sha256"]:
            raise ValueError("Corpus source hash mismatch")
        chunks, _ = extract(doc["text"].encode(), doc["filename"])
        doc_id = str(uuid5(NAMESPACE_URL, doc["id"] + ":" + doc["sha256"]))
        result.extend(
            {
                **c,
                "id": str(uuid5(NAMESPACE_URL, doc_id + ":" + str(i))),
                "document_id": doc_id,
                "kind": doc["kind"],
                "filename": doc["filename"],
                "document_version": 1,
                "document_sha256": doc["sha256"],
                "embedding_model": FINGERPRINT,
                "evidence_type": doc["evidence_type"],
            }
            for i, c in enumerate(chunks)
        )
    return result


def requirements_for(policy, chunks):
    result = []
    for requirement in policy["expected_requirements"]:
        matches = quote_matches(
            requirement["source"]["quote"], chunks, normalize_whitespace=True
        )
        if len(matches) != 1:
            raise ValueError("Policy quotation must resolve uniquely")
        anchor, quote = matches[0]
        source = {
            "document_id": anchor["document_id"],
            "chunk_id": anchor["id"],
            "location": anchor["location"],
            "quote": quote,
        }
        validate_source(source, chunks)
        result.append(
            semantic.NarrativeRequirement.model_validate(
                {
                    **{
                        k: v
                        for k, v in requirement.items()
                        if k not in {"components", "source"}
                    },
                    "source": source,
                }
            ).model_dump()
        )
    return result


def usage(requests):
    unknown = sum(
        not isinstance(r.get("usage"), dict)
        or "promptTokenCount" not in r["usage"]
        or "candidatesTokenCount" not in r["usage"]
        for r in requests
    )
    metadata = [r["usage"] for r in requests if isinstance(r.get("usage"), dict)]
    total = lambda key: sum(u.get(key, 0) for u in metadata)
    return {
        "input_tokens": None if unknown else total("promptTokenCount"),
        "output_tokens": None
        if unknown
        else total("candidatesTokenCount") + total("thoughtsTokenCount"),
        "cached_tokens": None if unknown else total("cachedContentTokenCount"),
        "thinking_tokens": None if unknown else total("thoughtsTokenCount"),
        "requests": len(requests),
        "unknown_usage_requests": unknown,
    }


class Trace:
    """Capture bounded provider responses without storing credentials or request headers."""

    def __init__(self, result, path, step, cap):
        self.result, self.path, self.step, self.cap = result, path, step, cap

    def reserve(self):
        count = sum(len(s["requests"]) for s in self.result["steps"].values())
        if count >= self.cap:
            raise BudgetExceeded("Request cap reached before sending another request")
        entry = {"started_at": datetime.now(UTC).isoformat(), "usage": None}
        self.step["requests"].append(entry)
        save(self.path, self.result)
        return entry

    @contextmanager
    def capture(self):
        original = httpx.Client.send
        trace = self

        def send(client, request, **kwargs):
            # This patch is active only inside a production Gemini assessment/extraction.
            if request.url.host != "generativelanguage.googleapis.com":
                raise ValueError("Unexpected evaluation provider host")
            previous = max(
                (
                    datetime.fromisoformat(r["started_at"]).timestamp()
                    for s in trace.result["steps"].values()
                    for r in s["requests"]
                ),
                default=0,
            )
            pacing = max(0, 5 - (time.time() - previous))
            time.sleep(pacing)
            entry = trace.reserve()
            entry["pacing_seconds"] = pacing
            started = time.monotonic()
            try:
                response = original(client, request, **kwargs)
            except Exception:
                entry.update(
                    http_seconds=time.monotonic() - started, transport_error=True
                )
                save(trace.path, trace.result)
                raise
            entry["http_status"] = response.status_code
            underlying = response.iter_bytes

            def decoded_bytes(*args, **options):
                data = bytearray()
                try:
                    for block in underlying(*args, **options):
                        if len(data) + len(block) <= 250000:
                            data.extend(block)
                        yield block
                finally:
                    entry["http_seconds"] = time.monotonic() - started
                    try:
                        parsed = json.loads(data)
                        entry["usage"] = parsed.get("usageMetadata")
                        if "error" in parsed:
                            entry["provider_error"] = parsed["error"].get("status")
                            entry["quota_details"] = [
                                d
                                for d in parsed["error"].get("details", [])
                                if "QuotaFailure" in d.get("@type", "")
                                or "RetryInfo" in d.get("@type", "")
                            ]
                        entry["model_version"] = parsed.get("modelVersion")
                        candidate = parsed.get("candidates", [{}])[0]
                        entry["finish_reason"] = candidate.get("finishReason")
                        entry["response_text"] = "".join(
                            p.get("text", "")
                            for p in candidate.get("content", {}).get("parts", [])
                            if not p.get("thought")
                        )
                    except (ValueError, KeyError, TypeError, IndexError):
                        pass
                    save(trace.path, trace.result)

            response.iter_bytes = decoded_bytes
            if response.status_code != 200:
                response.read()
            entry["http_seconds"] = time.monotonic() - started
            save(trace.path, trace.result)
            return response

        with patch.object(httpx.Client, "send", send):
            yield


@contextmanager
def score_database():
    url = make_url(os.environ["TEST_DATABASE_ADMIN_URL"])
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    name = "test_counterparty_evaluation_" + uuid4().hex
    engine = None
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
        engine = create_engine(url.set(database=name))
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE EXTENSION vector")
            connection.exec_driver_sql(
                "CREATE TEMP TABLE evidence (id text PRIMARY KEY, embedding vector(384))"
            )
            yield connection
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.dispose()


def score_case(connection, model, chunks, requirements):
    started = time.monotonic()
    vectors = model.embed([c["text"] for c in chunks], "passage")
    connection.execute(text("TRUNCATE evidence"))
    for chunk, vector in zip(chunks, vectors, strict=True):
        connection.execute(
            text("INSERT INTO evidence VALUES (:id, CAST(:v AS vector))"),
            {"id": chunk["id"], "v": json.dumps(vector)},
        )
    index_seconds = time.monotonic() - started
    started = time.monotonic()
    queries = model.embed(
        [semantic.requirement_query(r) for r in requirements], "query"
    )
    scores = {}
    for req, vector in zip(requirements, queries, strict=True):
        scores[req["id"]] = dict(
            connection.execute(
                text("SELECT id, 1 - (embedding <=> CAST(:v AS vector)) FROM evidence"),
                {"v": json.dumps(vector)},
            ).all()
        )
    return scores, {
        "passage_index_seconds": index_seconds,
        "query_encoding_and_scoring_seconds": time.monotonic() - started,
    }


def evidence_coverage(expected, selected, documents):
    by_id = {
        d["id"]: str(uuid5(NAMESPACE_URL, d["id"] + ":" + d["sha256"]))
        for d in documents
    }
    groups = []
    for group in expected["required_evidence_groups"]:
        found = any(
            quote_matches(
                ref["quote"],
                [c for c in selected if c["document_id"] == by_id[ref["document_id"]]],
                normalize_whitespace=True,
            )
            for ref in group["any_of"]
        )
        groups.append({"id": group["id"], "recovered": found})
    return groups


def run_step(result, path, key, cap, function, retry=False, **details):
    existing = result["steps"].get(key)
    if existing and (existing["status"] in {"completed", "ineligible"} or not retry):
        return existing
    step = {
        **details,
        "status": "running",
        "requests": existing["requests"] if existing else [],
        "seconds": existing.get("seconds", 0) if existing else 0,
    }
    if existing:
        step["previous_errors"] = existing.get("previous_errors", []) + [
            existing.get("error")
        ]
    result["steps"][key] = step
    save(path, result)
    started = time.monotonic()
    trace = Trace(result, path, step, cap)
    try:
        with trace.capture():
            step["output"] = function()
        step["status"] = "completed"
    except (ValueError, RuntimeError) as exc:
        step["status"] = "ineligible" if "context exceeds" in str(exc) else "error"
        step["error"] = str(exc)
        if isinstance(exc, BudgetExceeded) or "quota exhausted" in str(exc):
            raise
    finally:
        step["seconds"] = step.get("seconds", 0) + time.monotonic() - started
        step["usage"] = usage(step["requests"])
        save(path, result)
    return step


def summary(result):
    arms = {}
    for arm in ("hybrid", "full_document"):
        rows = [s for s in result["steps"].values() if s.get("arm") == arm]
        completed = [s for s in rows if s["status"] == "completed"]
        groups = [g for s in rows for g in s.get("evidence_groups", [])]
        confusion = {}
        for row in rows:
            predicted = (
                row["output"]["status"]
                if row["status"] == "completed"
                else row["status"]
            )
            label = row["expected_status"] + " -> " + predicted
            confusion[label] = confusion.get(label, 0) + 1
        cases = {r["case_id"] for r in rows}
        case_scores = [
            sum(
                r["status"] == "completed"
                and r["output"]["status"] == r["expected_status"]
                for r in rows
                if r["case_id"] == c
            )
            / sum(r["case_id"] == c for r in rows)
            for c in cases
        ]
        durations = sorted(r["seconds"] for r in rows)
        required = [r for r in rows if r.get("evidence_groups")]

        arms[arm] = {
            "attempted": len(rows),
            "confusion": confusion,
            "case_macro_agreement": statistics.mean(case_scores)
            if case_scores
            else None,
            "false_pass": sum(
                r["status"] == "completed"
                and r["output"]["status"] == "pass"
                and r["expected_status"] in {"fail", "unknown", "conflict"}
                for r in rows
            ),
            "false_pass_denominator": sum(
                r["expected_status"] in {"fail", "unknown", "conflict"} for r in rows
            ),
            "all_evidence_groups_recovered": sum(
                all(g["recovered"] for g in r["evidence_groups"]) for r in required
            ),
            "requirements_with_evidence_groups": len(required),
            "seconds": {
                "n": len(durations),
                "total": sum(durations),
                "median": statistics.median(durations) if durations else None,
                "p95_nearest_rank": durations[math.ceil(0.95 * len(durations)) - 1]
                if durations
                else None,
            },
            "completed": len(completed),
            "correct_status": sum(
                s["output"]["status"] == s["expected_status"] for s in completed
            ),
            "errors": sum(s["status"] == "error" for s in rows),
            "ineligible": sum(s["status"] == "ineligible" for s in rows),
            "evidence_groups_recovered": sum(g["recovered"] for g in groups),
            "evidence_groups_total": len(groups),
            "usage": usage([r for s in rows for r in s["requests"]]),
        }
    pairs = []
    for key, row in result["steps"].items():
        if row.get("arm") != "hybrid":
            continue
        other = result["steps"].get(key.replace("/hybrid/", "/full_document/"))
        if other and all(
            s["status"] == "completed" and s["usage"]["input_tokens"] is not None
            for s in (row, other)
        ):
            pairs.append((row, other))
    totals = [
        sum(
            s[i]["usage"]["input_tokens"] + s[i]["usage"]["output_tokens"]
            for s in pairs
        )
        for i in (0, 1)
    ]
    return {
        "arms": arms,
        "extraction_usage": usage(
            [
                r
                for s in result["steps"].values()
                if s.get("kind") == "extraction"
                for r in s["requests"]
            ]
        ),
        "total_usage": usage(
            [r for s in result["steps"].values() for r in s["requests"]]
        ),
        "paired_usage": {
            name: usage([r for pair in pairs for r in pair[i]["requests"]])
            for i, name in enumerate(("hybrid", "full_document"))
        },
        "eligible_completed_pairs_with_known_usage": len(pairs),
        "paired_input_plus_output_tokens": dict(
            zip(("hybrid", "full_document"), totals, strict=True)
        ),
        "paired_token_reduction": 1 - totals[0] / totals[1] if totals[1] else None,
        "interpretation": "Agreement with proposed labels, not independently human-validated accuracy. Citation support and extraction completeness need review.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split", choices=("development", "held-out"), default="development"
    )
    parser.add_argument("--cases", nargs="*", default=[])
    parser.add_argument(
        "--arms", nargs="+", choices=("hybrid", "full_document"), default=["hybrid"]
    )
    parser.add_argument("--output", type=Path, default=ROOT / "output/development.json")
    parser.add_argument("--cache", default="/app/model-cache")
    parser.add_argument("--max-calls", type=int, default=24)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument(
        "--final",
        action="store_true",
        help="Explicit access to reserved cases after freeze",
    )
    args = parser.parse_args()
    if args.max_calls < 1:
        parser.error("max-calls must be positive")
    if args.split == "held-out" and not args.final:
        parser.error("Reserved cases require --final after development and freeze")
    families = load_cases(args.split, args.cases)
    for f in families:
        requirements_for(f["policy"], chunks_for([f["policy"]["document"]]))
        for c in f["cases"]:
            Relationship.model_validate(c["relationship"])
            chunks_for(c["documents"])
    if not args.live:
        print(
            json.dumps(
                {
                    "validated_families": len(families),
                    "cases": sum(len(f["cases"]) for f in families),
                    "provider_calls": 0,
                }
            )
        )
        return
    if not os.environ.get("GEMINI_API_KEY") or not os.environ.get("GEMINI_MODEL"):
        parser.error("Explicit GEMINI_API_KEY and GEMINI_MODEL required")
    code = {
        str(p.relative_to(Path(semantic.__file__).parent.parent))
        if p.is_relative_to(Path(semantic.__file__).parent.parent)
        else p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (
            Path(__file__),
            Path(semantic.__file__),
            Path(inspect.getfile(semantic.GeminiAdapter)),
            *Path(semantic.__file__).parent.parent.rglob("*.py"),
        )
        if p.is_file()
    }
    identity = {
        "corpus_sha256": digest(load_cases(args.split, [])),
        "code": code,
        "model": os.environ["GEMINI_MODEL"],
        "prompts": {
            "extraction": digest(semantic.EXTRACTION_INSTRUCTION),
            "assessment": digest(semantic.ASSESSMENT_INSTRUCTION),
        },
        "embedding_fingerprint": FINGERPRINT,
        "split": args.split,
        "arms": sorted(args.arms),
    }
    result = (
        json.loads(args.output.read_text())
        if args.output.exists()
        else {
            "format_version": 1,
            "identity": identity,
            "created_at": datetime.now(UTC).isoformat(),
            "label_review": "pending_human_review",
            "steps": {},
            "config": CONFIG,
            "method": "Production parsing/E5/pgvector/ranking/assessment components; isolated database. Not API/queue latency. Temperature0, one observation per arm/requirement, application retry policy.",
        }
    )
    if result["identity"] != identity:
        parser.error(
            "Corpus/code/model/arms changed; preserve prior results and choose a new output file"
        )
    save(args.output, result)
    started = time.monotonic()
    model = LocalEmbedder(args.cache)
    result.setdefault("cold_model_load_seconds", time.monotonic() - started)
    try:
        with score_database() as connection:
            case_number = 0
            for family in families:
                policy = family["policy"]
                policies = chunks_for([policy["document"]])
                requirements = requirements_for(policy, policies)
                run_step(
                    result,
                    args.output,
                    policy["id"] + "/extraction",
                    args.max_calls,
                    lambda policies=policies: semantic.propose_narrative_requirements(
                        policies, mode="gemini"
                    ),
                    args.retry_failed,
                    kind="extraction",
                    policy_id=policy["id"],
                )
                for case in family["cases"]:
                    chunks = chunks_for(case["documents"])
                    scores, timings = score_case(
                        connection, model, chunks, requirements
                    )
                    result.setdefault("case_setup", {}).setdefault(
                        case["id"],
                        {
                            **timings,
                            "evidence_characters": sum(
                                len(d["text"]) for d in case["documents"]
                            ),
                            "languages": sorted(
                                {d["language"] for d in case["documents"]}
                            ),
                            "tags": case["tags"],
                        },
                    )
                    expected = {
                        e["requirement_id"]: e for e in case["expected_assessments"]
                    }
                    arms = (
                        args.arms if case_number % 2 == 0 else list(reversed(args.arms))
                    )
                    case_number += 1
                    for req in requirements:
                        for arm in arms:
                            selected = (
                                semantic.retrieve(
                                    semantic.requirement_query(req),
                                    chunks,
                                    semantic_scores=scores[req["id"]],
                                )
                                if arm == "hybrid"
                                else chunks
                            )

                            def assess(
                                req=req,
                                arm=arm,
                                chunks=chunks,
                                case=case,
                                scores=scores,
                            ):
                                if arm == "full_document":
                                    with patch.object(
                                        semantic, "retrieve", return_value=chunks
                                    ):
                                        return semantic.assess_requirement(
                                            req,
                                            chunks,
                                            case["relationship"],
                                            semantic_scores=scores[req["id"]],
                                            mode="gemini",
                                        )
                                return semantic.assess_requirement(
                                    req,
                                    chunks,
                                    case["relationship"],
                                    semantic_scores=scores[req["id"]],
                                    mode="gemini",
                                )

                            run_step(
                                result,
                                args.output,
                                case["id"] + "/" + arm + "/" + req["id"],
                                args.max_calls,
                                assess,
                                args.retry_failed,
                                kind="assessment",
                                case_id=case["id"],
                                requirement_id=req["id"],
                                arm=arm,
                                expected_status=expected[req["id"]]["status"],
                                selected_chunk_ids=[c["id"] for c in selected],
                                evidence_groups=evidence_coverage(
                                    expected[req["id"]], selected, case["documents"]
                                ),
                            )
    finally:
        result["summary"] = summary(result)
        save(args.output, result)
        print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
