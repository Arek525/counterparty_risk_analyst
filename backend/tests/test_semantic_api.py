"""API extraction cache, full source view and narrative version lifecycle."""

# ruff: noqa: F811 -- pytest injects the imported shared fixture by parameter name.

from uuid import UUID

import pytest
from sqlalchemy.orm import Session
from test_domain import domain_setup, login, upload  # noqa: F401 -- shared real-DB fixture

from counterparty.analysis.adapters import ModelError
from counterparty.models import AnalysisRun

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_full_text_cached_extraction_and_explicit_regeneration(
    domain_setup, client_factory, monkeypatch
):
    settings, _ = domain_setup
    calls = []

    def extract(chunks, **kwargs):
        calls.append(chunks)
        c = chunks[0]
        return [
            {
                "id": "CUSTOM-1",
                "title": "Support access",
                "description": "Support access must be approved for each incident.",
                "applicability_text": "When support can access customer data",
                "severity": "High",
                "source": {
                    "document_id": c["document_id"],
                    "chunk_id": c["id"],
                    "location": c["location"],
                    "quote": c["text"][:70],
                },
            }
        ]

    monkeypatch.setattr("counterparty.analysis.semantic.propose_narrative_requirements", extract)
    async with client_factory(settings) as client:
        await login(client)
        original = (
            "Support must be approved for each incident. " * 80
            + "\nFinal exception remains visible."
        ).encode()
        document = await upload(client, original)
        detail = (await client.get(f"/api/documents/{document['id']}")).json()
        assert detail["text"] == original.decode()
        assert len(detail["chunks"]) > 1
        body = {"name": "Narrative policy", "document_ids": [document["id"]]}
        first = (await client.post("/api/policies/propose", json=body)).json()
        second = (
            await client.post("/api/policies/propose", json={**body, "name": "Different label"})
        ).json()
        assert first["id"] == second["id"] and len(calls) == 1
        assert first["extraction_status"] == "ready"
        req = first["requirements"][0]
        assert "description" in req and "operator" not in req
        req["description"] += " Emergency access also requires review."
        edited = await client.put(
            f"/api/policies/{first['id']}/requirements", json={"requirements": [req]}
        )
        assert edited.status_code == 404, edited.text
        stored = (await client.get(f"/api/policies/{first['id']}")).json()
        assert stored["requirements"][0]["description"] == (
            "Support access must be approved for each incident."
        )
        await login(client, "reviewer")
        approved = await client.post(f"/api/policies/{first['id']}/approve")
        assert approved.status_code == 200
        assert approved.json()["requirement_index_status"] == "pending"
        assert (
            await client.put(
                f"/api/policies/{first['id']}/requirements", json={"requirements": [req]}
            )
        ).status_code == 404
        regenerated = (
            await client.post("/api/policies/propose", json={**body, "regenerate": True})
        ).json()
        assert regenerated["id"] != first["id"] and regenerated["version"] == 2
        assert len(calls) == 2
        await login(client, "foreign")
        assert (await client.get(f"/api/policies/{first['id']}")).status_code == 404


async def test_failed_extraction_is_saved_not_silently_retried(
    domain_setup, client_factory, monkeypatch
):
    settings, _ = domain_setup
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise ModelError("Gemini quota exhausted; stopped without fallback")

    monkeypatch.setattr("counterparty.analysis.semantic.propose_narrative_requirements", fail)
    async with client_factory(settings) as client:
        await login(client)
        doc = await upload(client)
        body = {"name": "Failed extraction", "document_ids": [doc["id"]]}
        first = (await client.post("/api/policies/propose", json=body)).json()
        assert first["extraction_status"] == "error"
        assert first["requirements"] == []
        again = (await client.post("/api/policies/propose", json=body)).json()
        assert first["id"] == again["id"] and len(calls) == 1
        await login(client, "reviewer")
        assert (await client.post(f"/api/policies/{first['id']}/approve")).status_code == 409


async def test_retry_preserves_completed_steps_and_blocks_completed_reports(
    domain_setup, client_factory
):
    from test_domain import case, proposed

    settings, engine = domain_setup
    async with client_factory(settings) as client:
        await login(client, "reviewer")
        doc = await upload(client)
        policy = await proposed(client, doc["id"])
        assert (await client.post(f"/api/policies/{policy['id']}/approve")).status_code == 200
        relationship = await case(client)
        response = await client.post(
            f"/api/cases/{relationship['id']}/runs",
            json={"policy_version_id": policy["id"], "retrieval_variant": "lexical"},
        )
        assert response.status_code == 201, response.text
        run_id = response.json()["id"]
        with Session(engine) as session:
            run = session.get(AnalysisRun, UUID(run_id))
            run.status = "failed"
            run.assessment_progress = {
                "completed": 1,
                "completed_ids": ["done"],
                "attempts": {"done": 3, "next": 1},
                "findings": [{"requirement_id": "done"}],
            }
            session.commit()
        resumed = await client.post(f"/api/runs/{run_id}/retry")
        assert resumed.status_code == 200 and resumed.json()["progress"]["completed"] == 1
        assert (await client.post(f"/api/runs/{run_id}/retry")).status_code == 409
        with Session(engine) as session:
            run = session.get(AnalysisRun, UUID(run_id))
            assert run.assessment_progress["findings"] == [{"requirement_id": "done"}]
