"""Explicit, repeatable local synthetic demo bootstrap; importing does not seed data."""

import argparse
import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from counterparty.config import Settings
from counterparty.database import create_engine_for_settings
from counterparty.documents import chunks_for, ingest
from counterparty.models import AnalysisRun, AssessmentCase, AuditEvent, PolicySetVersion, User
from counterparty.organizations import Organization
from counterparty.security import audit, hash_password

DEMO_PASSWORD = "Demo-only-2026!"
DEMO_ACCOUNTS = [
    {
        "email": "analyst@northstar.demo",
        "name": "Demo Analyst",
        "role": "analyst",
        "organization": "Northstar Labs",
    },
    {
        "email": "reviewer@northstar.demo",
        "name": "Demo Reviewer",
        "role": "reviewer",
        "organization": "Northstar Labs",
    },
    {
        "email": "analyst@other.demo",
        "name": "Other Organization Analyst",
        "role": "analyst",
        "organization": "Other Demo Organization",
    },
]


# Retired demo identities must remain blocked when demo mode is disabled.
DEMO_EMAILS = {account["email"] for account in DEMO_ACCOUNTS} | {
    "admin@northstar.demo",
    "auditor@northstar.demo",
}


def bootstrap(engine, settings: Settings, fixture_root: Path, *, accounts_only=False) -> dict:
    if not settings.demo_mode:
        raise ValueError("Synthetic demo bootstrap requires DEMO_MODE=true")
    if settings.model_mode != "demo":
        raise ValueError("Bootstrap requires MODEL_MODE=demo and never calls a model provider")
    # Accounts-only bootstrap must not depend on optional demo documents.
    example = None if accounts_only else load_example(fixture_root)
    counts = {"users": 0, "policies": 0, "cases": 0, "documents": 0}
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(748213609)"))
        organizations = {}
        for slug, name in (
            ("synthetic-northstar-labs", "Northstar Labs (synthetic demo)"),
            ("synthetic-other-demo", "Other Demo Organization"),
        ):
            if accounts_only and slug == "synthetic-other-demo":
                continue
            organization = session.scalar(select(Organization).where(Organization.slug == slug))
            if organization is not None and not organization.is_synthetic:
                raise ValueError("Demo organization conflicts with a non-synthetic record")
            if organization is None:
                organization = Organization(slug=slug, name=name, is_synthetic=True)
                session.add(organization)
                session.flush()
            organizations[slug] = organization
        users = {}
        for account in DEMO_ACCOUNTS:
            if accounts_only and account["email"].endswith("@other.demo"):
                continue
            slug = (
                "synthetic-other-demo"
                if account["email"].endswith("@other.demo")
                else "synthetic-northstar-labs"
            )
            user = session.scalar(select(User).where(User.email == account["email"]))
            if user is not None and (
                user.organization_id != organizations[slug].id or user.role != account["role"]
            ):
                raise ValueError("Demo account conflicts with an existing account")
            if user is None:
                user = User(
                    organization_id=organizations[slug].id,
                    email=account["email"],
                    name=account["name"],
                    role=account["role"],
                    password_hash=hash_password(DEMO_PASSWORD),
                    is_active=True,
                )
                session.add(user)
                session.flush()
                counts["users"] += 1
            users[account["email"]] = user
        if accounts_only:
            audit(session, users["reviewer@northstar.demo"], "synthetic.bootstrap_completed")
            return counts
        analyst = users["analyst@northstar.demo"]
        reviewer = users["reviewer@northstar.demo"]
        existing = session.scalar(
            select(PolicySetVersion).where(
                PolicySetVersion.organization_id == analyst.organization_id,
                PolicySetVersion.name == example["policy"]["name"],
                PolicySetVersion.version == 1,
            )
        )
        seeded = session.scalar(
            select(AuditEvent.id)
            .where(
                AuditEvent.organization_id == analyst.organization_id,
                AuditEvent.event.in_(("synthetic.bootstrap_completed", "synthetic.policy_seeded")),
            )
            .limit(1)
        )
        if existing is None and seeded is None:
            seed_example(session, settings, fixture_root, example, analyst, reviewer, counts)
        if seeded is None and existing is not None:
            audit(session, reviewer, "synthetic.bootstrap_completed")
    return counts


def load_example(fixture_root):
    example = json.loads((fixture_root / "gemini-example.json").read_text())
    if example["format_version"] != 1 or example["report"]["model_mode"] != "gemini":
        raise ValueError("Expected a recorded Gemini example")
    for document in example["documents"]:
        path = (fixture_root / document["path"]).resolve()
        if not path.is_relative_to(fixture_root.resolve()):
            raise ValueError("Example document must remain within fixture directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != document["sha256"]:
            raise ValueError(f"Recorded example source changed: {document['filename']}")
    return example


def remap_ids(value, identifiers):
    """Only remap exact opaque IDs, including retrieval-score dictionary keys."""
    if isinstance(value, dict):
        return {
            identifiers.get(key, key): remap_ids(item, identifiers) for key, item in value.items()
        }
    if isinstance(value, list):
        return [remap_ids(item, identifiers) for item in value]
    return identifiers.get(value, value) if isinstance(value, str) else value


def seed_example(session, settings, fixture_root, example, analyst, reviewer, counts):
    from counterparty.analysis.schemas import validate_source
    from counterparty.analysis.semantic import (
        SemanticAssessment,
        build_report,
        validate_narrative_requirements,
    )

    case = AssessmentCase(
        organization_id=analyst.organization_id, owner_id=analyst.id, **example["case"]
    )
    session.add(case)
    session.flush()
    identifiers, documents = {}, []
    for recorded in example["documents"]:
        document, created = ingest(
            session,
            reviewer,
            (fixture_root / recorded["path"]).read_bytes(),
            recorded["filename"],
            recorded["kind"],
            case.id if recorded["kind"] == "evidence" else None,
            settings.storage_path,
        )
        documents.append(document)
        counts["documents"] += created
        identifiers[recorded["id"]] = str(document.id)
        actual_chunks = chunks_for(session, [document])
        if len(actual_chunks) != len(recorded["chunks"]):
            raise ValueError("Recorded chunk boundaries changed; recapture the example")
        for old, current in zip(recorded["chunks"], actual_chunks, strict=True):
            if (
                old["location"] != current["location"]
                or old["sha256"] != hashlib.sha256(current["text"].encode()).hexdigest()
            ):
                raise ValueError("Recorded chunk content changed; recapture the example")
            identifiers[old["id"]] = current["id"]
    chunks = chunks_for(session, documents)
    requirements = validate_narrative_requirements(
        remap_ids(example["policy"]["requirements"], identifiers), chunks
    )
    report = remap_ids(example["report"], identifiers)
    findings = report["findings"]
    if [f["requirement_id"] for f in findings] != [r["id"] for r in requirements]:
        raise ValueError("Recorded report must cover every requirement exactly once")
    evidence = [chunk for chunk in chunks if chunk["kind"] == "evidence"]
    for finding, requirement in zip(findings, requirements, strict=True):
        for field, expected in (
            ("requirement_source", requirement["source"]),
            ("requirement_description", requirement["description"]),
            ("title", requirement["title"]),
            ("severity", requirement["severity"]),
        ):
            if finding[field] != expected:
                raise ValueError("Recorded finding differs from its extracted requirement")
        SemanticAssessment.model_validate(
            {
                "status": finding["status"],
                "explanation": finding["explanation"],
                "missing_information": finding["missing_information"],
                "evidence": [
                    {k: v for k, v in citation.items() if k != "evidence_type"}
                    for citation in finding["evidence"]
                ],
            }
        )
        for citation in finding["evidence"]:
            validate_source({k: v for k, v in citation.items() if k != "evidence_type"}, evidence)
    aggregated = build_report(findings, "gemini")
    if any(
        report[key] != aggregated[key]
        for key in ("risk", "completeness", "questions", "discrepancies")
    ):
        raise ValueError("Recorded report aggregation does not match its findings")
    policy_document_ids = [str(d.id) for d in documents if d.kind == "policy"]
    policy = PolicySetVersion(
        organization_id=analyst.organization_id,
        name=example["policy"]["name"],
        version=1,
        status="approved",
        document_ids=policy_document_ids,
        extraction_key=hashlib.sha256(json.dumps(sorted(policy_document_ids)).encode()).hexdigest(),
        requirements=requirements,
        created_by=reviewer.id,
        approved_by=reviewer.id,
        approved_at=datetime.now(UTC),
    )
    session.add(policy)
    session.flush()
    provenance = {
        "captured_at": example["captured_at"],
        "model_name": example["model_name"],
        "description": example["provenance"],
    }
    report["recorded_example"] = provenance
    report["workflow_complete"] = False
    retrieval = remap_ids(example["retrieval_snapshot"], identifiers)
    snapshot = {
        "case": {"id": str(case.id), **example["case"]},
        "policy": {"id": str(policy.id), "name": policy.name, "version": policy.version},
        "requirements": requirements,
        "chunks": chunks,
        "model_mode": "gemini",
        "model_name": example["model_name"],
        "assessment_version": "semantic-v2",
        "retrieval_config": retrieval["config"],
        "retrieval_fingerprint": retrieval["fingerprint"],
        "retrieval_algorithm": retrieval["config"]["retrieval"],
    }
    run = AnalysisRun(
        organization_id=analyst.organization_id,
        case_id=case.id,
        created_by=analyst.id,
        policy_version_id=policy.id,
        status="awaiting_review",
        input_snapshot=snapshot,
        retrieval_snapshot=retrieval,
        report=report,
        retrieval_variant="hybrid",
        model_mode="gemini",
        assessment_progress={
            "version": "semantic-v2",
            "total": len(requirements),
            "completed": len(requirements),
            "completed_ids": [r["id"] for r in requirements],
            "findings": copy.deepcopy(findings),
            "attempts": {},
            "metrics": report["metrics"],
            "current_requirement_id": None,
        },
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()
    audit(
        session,
        reviewer,
        "synthetic.policy_seeded",
        details={
            "policy_id": str(policy.id),
            "manifest_provenance": provenance,
            "extraction_metrics": example["extraction_metrics"],
        },
    )
    audit(
        session,
        reviewer,
        "synthetic.report_seeded",
        case.id,
        run.id,
        details={"provenance": provenance},
    )
    counts["policies"] += 1
    counts["cases"] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path("/app/datasets/synthetic"))
    parser.add_argument(
        "--accounts-only",
        action="store_true",
        help="Create only the two Northstar accounts, without sample documents or policies",
    )
    args = parser.parse_args()
    settings = Settings()
    engine = create_engine_for_settings(settings)
    try:
        print(bootstrap(engine, settings, args.fixtures, accounts_only=args.accounts_only))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
