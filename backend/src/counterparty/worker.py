"""Durable, bounded analysis execution with PostgreSQL progress records."""

import copy
import hashlib
import logging
import multiprocessing
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import Engine, and_, or_, select
from sqlalchemy.orm import Session

from counterparty.analysis.adapters import ModelError
from counterparty.config import Settings
from counterparty.database import create_engine_for_settings
from counterparty.embeddings import EmbeddingError
from counterparty.indexing import (
    index_eligible,
    index_one,
    index_policy_one,
    needs_embeddings,
    policy_index_eligible,
    prepare_retrieval,
    set_model_state,
)
from counterparty.models import AnalysisRun, AuditEvent, Document, PolicySetVersion

logger = logging.getLogger(__name__)


def lock_key(run_id: UUID) -> int:
    return int.from_bytes(
        hashlib.blake2b(str(run_id).encode(), digest_size=8).digest(), signed=True
    )


@contextmanager
def ownership_connection(engine: Engine):
    params = engine.url.translate_connect_args(username="user", database="dbname")
    with psycopg.connect(
        **params,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        connect_timeout=3,
        options="-c statement_timeout=10000",
    ) as connection:
        yield connection


def _event(session, run, event, details=None):
    session.add(
        AuditEvent(
            organization_id=run.organization_id,
            case_id=run.case_id,
            run_id=run.id,
            actor_id=None,
            event=event,
            details=details or {},
        )
    )


def _eligible(now):
    return or_(
        AnalysisRun.status == "queued",
        and_(
            AnalysisRun.status == "running",
            or_(AnalysisRun.lease_expires_at < now, AnalysisRun.lease_expires_at.is_(None)),
        ),
    )


def process_one(engine: Engine, settings: Settings, model=None, heartbeat=None) -> bool:
    """Claim one eligible job; return False if no job can be exclusively claimed."""
    with Session(engine) as session:
        candidates = list(
            session.scalars(
                select(AnalysisRun.id)
                .where(_eligible(datetime.now(UTC)))
                .order_by(AnalysisRun.created_at)
            )
        )
    for run_id in candidates:
        with ownership_connection(engine) as owner:
            key = lock_key(run_id)
            acquired = owner.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired", (key,)
            ).fetchone()["acquired"]
            if not acquired:
                continue
            try:
                if _execute_claim(engine, settings, run_id, owner, model, heartbeat):
                    return True
            finally:
                if not owner.closed and not owner.broken:
                    owner.execute("SELECT pg_advisory_unlock(%s)", (key,))
    return False


MAX_REQUIREMENT_ATTEMPTS = 3


def _publish_progress(engine, settings, run_id, token, owner, progress):
    owner.execute("SELECT 1")
    with Session(engine) as session:
        run = session.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id).with_for_update())
        if run.lease_owner != token or run.status != "running":
            raise EmbeddingError("Analysis ownership changed before assessment publication")
        run.assessment_progress = copy.deepcopy(progress)
        run.lease_expires_at = datetime.now(UTC) + timedelta(seconds=settings.worker_lease_seconds)
        owner.execute("SELECT 1")
        session.commit()


def assess_sequential(engine, settings, run_id, token, owner, snapshot, heartbeat=None):
    from counterparty.analysis.semantic import assess_requirement, build_report

    with Session(engine) as session:
        progress = copy.deepcopy(session.get(AnalysisRun, run_id).assessment_progress) or {
            "version": "semantic-v2",
            "total": len(snapshot["requirements"]),
            "completed": 0,
            "completed_ids": [],
            "findings": [],
            "attempts": {},
            "metrics": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": None},
        }
    for requirement in snapshot["requirements"]:
        requirement_id = requirement["id"]
        if requirement_id in progress["completed_ids"]:
            continue
        expected_model = snapshot.get("model_name")
        if (
            snapshot.get("model_mode") == "gemini"
            and expected_model
            and expected_model != os.getenv("GEMINI_MODEL", "")
            and any(
                chunk.get("kind") == "evidence" and chunk.get("text", "").strip()
                for chunk in snapshot["chunks"]
            )
        ):
            raise ModelError(
                "Configured model differs from this analysis snapshot. Restore its model to resume."
            )
        attempts = progress["attempts"].get(requirement_id, 0)
        if attempts >= MAX_REQUIREMENT_ATTEMPTS:
            raise ModelError("Requirement attempt limit exceeded; create a new analysis to retry.")
        progress["current_requirement_id"] = requirement_id
        progress["attempts"][requirement_id] = attempts + 1
        _publish_progress(engine, settings, run_id, token, owner, progress)
        if heartbeat:
            heartbeat()
        try:
            finding = assess_requirement(
                requirement,
                snapshot["chunks"],
                snapshot["case"]["relationship"],
                mode=snapshot.get("model_mode", "demo"),
                semantic_scores=snapshot.get("retrieval_scores", {}).get(requirement_id),
                metrics=progress["metrics"],
            )
        except Exception:
            _publish_progress(engine, settings, run_id, token, owner, progress)
            raise
        progress["findings"].append(finding)
        progress["completed_ids"].append(requirement_id)
        progress["completed"] = len(progress["completed_ids"])
        progress["current_requirement_id"] = None
        _publish_progress(engine, settings, run_id, token, owner, progress)
        if heartbeat:
            heartbeat()
    report = build_report(
        progress["findings"], snapshot.get("model_mode", "demo"), progress["metrics"]
    )
    if snapshot.get("model_name"):
        report["model_name"] = snapshot["model_name"]
    return report


def _execute_claim(engine, settings, run_id, owner, model=None, heartbeat=None):
    with Session(engine) as session:
        run = session.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.id == run_id, _eligible(datetime.now(UTC)))
            .with_for_update(skip_locked=True)
        )
        if run is None or (model is None and needs_embeddings(run)):
            return False
        attempt_limit = settings.worker_max_attempts
        if run.attempts >= attempt_limit:
            run.status = "failed"
            run.error = "Execution attempt limit exceeded; create a new analysis to retry."
            _event(session, run, "run.failed", {"reason": "attempt_limit"})
            session.commit()
            return True
        run.attempts += 1
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
        claim_token = f"{os.getpid()}-{uuid4().hex}"
        run.lease_owner = claim_token
        run.lease_expires_at = datetime.now(UTC) + timedelta(seconds=settings.worker_lease_seconds)
        snapshot = run.input_snapshot
        retrieval = run.retrieval_snapshot
        _event(session, run, "run.started", {"attempt": run.attempts, "model_mode": run.model_mode})
        session.commit()
    started = time.monotonic()
    try:
        if (
            snapshot.get("requirements")
            and any(chunk.get("kind") == "evidence" for chunk in snapshot["chunks"])
            and "retrieval_config" not in snapshot
            and "retrieval_scores" not in snapshot
        ):
            raise EmbeddingError("Run retrieval configuration is missing. Create a new analysis.")
        if "retrieval_config" in snapshot and "retrieval_scores" not in snapshot:
            retrieval = retrieval or prepare_retrieval(
                engine, run_id, claim_token, snapshot, model, owner
            )
            snapshot = {
                **snapshot,
                "retrieval_scores": retrieval["scores"],
                "retrieval_algorithm": retrieval["config"]["retrieval"],
            }
        if snapshot.get("assessment_version") == "semantic-v2":
            report = assess_sequential(
                engine, settings, run_id, claim_token, owner, snapshot, heartbeat
            )
        else:
            from counterparty.analysis import analyze

            report = analyze(snapshot)
        owner.execute("SELECT 1")  # Do not persist after losing the exclusive DB session.
        with Session(engine) as session:
            run = session.scalar(
                select(AnalysisRun).where(AnalysisRun.id == run_id).with_for_update()
            )
            if run.lease_owner != claim_token or run.status != "running":
                return True
            run.report = {
                **report,
                "workflow_version": "assessment-v1",
                "workflow_complete": False,
            }
            run.status = "awaiting_review"
            run.error = None
            run.finished_at = datetime.now(UTC)
            run.lease_owner = None
            run.lease_expires_at = None
            _event(
                session,
                run,
                "run.awaiting_review",
                {
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "metrics": run.report.get("metrics", {}),
                },
            )
            session.commit()
    except Exception as error:
        # Do not persist arbitrary exception messages: providers may include prompts or keys.
        logger.warning("Analysis %s failed (%s)", run_id, type(error).__name__)
        if owner.closed or owner.broken:
            return True
        try:
            owner.execute("SELECT 1")
        except psycopg.Error:
            return True
        with Session(engine) as session:
            run = session.scalar(
                select(AnalysisRun).where(AnalysisRun.id == run_id).with_for_update()
            )
            if run.lease_owner != claim_token or run.status != "running":
                return True
            # The adapter already bounds transient retries. Never retry exhausted
            # quota, missing configuration or rejected output at the job layer.
            terminal = (
                isinstance(error, (ModelError, EmbeddingError)) or run.attempts >= attempt_limit
            )
            run.status = "failed" if terminal else "running"
            run.error = (
                str(error)
                if isinstance(error, (ModelError, EmbeddingError))
                else (
                    f"{type(error).__name__}: analysis could not finish. "
                    "Check provider configuration."
                )
            )
            run.lease_owner = None
            run.lease_expires_at = datetime.now(UTC) + timedelta(seconds=2**run.attempts)
            _event(
                session,
                run,
                "run.retry_scheduled" if run.status == "running" else "run.failed",
                {"error_type": type(error).__name__, "attempt": run.attempts},
            )
            session.commit()
    return True


def _child(pipe):
    settings = Settings()
    engine = create_engine_for_settings(settings)
    model = None
    try:
        while True:
            command = pipe.recv()
            if command == "prepare":
                try:
                    from counterparty.embeddings import LocalEmbedder

                    model = LocalEmbedder(settings.model_cache_path)
                    pipe.send("ready")
                except Exception:
                    model = None
                    pipe.send("model_error")
            elif command == "work":
                if (
                    process_one(engine, settings, model, heartbeat=lambda: pipe.send("progress"))
                    or index_one(engine, settings, model)
                    or index_policy_one(engine, model)
                ):
                    pipe.send("worked")
                else:
                    with Session(engine) as session:
                        pending = session.scalar(
                            select(Document.id).where(index_eligible(datetime.now(UTC))).limit(1)
                        )
                        policy_pending = session.scalar(
                            select(PolicySetVersion.id).where(policy_index_eligible()).limit(1)
                        )
                        semantic = any(
                            needs_embeddings(run)
                            for run in session.scalars(
                                select(AnalysisRun).where(_eligible(datetime.now(UTC)))
                            )
                        )
                    pipe.send(
                        "needs_model"
                        if model is None and (pending or semantic or policy_pending)
                        else "idle"
                    )
            elif command == "stop":
                break
            else:
                raise ValueError("Unknown worker command")
    except (EOFError, BrokenPipeError):
        pass
    finally:
        engine.dispose()
        pipe.close()


class ChildSupervisor:
    """One spawn child reuses its model; each command has a hard wall-clock budget."""

    def __init__(self, target=_child):
        context = multiprocessing.get_context("spawn")
        self.pipe, child_pipe = context.Pipe()
        self.process = context.Process(target=target, args=(child_pipe,))
        self.process.start()
        child_pipe.close()

    def command(self, command, timeout, heartbeat=None):
        deadline = time.monotonic() + timeout
        # At most 100 requirements, two progress notifications per requirement.
        absolute_deadline = time.monotonic() + timeout * 101
        try:
            self.pipe.send(command)
            while remaining := max(0, deadline - time.monotonic()):
                if self.pipe.poll(min(remaining, 5)):
                    result = self.pipe.recv()
                    if result == "progress":
                        deadline = min(time.monotonic() + timeout, absolute_deadline)
                        if heartbeat:
                            heartbeat()
                        continue
                    return result
                if heartbeat:
                    heartbeat()
            raise TimeoutError("Worker command deadline exceeded")
        except (EOFError, BrokenPipeError, OSError, TimeoutError):
            self.close()
            raise

    def close(self):
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(5)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(5)
        self.pipe.close()


def main():
    from counterparty.deletion import cleanup_files

    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    engine = create_engine_for_settings(settings)
    child = None
    state, error, retry_after = "pending", None, 0
    try:
        while True:
            try:
                cleanup_files(engine, settings.storage_path)
                if child is None:
                    child = ChildSupervisor()
                    state = "pending"
                set_model_state(engine, state, error)
                result = child.command(
                    "work",
                    settings.worker_max_runtime_seconds,
                    heartbeat=partial(set_model_state, engine, state, error),
                )
                if result == "needs_model" and time.monotonic() >= retry_after:
                    state, error = "preparing", None
                    set_model_state(engine, state)
                    result = child.command(
                        "prepare",
                        settings.model_prepare_timeout_seconds,
                        heartbeat=partial(set_model_state, engine, state),
                    )
                    state = "ready" if result == "ready" else "error"
                    error = (
                        None
                        if state == "ready"
                        else (
                            "Local model preparation failed; check network and cache space. "
                            "Retrying automatically."
                        )
                    )
                    retry_after = time.monotonic() + settings.model_retry_seconds
                    set_model_state(engine, state, error)
                if result != "worked":
                    time.sleep(settings.worker_poll_seconds)
            except (EOFError, BrokenPipeError, OSError, TimeoutError):
                if child:
                    child.close()
                child = None
                state, error = (
                    "error",
                    "Worker command stopped or exceeded its deadline; recovering.",
                )
                set_model_state(engine, state, error)
                retry_after = time.monotonic() + settings.model_retry_seconds
                logger.warning("Worker child stopped; leased work will recover")
                time.sleep(settings.worker_poll_seconds)
    finally:
        if child:
            child.close()
        engine.dispose()


if __name__ == "__main__":
    main()
