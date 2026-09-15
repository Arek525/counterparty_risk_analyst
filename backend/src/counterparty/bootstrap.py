"""Explicit, repeatable local synthetic demo bootstrap; importing does not seed data."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from counterparty.config import Settings
from counterparty.database import create_engine_for_settings
from counterparty.documents import ingest
from counterparty.models import AuditEvent, PolicySetVersion, User
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
        "email": "auditor@northstar.demo",
        "name": "Demo Auditor",
        "role": "auditor",
        "organization": "Northstar Labs",
    },
    {
        "email": "admin@northstar.demo",
        "name": "Demo Administrator",
        "role": "administrator",
        "organization": "Northstar Labs",
    },
    {
        "email": "analyst@other.demo",
        "name": "Other Organization Analyst",
        "role": "analyst",
        "organization": "Other Demo Organization",
    },
]


def bootstrap(engine, settings: Settings, fixture_root: Path) -> dict:
    if not settings.demo_mode:
        raise ValueError("Synthetic demo bootstrap requires DEMO_MODE=true")
    if settings.model_mode != "demo":
        raise ValueError("Bootstrap requires MODEL_MODE=demo and never calls a model provider")
    # Read every fixture before making database or file changes.
    manifest = json.loads((fixture_root / "policy-manifest.json").read_text())
    policies = {
        name: (fixture_root / "policies" / name).read_bytes() for name in manifest["documents"]
    }
    from counterparty.routes import chunks_for

    counts = {"users": 0, "policies": 0, "cases": 0, "documents": 0}
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(748213609)"))
        organizations = {}
        for slug, name in (
            ("synthetic-northstar-labs", "Northstar Labs (synthetic demo)"),
            ("synthetic-other-demo", "Other Demo Organization"),
        ):
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
        analyst = users["analyst@northstar.demo"]
        reviewer = users["reviewer@northstar.demo"]
        existing = session.scalar(
            select(PolicySetVersion).where(
                PolicySetVersion.organization_id == analyst.organization_id,
                PolicySetVersion.name == manifest["name"],
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
            documents = []
            for name, raw in policies.items():
                document, created = ingest(
                    session, analyst, raw, name, "policy", None, settings.storage_path
                )
                documents.append(document)
                counts["documents"] += created
            requirements = resolve_manifest(manifest, chunks_for(session, documents))
            policy = PolicySetVersion(
                organization_id=analyst.organization_id,
                name=manifest["name"],
                version=1,
                status="approved",
                document_ids=[str(document.id) for document in documents],
                requirements=requirements,
                created_by=analyst.id,
                approved_by=reviewer.id,
                approved_at=datetime.now(UTC),
            )
            session.add(policy)
            session.flush()
            audit(
                session,
                reviewer,
                "synthetic.policy_seeded",
                details={
                    "policy_id": str(policy.id),
                    "manifest_provenance": manifest["provenance"],
                },
            )
            counts["policies"] += 1
        if seeded is None and existing is not None:
            audit(session, reviewer, "synthetic.bootstrap_completed")
    return counts


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path("/app/datasets/synthetic"))
    args = parser.parse_args()
    settings = Settings()
    engine = create_engine_for_settings(settings)
    try:
        print(bootstrap(engine, settings, args.fixtures))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
