"""Durable, bounded analysis execution with PostgreSQL and LangGraph checkpoints."""

import hashlib
import logging
import multiprocessing
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import TypedDict
from uuid import UUID, uuid4

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
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
    needs_embeddings,
    prepare_retrieval,
    set_model_state,
)
from counterparty.models import AnalysisRun, AuditEvent, Decision, Document

logger = logging.getLogger(__name__)


class AnalysisState(TypedDict, total=False):
    run_id: str
    snapshot: dict
    variant: str
    report: dict
    decision: dict


def lock_key(run_id: UUID) -> int:
    return int.from_bytes(
        hashlib.blake2b(str(run_id).encode(), digest_size=8).digest(), signed=True
    )


@contextmanager
def checkpointer(engine: Engine):
    params = engine.url.translate_connect_args(username="user", database="dbname")
    with psycopg.connect(
        **params,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        connect_timeout=3,
        options="-c statement_timeout=10000",
    ) as connection:
        yield PostgresSaver(connection)


def setup_checkpoints(engine: Engine) -> None:
    with checkpointer(engine) as saver:
        # The library owns its schema. Serialize its setup across starting workers.
        saver.conn.execute("SELECT pg_advisory_lock(471932841)")
        try:
            saver.setup()
        finally:
            saver.conn.execute("SELECT pg_advisory_unlock(471932841)")


def build_graph(saver):
    def assess(state: AnalysisState):
        from counterparty.analysis import analyze

        report = analyze(state["snapshot"], state["variant"])
        return {"report": report}

    def review(state: AnalysisState):
        decision = interrupt({"run_id": state["run_id"], "action": "review_report"})
        return {"decision": decision}

    graph = StateGraph(AnalysisState)
    graph.add_node("assess", assess)
    graph.add_node("review", review)
    graph.add_edge(START, "assess")
    graph.add_edge("assess", "review")
    graph.add_edge("review", END)
    return graph.compile(checkpointer=saver)


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
        and_(
            AnalysisRun.status == "completed",
            AnalysisRun.report.is_not(None),
            AnalysisRun.report["workflow_error"].astext.is_(None),
            or_(
                AnalysisRun.report["workflow_complete"].astext.is_(None),
                AnalysisRun.report["workflow_complete"].astext != "true",
            ),
        ),
    )


def process_one(engine: Engine, settings: Settings, model=None) -> bool:
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
        with checkpointer(engine) as saver:
            # The checkpoint writer and ownership lock share one physical session.
            # Losing ownership therefore also prevents stale checkpoint writes.
            owner = saver.conn
            key = lock_key(run_id)
            acquired = owner.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired", (key,)
            ).fetchone()["acquired"]
            if not acquired:
                continue
            try:
                if _execute_claim(engine, settings, run_id, saver, model):
                    return True
            finally:
                if not owner.closed and not owner.broken:
                    owner.execute("SELECT pg_advisory_unlock(%s)", (key,))
    return False


def _execute_claim(engine, settings, run_id, saver, model=None):
    owner = saver.conn
    with Session(engine) as session:
        run = session.scalar(
            select(AnalysisRun)
            .where(AnalysisRun.id == run_id, _eligible(datetime.now(UTC)))
            .with_for_update(skip_locked=True)
        )
        if run is None or (model is None and needs_embeddings(run)):
            return False
        decision = session.scalar(select(Decision).where(Decision.run_id == run_id))
        attempt_limit = settings.worker_max_attempts + (3 if decision else 0)
        if run.attempts >= attempt_limit:
            run.status = "failed" if not decision else "completed"
            run.error = "Execution attempt limit exceeded; create a new analysis to retry."
            if decision:
                run.report = {**run.report, "workflow_complete": False, "workflow_error": run.error}
            _event(session, run, "run.failed", {"reason": "attempt_limit"})
            session.commit()
            return True
        run.attempts += 1
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
        claim_token = f"{os.getpid()}-{uuid4().hex}"
        run.lease_owner = claim_token
        run.lease_expires_at = datetime.now(UTC) + timedelta(seconds=settings.worker_lease_seconds)
        snapshot, variant = run.input_snapshot, run.retrieval_variant
        retrieval = run.retrieval_snapshot
        decision_data = (
            {
                "decision": decision.decision,
                "rationale": decision.rationale,
                "actor_id": str(decision.actor_id),
            }
            if decision
            else None
        )
        _event(session, run, "run.started", {"attempt": run.attempts, "model_mode": run.model_mode})
        session.commit()
    started = time.monotonic()
    try:
        graph = build_graph(saver)
        config = {"configurable": {"thread_id": str(run_id)}, "recursion_limit": 8}
        state = graph.get_state(config)
        if not state.values:
            if (
                variant in {"hybrid", "semantic"}
                and snapshot.get("requirements")
                and any(chunk.get("kind") == "evidence" for chunk in snapshot["chunks"])
                and "retrieval_config" not in snapshot
                and "retrieval_scores" not in snapshot
            ):
                raise EmbeddingError(
                    "Run retrieval configuration is missing. Create a new analysis."
                )
            if (
                variant in {"hybrid", "semantic"}
                and "retrieval_config" in snapshot
                and "retrieval_scores" not in snapshot
            ):
                retrieval = retrieval or prepare_retrieval(
                    engine, run_id, claim_token, snapshot, model, owner
                )
                snapshot = {
                    **snapshot,
                    "retrieval_scores": retrieval["scores"],
                    "retrieval_algorithm": retrieval["config"]["retrieval"],
                }
            result = graph.invoke(
                {"run_id": str(run_id), "snapshot": snapshot, "variant": variant}, config
            )
        elif state.next and decision_data:
            result = graph.invoke(Command(resume=decision_data), config)
        elif state.next and not state.tasks:
            result = graph.invoke(None, config)
        elif state.next and any(task.interrupts for task in state.tasks):
            result = state.values
        elif state.next:
            result = graph.invoke(None, config)
        else:
            result = state.values
        # Crash after initial graph completion but before its DB report write
        # can leave a decision waiting; resume exactly that checkpoint.
        current = graph.get_state(config)
        if decision_data and current.next:
            result = graph.invoke(Command(resume=decision_data), config)
        finished = not graph.get_state(config).next
        owner.execute("SELECT 1")  # Do not persist after losing the exclusive DB session.
        with Session(engine) as session:
            run = session.scalar(
                select(AnalysisRun).where(AnalysisRun.id == run_id).with_for_update()
            )
            if run.lease_owner != claim_token or run.status != "running":
                return True
            run.report = {
                **(run.report if decision_data else result["report"]),
                "workflow_version": "assessment-v1",
                "workflow_complete": finished,
            }
            run.status = "completed" if finished else "awaiting_review"
            run.error = None
            run.finished_at = datetime.now(UTC)
            run.lease_owner = None
            run.lease_expires_at = None
            _event(
                session,
                run,
                "run.completed" if finished else "run.awaiting_review",
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
            if decision_data and run.status == "failed":
                run.status = "completed"
                run.report = {**run.report, "workflow_complete": False, "workflow_error": run.error}
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
                if process_one(engine, settings, model) or index_one(engine, settings, model):
                    pipe.send("worked")
                else:
                    with Session(engine) as session:
                        pending = session.scalar(
                            select(Document.id).where(index_eligible(datetime.now(UTC))).limit(1)
                        )
                        semantic = any(
                            needs_embeddings(run)
                            for run in session.scalars(
                                select(AnalysisRun).where(_eligible(datetime.now(UTC)))
                            )
                        )
                    pipe.send("needs_model" if model is None and (pending or semantic) else "idle")
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
        try:
            self.pipe.send(command)
            while remaining := max(0, deadline - time.monotonic()):
                if self.pipe.poll(min(remaining, 5)):
                    return self.pipe.recv()
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
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    engine = create_engine_for_settings(settings)
    setup_checkpoints(engine)
    child = None
    state, error, retry_after = "pending", None, 0
    try:
        while True:
            try:
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
