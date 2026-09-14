"""Explicit, repeatable local synthetic demo bootstrap; importing does not seed data."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from counterparty.config import Settings
from counterparty.database import create_engine_for_settings
from counterparty.documents import ingest
from counterparty.models import AssessmentCase, PolicySetVersion, User
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
    policies = {
        name: (fixture_root / "policies" / f"{name}.md").read_bytes()
        for name in ("northstar", "orchard")
    }
    evidence = {
        name: (fixture_root / "evidence" / f"{name}.md").read_bytes()
        for name in ("complete", "missing", "conflict", "discrepancy", "injection")
    }
    from counterparty.analysis import propose_requirements
    from counterparty.routes import chunks_for, validated_requirements

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
        for name, raw in policies.items():
            policy_name = f"Synthetic {name.title()} policy"
            existing = session.scalar(
                select(PolicySetVersion).where(
                    PolicySetVersion.organization_id == analyst.organization_id,
                    PolicySetVersion.name == policy_name,
                )
            )
            if existing is not None:
                continue
            document, created = ingest(
                session, analyst, raw, f"{name}.md", "policy", None, settings.storage_path
            )
            counts["documents"] += created
            chunks = chunks_for(session, [document])
            policy = PolicySetVersion(
                organization_id=analyst.organization_id,
                name=policy_name,
                version=1,
                status="approved",
                document_ids=[str(document.id)],
                requirements=validated_requirements(
                    propose_requirements(chunks, mode="demo"), chunks
                ),
                created_by=analyst.id,
                approved_by=reviewer.id,
                approved_at=datetime.now(UTC),
            )
            session.add(policy)
            session.flush()
            audit(session, reviewer, "demo.policy_seeded", details={"policy_id": str(policy.id)})
            counts["policies"] += 1
        for scenario, raw in evidence.items():
            name = f"Synthetic scenario: {scenario}"
            case = session.scalar(
                select(AssessmentCase).where(
                    AssessmentCase.organization_id == analyst.organization_id,
                    AssessmentCase.name == name,
                )
            )
            if case is not None:
                continue
            case = AssessmentCase(
                organization_id=analyst.organization_id,
                owner_id=analyst.id,
                name=name,
                counterparty_name=f"Synthetic {scenario.title()} Vendor",
                relationship={
                    "purpose": "Synthetic technology supplier assessment",
                    "data_shared": "Synthetic customer records",
                    "system_access": "Admin console",
                    "business_criticality": "high",
                    "personal_data": True,
                    "privileged_access": True,
                },
            )
            session.add(case)
            session.flush()
            _, created = ingest(
                session, analyst, raw, f"{scenario}.md", "evidence", case.id, settings.storage_path
            )
            counts["documents"] += created
            counts["cases"] += 1
            audit(
                session,
                analyst,
                "demo.case_seeded",
                case_id=case.id,
                details={"scenario": scenario},
            )
    return counts


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
