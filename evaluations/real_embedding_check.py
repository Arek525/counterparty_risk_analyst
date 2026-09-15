"""Opt-in real-model + disposable PostgreSQL check; never part of routine pytest."""

import argparse
import json
import os
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from counterparty.config import Settings
from counterparty.documents import chunk_dict, ingest
from counterparty.embedding_config import CONFIG, FINGERPRINT, requirement_query
from counterparty.embeddings import LocalEmbedder, validate_vectors
from counterparty.indexing import index_one, prepare_retrieval
from counterparty.models import (
    AnalysisRun,
    AssessmentCase,
    DocumentChunk,
    PolicySetVersion,
    User,
)
from counterparty.organizations import Organization
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True)
    args = parser.parse_args()
    # Verified cache must work even when all HTTP streaming is forbidden.
    with patch(
        "httpx.Client.stream",
        side_effect=AssertionError("Unexpected cache network call"),
    ):
        model = LocalEmbedder(args.cache)
    assert model.pad_id == 1
    text = "Przywracanie kopii zapasowych. " * 220 + " SANCTIONS UNIQUE TAIL"
    content = model.tokenizer.encode(text, add_special_tokens=False).ids
    windows = model.windows(text, "passage")
    prefix = model.prefixes["passage"]
    capacity = 512 - len(prefix) - 2
    step = capacity - CONFIG["window_overlap"]
    recovered = []
    for index, window in enumerate(windows):
        assert window[: 1 + len(prefix)] == [model.start_id, *prefix]
        assert window[-1] == model.end_id
        part = window[1 + len(prefix) : -1]
        assert part == content[index * step : index * step + capacity]
        recovered.extend(part if index == 0 else part[CONFIG["window_overlap"] :])
    assert recovered == content
    # The short-input tokenization equals the pinned tokenizer's full role-prefixed sequence.
    for role in ("query", "passage"):
        for value in (
            "MFA is enabled",
            "Wymagamy drugiego czynnika logowania.",
            "  leading whitespace",
            "\nZażółć gęślą jaźń!",
            "...!?  MFA: tak.",
        ):
            assert (
                model.windows(value, role)[0]
                == model.tokenizer.encode(f"{role}: {value}").ids
            )
    values = model.embed([text, "MFA is enabled"], "passage")
    validate_vectors(values, 2)
    admin_url = os.environ["TEST_DATABASE_ADMIN_URL"]
    name = "test_counterparty_real_embeddings_" + uuid4().hex
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    engine = None
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
        url = (
            make_url(admin_url).set(database=name).render_as_string(hide_password=False)
        )
        cfg = Config("/app/alembic.ini")
        cfg.attributes["database_url"] = url
        command.upgrade(cfg, "head")
        settings = Settings(
            database_url=url, storage_path="/tmp/real-embedding-evidence"
        )
        engine = create_engine(url)
        with Session(engine) as session:
            org = Organization(
                name="Synthetic real model check",
                slug="real-embedding-check",
                is_synthetic=True,
            )
            session.add(org)
            session.flush()
            user = User(
                organization_id=org.id,
                name="Synthetic reviewer",
                email=name + "@example.test",
                password_hash="not-a-login",
                role="reviewer",
            )
            session.add(user)
            session.flush()
            case = AssessmentCase(
                organization_id=org.id,
                owner_id=user.id,
                name="Synthetic",
                counterparty_name="Synthetic",
                relationship={},
            )
            policy = PolicySetVersion(
                organization_id=org.id,
                created_by=user.id,
                name="Synthetic",
                version=1,
                status="approved",
                document_ids=[],
                requirements=[],
            )
            session.add_all([case, policy])
            session.flush()
            doc, _ = ingest(
                session,
                user,
                "Każdy administrator musi używać drugiego czynnika logowania.".encode(),
                "proof.txt",
                "evidence",
                case.id,
                settings.storage_path,
            )
            session.commit()
            doc_id, case_id, org_id, user_id, policy_id = (
                doc.id,
                case.id,
                org.id,
                user.id,
                policy.id,
            )
        assert index_one(engine, settings, model)
        with Session(engine) as session:
            from counterparty.models import Document

            chunk = session.scalar(
                select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
            )
            snapshot = {
                "chunks": [chunk_dict(chunk, session.get(Document, doc_id))],
                "requirements": [
                    {
                        "id": "mfa",
                        "title": "Require multi factor authentication",
                        "field": "mfa",
                    }
                ],
                "retrieval_config": CONFIG,
                "retrieval_fingerprint": FINGERPRINT,
            }
            run = AnalysisRun(
                organization_id=org_id,
                case_id=case_id,
                created_by=user_id,
                policy_version_id=policy_id,
                input_snapshot=snapshot,
                status="running",
                lease_owner="real-check",
                retrieval_variant="semantic",
            )
            session.add(run)
            session.commit()
            run_id, chunk_id, stored = run.id, str(chunk.id), list(chunk.embedding)
        query = model.embed([requirement_query(snapshot["requirements"][0])], "query")[
            0
        ]
        expected = sum(a * b for a, b in zip(query, stored, strict=True))
        with engine.connect() as owner:
            actual = prepare_retrieval(
                engine, run_id, "real-check", snapshot, model, owner
            )
        score = actual["scores"]["mfa"][chunk_id]
        assert abs(score - expected) < 1e-6, (score, expected)
        print(
            json.dumps(
                {
                    "offline_cache": True,
                    "pad_id": model.pad_id,
                    "covered_tokens": len(content),
                    "windows": len(windows),
                    "dimension": len(stored),
                    "pgvector_cosine": score,
                    "direct_cosine": expected,
                    "absolute_error": abs(score - expected),
                }
            )
        )
    finally:
        if engine:
            engine.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.dispose()


if __name__ == "__main__":
    main()
