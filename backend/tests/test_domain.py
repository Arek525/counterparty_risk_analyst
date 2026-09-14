"""Domain acceptance tests against isolated, real PostgreSQL databases."""

import copy
import hashlib
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from pypdf import PdfWriter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from counterparty.bootstrap import bootstrap
from counterparty.config import Settings
from counterparty.database import create_engine_for_settings
from counterparty.models import (
    AnalysisRun,
    AssessmentCase,
    AuthSession,
    DocumentChunk,
    PolicySetVersion,
    User,
)
from counterparty.organizations import Organization
from counterparty.security import hash_password

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PASSWORD = "synthetic-password"
POLICY = b"Personal data retention must not exceed 30 days.\nHosting region must be EU.\n"
EVIDENCE = b"Personal data retention is 20 days. Hosting region is EU."


@pytest.fixture
def domain_setup(database_url, migration_config, tmp_path):
    command.upgrade(migration_config, "head")
    settings = Settings(database_url=database_url, storage_path=str(tmp_path / "storage"))
    engine = create_engine_for_settings(settings)
    with Session(engine) as session:
        organizations = [
            Organization(slug=f"synthetic-domain-{i}", name=f"Synthetic org {i}", is_synthetic=True)
            for i in range(2)
        ]
        session.add_all(organizations)
        session.flush()
        password = hash_password(PASSWORD)
        for name, role, organization in (
            ("analyst", "analyst", organizations[0]),
            ("peer", "analyst", organizations[0]),
            ("reviewer", "reviewer", organizations[0]),
            ("auditor", "auditor", organizations[0]),
            ("foreign", "reviewer", organizations[1]),
        ):
            session.add(
                User(
                    organization_id=organization.id,
                    name=name,
                    role=role,
                    email=f"{name}@example.test",
                    password_hash=password,
                )
            )
        session.commit()
    yield settings, engine
    engine.dispose()


async def login(client, name="analyst"):
    response = await client.post(
        "/api/auth/login", json={"email": f"{name}@example.test", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response


async def case(client):
    response = await client.post(
        "/api/cases",
        json={
            "name": "Synthetic case",
            "counterparty_name": "Synthetic vendor",
            "relationship": {"personal_data": True},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def upload(client, data=POLICY, name="policy.md", case_id=None):
    response = await client.post(
        "/api/documents",
        files={"file": (name, data, "text/plain")},
        data={
            "kind": "evidence" if case_id else "policy",
            **({"case_id": case_id} if case_id else {}),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def proposed(client, document_id):
    response = await client.post(
        "/api/policies/propose", json={"name": "Synthetic policy", "document_ids": [document_id]}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_auth_session_origin_logout_and_expiry(domain_setup, client_factory):
    settings, engine = domain_setup
    async with client_factory(settings) as client:
        assert (await client.get("/api/cases")).status_code == 401
        assert (
            await client.post(
                "/api/auth/login", json={"email": "unknown@example.test", "password": PASSWORD}
            )
        ).status_code == 401
        denied = await client.post(
            "/api/auth/login",
            headers={"Origin": "https://attacker.test"},
            json={"email": "analyst@example.test", "password": PASSWORD},
        )
        assert denied.status_code == 403
        response = await login(client)
        assert "password_hash" not in response.json()
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        token = client.cookies.get("counterparty_session")
        with Session(engine) as session:
            stored = session.scalar(select(AuthSession))
            assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
            assert stored.token_hash != token
            stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()
        assert (await client.get("/api/auth/me")).status_code == 401
        await login(client)
        assert (await client.post("/api/auth/logout")).status_code == 200
        assert (await client.get("/api/auth/me")).status_code == 401
    settings.demo_mode = False
    async with client_factory(settings) as client:
        assert (await client.get("/api/demo/accounts")).status_code == 404


async def test_case_tenant_ownership_and_read_only_roles(domain_setup, client_factory):
    settings, _ = domain_setup
    async with client_factory(settings) as client:
        await login(client)
        created = await case(client)
        document = await upload(client, EVIDENCE, "evidence.md", created["id"])
        await login(client, "peer")
        assert (await client.get("/api/cases")).json() == []
        for path in (
            f"/api/cases/{created['id']}",
            f"/api/documents/{document['id']}",
            f"/api/documents/{document['id']}/download",
            f"/api/documents?case_id={created['id']}",
        ):
            assert (await client.get(path)).status_code == 404
        await login(client, "foreign")
        assert (await client.get(f"/api/cases/{created['id']}")).status_code == 404
        await login(client, "auditor")
        assert len((await client.get("/api/cases")).json()) == 1
        assert (
            await client.post("/api/cases", json={"name": "x", "counterparty_name": "x"})
        ).status_code == 403
        assert (await client.delete(f"/api/documents/{document['id']}")).status_code == 403
        assert (
            await client.patch(f"/api/cases/{created['id']}", json={"name": "x"})
        ).status_code == 403


async def test_upload_validation_hash_dedup_versions_and_deletion(domain_setup, client_factory):
    settings, engine = domain_setup
    async with client_factory(settings) as client:
        await login(client)
        first = await upload(client, name="../../policy.md")
        assert first["filename"] == "policy.md"
        assert first["sha256"] == hashlib.sha256(POLICY).hexdigest()
        duplicate = await upload(client, name="another.md")
        assert duplicate["id"] == first["id"] and duplicate["deduplicated"]
        second = await upload(client, data=POLICY + b"MFA must be enabled.")
        assert second["version"] == 2
        downloaded = await client.get(f"/api/documents/{first['id']}/download")
        assert downloaded.content == POLICY
        assert "attachment" in downloaded.headers["content-disposition"]
        detail = (await client.get(f"/api/documents/{first['id']}")).json()
        assert detail["chunks"][0]["location"]["line_start"] == 1
        assert "storage_key" not in detail
        with Session(engine) as session:
            chunk = session.scalar(
                select(DocumentChunk).where(DocumentChunk.document_id == UUID(first["id"]))
            )
            assert len(chunk.embedding) == 128
        for name, content, expected in (
            ("evil.html", b"<script>alert(1)</script>", 422),
            ("binary.txt", b"abc\x00def", 422),
            ("bad.pdf", b"not a pdf", 422),
            ("empty.txt", b"", 422),
            ("huge.txt", b"a" * (10 * 1024 * 1024 + 1), 413),
        ):
            response = await client.post(
                "/api/documents", files={"file": (name, content)}, data={"kind": "policy"}
            )
            assert response.status_code == expected, response.text
        pdf = PdfWriter()
        pdf.add_blank_page(100, 100)
        buffer = io.BytesIO()
        pdf.write(buffer)
        rejected = await client.post(
            "/api/documents",
            files={"file": ("scan.pdf", buffer.getvalue())},
            data={"kind": "policy"},
        )
        assert rejected.status_code == 422 and "OCR" in rejected.json()["detail"]
        assert (await client.delete(f"/api/documents/{first['id']}")).status_code == 200
        assert (await client.get(f"/api/documents/{first['id']}")).status_code == 404
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(DocumentChunk)
                    .where(DocumentChunk.document_id == UUID(first["id"]))
                )
                == 0
            )


async def test_policy_citations_roles_approval_and_clone(domain_setup, client_factory):
    settings, _ = domain_setup
    async with client_factory(settings) as client:
        await login(client)
        document = await upload(client)
        policy = await proposed(client, document["id"])
        assert policy["status"] == "draft" and len(policy["requirements"]) == 2
        bad = copy.deepcopy(policy["requirements"])
        bad[0]["source"]["quote"] = "invented policy sentence"
        assert (
            await client.put(
                f"/api/policies/{policy['id']}/requirements", json={"requirements": bad}
            )
        ).status_code == 422
        bad = copy.deepcopy(policy["requirements"])
        bad[0]["operator"] = "exec"
        assert (
            await client.put(
                f"/api/policies/{policy['id']}/requirements", json={"requirements": bad}
            )
        ).status_code == 422
        assert (await client.post(f"/api/policies/{policy['id']}/approve")).status_code == 403
        await login(client, "foreign")
        assert (await client.get(f"/api/policies/{policy['id']}")).status_code == 404
        await login(client, "reviewer")
        approved = await client.post(f"/api/policies/{policy['id']}/approve")
        assert approved.status_code == 200, approved.text
        assert (
            await client.put(
                f"/api/policies/{policy['id']}/requirements",
                json={"requirements": policy["requirements"]},
            )
        ).status_code == 409
        clone = await client.post(f"/api/policies/{policy['id']}/clone")
        assert clone.status_code == 201
        assert clone.json()["status"] == "draft" and clone.json()["version"] == 2
        assert (await client.delete(f"/api/documents/{document['id']}")).status_code == 409


async def test_run_snapshot_version_scope_and_immutable_decision(domain_setup, client_factory):
    settings, engine = domain_setup
    async with client_factory(settings) as client:
        await login(client)
        created = await case(client)
        document = await upload(client)
        policy = await proposed(client, document["id"])
        body = {"policy_version_id": policy["id"], "retrieval_variant": "hybrid"}
        assert (await client.post(f"/api/cases/{created['id']}/runs", json=body)).status_code == 409
        old = await upload(client, EVIDENCE, "evidence.md", created["id"])
        latest = await upload(client, EVIDENCE + b" MFA is enabled.", "evidence.md", created["id"])
        await login(client, "reviewer")
        assert (await client.post(f"/api/policies/{policy['id']}/approve")).status_code == 200
        await login(client)
        response = await client.post(f"/api/cases/{created['id']}/runs", json=body)
        assert response.status_code == 201, response.text
        run = response.json()
        source_ids = {chunk["document_id"] for chunk in run["input_snapshot"]["chunks"]}
        assert latest["id"] in source_ids and old["id"] not in source_ids
        snapshot = run["input_snapshot"]
        await client.patch(
            f"/api/cases/{created['id']}", json={"relationship": {"personal_data": False}}
        )
        await upload(client, EVIDENCE + b" MFA is disabled.", "evidence.md", created["id"])
        assert (await client.get(f"/api/runs/{run['id']}")).json()["input_snapshot"] == snapshot
        assert (await client.delete(f"/api/documents/{latest['id']}")).status_code == 409
        assert (await client.delete(f"/api/documents/{old['id']}")).status_code == 200
        decision = {
            "decision": "needs_information",
            "rationale": "Please provide current evidence.",
        }
        assert (
            await client.post(f"/api/runs/{run['id']}/decision", json=decision)
        ).status_code == 403
        await login(client, "reviewer")
        assert (
            await client.post(f"/api/runs/{run['id']}/decision", json=decision)
        ).status_code == 409
        from counterparty.worker import process_one, setup_checkpoints

        setup_checkpoints(engine)
        assert process_one(engine, settings)
        completed = await client.post(f"/api/runs/{run['id']}/decision", json=decision)
        assert completed.status_code == 201, completed.text
        assert completed.json()["decision"]["decision"] == "needs_information"
        assert (
            await client.post(f"/api/runs/{run['id']}/decision", json=decision)
        ).status_code == 409
        assert process_one(engine, settings)
        assert (await client.get(f"/api/runs/{run['id']}")).json()["report"]["workflow_complete"]
        await login(client, "foreign")
        assert (await client.get(f"/api/runs/{run['id']}")).status_code == 404
        assert (await client.get("/api/audit")).json()[0]["event"] == "auth.login"


async def test_explicit_bootstrap_is_idempotent(database_url, migration_config, tmp_path):
    command.upgrade(migration_config, "head")
    settings = Settings(database_url=database_url, storage_path=str(tmp_path / "storage"))
    engine = create_engine_for_settings(settings)
    fixtures = Path("/datasets/synthetic")
    if not fixtures.exists():
        fixtures = Path(__file__).resolve().parents[2] / "datasets" / "synthetic"
    try:
        first = bootstrap(engine, settings, fixtures)
        assert first == {"users": 5, "policies": 2, "cases": 5, "documents": 7}
        assert bootstrap(engine, settings, fixtures) == {
            "users": 0,
            "policies": 0,
            "cases": 0,
            "documents": 0,
        }
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(PolicySetVersion)) == 2
            assert session.scalar(select(func.count()).select_from(AssessmentCase)) == 5
            assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 0
    finally:
        engine.dispose()


async def test_ingestion_concurrency_and_transactional_file_cleanup(domain_setup):
    from concurrent.futures import ThreadPoolExecutor

    from counterparty.documents import ingest

    settings, engine = domain_setup

    def insert_same():
        with Session(engine) as session, session.begin():
            user = session.scalar(select(User).where(User.email == "analyst@example.test"))
            document, created = ingest(
                session, user, POLICY, "concurrent.md", "policy", None, settings.storage_path
            )
            return document.id, created

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: insert_same(), range(2)))
    assert results[0][0] == results[1][0]
    assert sum(created for _, created in results) == 1
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "analyst@example.test"))
        document, _ = ingest(
            session,
            user,
            POLICY + b"Rollback example",
            "rollback.md",
            "policy",
            None,
            settings.storage_path,
        )
        path = Path(settings.storage_path) / document.storage_key
        assert path.is_file()
        session.rollback()
        assert not path.exists()


async def test_evidence_provenance_and_cross_scope_dedup(domain_setup, client_factory):
    settings, _ = domain_setup
    async with client_factory(settings) as client:
        await login(client)
        first_case = await case(client)
        first_document = await upload(client, EVIDENCE, "evidence.md", first_case["id"])
        second_case = await case(client)
        response = await client.post(
            "/api/documents",
            files={"file": ("review.md", EVIDENCE)},
            data={"kind": "evidence", "case_id": second_case["id"], "evidence_type": "independent"},
        )
        assert response.status_code == 201
        document = response.json()
        assert document["id"] != first_document["id"]
        assert document["evidence_type"] == "independent"
        detail = (await client.get(f"/api/documents/{document['id']}")).json()
        assert all(chunk["evidence_type"] == "independent" for chunk in detail["chunks"])


async def test_policy_mode_uses_app_settings_and_model_errors_are_json(
    domain_setup, client_factory, monkeypatch
):
    settings, engine = domain_setup
    monkeypatch.setenv("MODEL_MODE", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings.model_mode = "demo"
    async with client_factory(settings) as client:
        await login(client)
        document = await upload(client)
        policy = await proposed(client, document["id"])
        assert policy["requirements"]
    settings.model_mode = "gemini"
    monkeypatch.setenv("MODEL_MODE", "demo")
    async with client_factory(settings) as client:
        await login(client)
        response = await client.post(
            "/api/policies/propose",
            json={"name": "Must not silently fall back", "document_ids": [document["id"]]},
        )
        assert response.status_code == 503
        assert response.headers["content-type"] == "application/json"
        assert "GEMINI_API_KEY missing" in response.json()["detail"]
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(PolicySetVersion)) == 1


async def test_pgvector_search_is_scoped_versioned_and_matches_local_cosine(
    domain_setup, client_factory
):
    from counterparty.analysis import embed_text

    settings, _ = domain_setup
    async with client_factory(settings) as client:
        await login(client)
        created = await case(client)
        document = await upload(client)
        policy = await proposed(client, document["id"])
        previous = await upload(client, EVIDENCE, "evidence.md", created["id"])
        current = await upload(client, EVIDENCE + b" MFA enabled.", "evidence.md", created["id"])
        other_case = await case(client)
        unrelated = await upload(client, EVIDENCE, "other.md", other_case["id"])
        await login(client, "reviewer")
        assert (await client.post(f"/api/policies/{policy['id']}/approve")).status_code == 200
        run = (
            await client.post(
                f"/api/cases/{created['id']}/runs",
                json={"policy_version_id": policy["id"], "retrieval_variant": "hybrid"},
            )
        ).json()
        snapshot = run["input_snapshot"]
        scores = snapshot["retrieval_scores"]
        assert snapshot["retrieval_config"]["backend"] == "pgvector-exact"
        evidence = [chunk for chunk in snapshot["chunks"] if chunk["kind"] == "evidence"]
        assert {chunk["document_id"] for chunk in evidence} == {current["id"]}
        for requirement in snapshot["requirements"]:
            query = embed_text(requirement["title"] + " " + requirement["field"])
            assert set(scores[requirement["id"]]) == {chunk["id"] for chunk in evidence}
            for chunk in evidence:
                expected = sum(a * b for a, b in zip(query, embed_text(chunk["text"]), strict=True))
                assert scores[requirement["id"]][chunk["id"]] == pytest.approx(expected, abs=1e-6)
        for excluded in (previous, unrelated, document):
            details = (await client.get(f"/api/documents/{excluded['id']}")).json()
            assert all(
                chunk["id"] not in req_scores
                for chunk in details["chunks"]
                for req_scores in scores.values()
            )
        await upload(client, EVIDENCE + b" Changed new version.", "evidence.md", created["id"])
        assert (await client.get(f"/api/runs/{run['id']}")).json()["input_snapshot"] == snapshot
