"""Two-role authorization, including historical decisions on a shared case."""

# ruff: noqa: F811 -- pytest injects the imported shared fixture by parameter name.

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_domain import case, domain_setup, index_all, login, proposed, upload  # noqa: F401

from counterparty.models import AnalysisRun, Decision, User

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_analyst_cannot_modify_policy_sources_or_versions(domain_setup, client_factory):
    settings, _ = domain_setup
    async with client_factory(settings) as client:
        await login(client, "reviewer")
        document = await upload(client)
        policy = await proposed(client, document["id"])
        await login(client)
        assert (await client.get(f"/api/documents/{document['id']}")).status_code == 200
        assert (await client.get(f"/api/policies/{policy['id']}")).status_code == 200
        denied = await client.post(
            "/api/documents",
            data={"kind": "policy"},
            files={"file": ("new.txt", b"New organizational policy.")},
        )
        assert denied.status_code == 403
        for regenerate in (False, True):
            response = await client.post(
                "/api/policies/propose",
                json={
                    "name": "Unauthorized extraction",
                    "document_ids": [document["id"]],
                    "regenerate": regenerate,
                },
            )
            assert response.status_code == 403
        for method, path in (
            ("post", f"/api/documents/{document['id']}/reindex"),
            ("delete", f"/api/documents/{document['id']}"),
            ("post", f"/api/policies/{policy['id']}/approve"),
            ("delete", f"/api/policies/{policy['id']}"),
        ):
            assert (await getattr(client, method)(path)).status_code == 403
        await login(client, "reviewer")
        assert (await client.post(f"/api/documents/{document['id']}/reindex")).status_code == 200
        assert (await client.post(f"/api/policies/{policy['id']}/approve")).status_code == 200
        assert (await client.delete(f"/api/policies/{policy['id']}")).status_code == 200
        assert (await client.delete(f"/api/documents/{document['id']}")).status_code == 200


@pytest.mark.parametrize("decision_kind", ["accepted", "rejected"])
async def test_old_decision_freezes_all_analyst_mutations_even_on_newer_run(
    domain_setup, client_factory, decision_kind
):

    settings, engine = domain_setup
    async with client_factory(settings) as client:
        await login(client, "reviewer")
        policy_source = await upload(client)
        policy = await proposed(client, policy_source["id"])
        assert (await client.post(f"/api/policies/{policy['id']}/approve")).status_code == 200
        await login(client)
        relationship = await case(client)
        case_id = relationship["id"]
        body = {"policy_version_id": policy["id"]}
        old = await client.post(f"/api/cases/{case_id}/runs", json=body)
        assert old.status_code == 201, old.text
        old_id = old.json()["id"]
        # Evidence not referenced by either snapshot: deletion must fail because of the
        # decision, not the existing immutable-source reference guard.
        await login(client, "peer")
        newer = await client.post(f"/api/cases/{case_id}/runs", json=body)
        assert newer.status_code == 201, newer.text
        new_id = newer.json()["id"]
        evidence = await upload(client, b"Unreferenced evidence.", "evidence.txt", case_id)
        with Session(engine) as session:
            reviewer = session.scalar(select(User).where(User.role == "reviewer"))
            old_run = session.get(AnalysisRun, UUID(old_id))
            old_run.status = "completed"
            old_run.report = {"model_mode": "demo"}
            session.get(AnalysisRun, UUID(new_id)).status = "failed"
            session.add(
                Decision(
                    organization_id=old_run.organization_id,
                    run_id=old_run.id,
                    actor_id=reviewer.id,
                    decision=decision_kind,
                    rationale="Keep this historical decision intact.",
                )
            )
            session.commit()
        for actor in ("analyst", "peer"):
            await login(client, actor)
            for path in (
                f"/api/cases/{case_id}",
                f"/api/cases/{case_id}/runs",
                f"/api/runs/{old_id}",
                f"/api/runs/{new_id}",
                f"/api/documents/{evidence['id']}/download",
            ):
                assert (await client.get(path)).status_code == 200
            operations = (
                ("patch", f"/api/cases/{case_id}", {"json": {"name": "Blocked"}}),
                ("post", f"/api/cases/{case_id}/runs", {"json": body}),
                ("post", f"/api/runs/{new_id}/retry", {}),
                ("delete", f"/api/runs/{old_id}", {}),
                ("delete", f"/api/runs/{new_id}", {}),
                ("delete", f"/api/cases/{case_id}", {}),
                ("post", f"/api/documents/{evidence['id']}/reindex", {}),
                ("delete", f"/api/documents/{evidence['id']}", {}),
                (
                    "post",
                    "/api/documents",
                    {
                        "data": {"kind": "evidence", "case_id": case_id},
                        "files": {"file": ("new.txt", b"Blocked evidence.")},
                    },
                ),
            )
            for method, path, kwargs in operations:
                response = await getattr(client, method)(path, **kwargs)
                assert response.status_code == 403, (actor, method, path, response.text)
        with Session(engine) as session:
            assert session.scalar(select(Decision)).run_id == UUID(old_id)
            assert session.get(AnalysisRun, UUID(new_id)).status == "failed"
        await login(client, "reviewer")
        assert (
            await client.patch(f"/api/cases/{case_id}", json={"name": "Reviewed"})
        ).status_code == 200
        await upload(client, b"Reviewer follow-up.", "follow-up.txt", case_id)
        assert (await client.post(f"/api/documents/{evidence['id']}/reindex")).status_code == 200
        assert (await client.delete(f"/api/documents/{evidence['id']}")).status_code == 200
        assert (await client.post(f"/api/runs/{new_id}/retry")).status_code == 200
        assert (await client.delete(f"/api/runs/{new_id}")).status_code == 200
        index_all(engine, settings)
        assert (await client.post(f"/api/cases/{case_id}/runs", json=body)).status_code == 201
        assert (await client.delete(f"/api/cases/{case_id}")).status_code == 200


async def test_information_request_keeps_case_open_and_preserves_reviewed_report(
    domain_setup, client_factory
):
    settings, engine = domain_setup
    async with client_factory(settings) as client:
        await login(client, "reviewer")
        source = await upload(client)
        policy = await proposed(client, source["id"])
        await client.post(f"/api/policies/{policy['id']}/approve")
        relationship = await case(client)
        run = (
            await client.post(
                f"/api/cases/{relationship['id']}/runs",
                json={"policy_version_id": policy["id"]},
            )
        ).json()
        run_id = run["id"]
        endpoint = f"/api/runs/{run_id}/information-request-draft"
        assert (await client.put(endpoint, json={"text": "Too early"})).status_code == 409
        with Session(engine) as session:
            row = session.get(AnalysisRun, UUID(run_id))
            row.status = "awaiting_review"
            row.report = {"model_mode": "demo", "findings": []}
            session.commit()
        await login(client)
        draft = await client.put(endpoint, json={"text": "Please provide the assurance report."})
        assert draft.status_code == 200, draft.text
        assert draft.json()["information_request_draft"]["actor_email"] == "analyst@example.test"
        assert (
            await client.put(endpoint, json={"text": "Overwrite submitted request"})
        ).status_code == 403
        assert (
            await client.post(
                f"/api/runs/{run_id}/decision",
                json={"decision": "needs_information", "rationale": "Not allowed"},
            )
        ).status_code == 403
        await login(client, "foreign")
        assert (await client.put(endpoint, json={"text": "Not allowed"})).status_code == 404
        await login(client, "reviewer")
        revised = "Provide the signed assurance report and its service scope."
        assert (await client.put(endpoint, json={"text": revised})).status_code == 200
        decided = await client.post(
            f"/api/runs/{run_id}/decision",
            json={"decision": "needs_information", "rationale": revised},
        )
        assert decided.status_code == 201, decided.text
        assert decided.json()["case_is_decided"] is False
        await login(client)
        assert (await client.put(endpoint, json={"text": "Change history"})).status_code == 409
        assert (await client.delete(f"/api/runs/{run_id}")).status_code == 403
        assert (
            await client.patch(
                f"/api/cases/{relationship['id']}", json={"name": "Additional evidence"}
            )
        ).status_code == 200
        await upload(client, b"New assurance report.", "assurance.txt", relationship["id"])
        index_all(engine, settings)
        newer = await client.post(
            f"/api/cases/{relationship['id']}/runs",
            json={"policy_version_id": policy["id"]},
        )
        assert newer.status_code == 201, newer.text
        assert newer.json()["id"] != run_id
        old = (await client.get(f"/api/runs/{run_id}")).json()
        assert old["input_snapshot"] == run["input_snapshot"]
        assert old["decision"]["rationale"] == revised
        assert old["report"] == {"model_mode": "demo", "findings": [], "workflow_complete": True}
        assert (
            await client.post(
                f"/api/runs/{run_id}/ticket-proposals", json={"title": "Removed", "body": "Removed"}
            )
        ).status_code == 404


async def test_disabled_account_cannot_login_or_reuse_session(domain_setup, client_factory):
    settings, engine = domain_setup
    async with client_factory(settings) as client:
        await login(client)
        with Session(engine) as session:
            session.scalar(
                select(User).where(User.email == "analyst@example.test")
            ).is_active = False
            session.commit()
        assert (await client.get("/api/auth/me")).status_code == 401
        response = await client.post(
            "/api/auth/login",
            json={"email": "analyst@example.test", "password": "synthetic-password"},
        )
        assert response.status_code == 401


async def test_accounts_only_bootstrap_stays_empty_and_lists_two_accounts(
    database_url, migration_config, tmp_path, client_factory
):
    from pathlib import Path

    from alembic import command
    from sqlalchemy import func

    from counterparty.bootstrap import bootstrap
    from counterparty.config import Settings
    from counterparty.database import create_engine_for_settings
    from counterparty.models import AssessmentCase, Document, PolicySetVersion

    command.upgrade(migration_config, "head")
    settings = Settings(database_url=database_url, storage_path=str(tmp_path))
    engine = create_engine_for_settings(settings)
    fixtures = Path("/datasets/synthetic")
    try:
        assert bootstrap(engine, settings, fixtures, accounts_only=True) == {
            "users": 2,
            "policies": 0,
            "cases": 0,
            "documents": 0,
        }
        assert bootstrap(engine, settings, fixtures, accounts_only=True) == {
            "users": 0,
            "policies": 0,
            "cases": 0,
            "documents": 0,
        }
        with Session(engine) as session:
            for model in (AssessmentCase, Document, PolicySetVersion):
                assert session.scalar(select(func.count()).select_from(model)) == 0
        async with client_factory(settings) as client:
            response = await client.get("/api/demo/accounts")
            assert response.status_code == 200
            assert {account["role"] for account in response.json()} == {"analyst", "reviewer"}
            assert len(response.json()) == 2
        assert bootstrap(engine, settings, fixtures) == {
            "users": 1,
            "policies": 0,
            "cases": 0,
            "documents": 0,
        }
    finally:
        engine.dispose()


async def test_retired_demo_administrator_stays_blocked_outside_demo_mode(
    domain_setup, client_factory
):
    settings, engine = domain_setup
    with Session(engine) as session:
        reviewer = session.scalar(select(User).where(User.email == "reviewer@example.test"))
        reviewer.email = "admin@northstar.demo"
        session.commit()
    async with client_factory(settings) as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "admin@northstar.demo", "password": "synthetic-password"},
        )
        assert response.status_code == 200
        settings.demo_mode = False
        assert (await client.get("/api/auth/me")).status_code == 403
        response = await client.post(
            "/api/auth/login",
            json={"email": "admin@northstar.demo", "password": "synthetic-password"},
        )
        assert response.status_code == 403
