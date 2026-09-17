"""Offline model contract tests; no artifact downloads or paid provider calls."""

import hashlib

import httpx
import pytest


def test_every_window_keeps_prefix_and_complete_token_coverage():
    from counterparty.embeddings import token_windows

    source = list(range(20, 2820))
    windows = token_windows(source, [7, 8], start_id=0, end_id=2)
    assert len(windows) > 5
    assert all(window[:3] == [0, 7, 8] and window[-1] == 2 for window in windows)
    assert all(len(window) <= 512 for window in windows)
    assert set(source) == {token for window in windows for token in window[3:-1]}
    assert windows[-1][-2] == source[-1]


def test_cache_checks_integrity_then_works_without_network(tmp_path):
    from counterparty.embeddings import ensure_artifact

    content = b"synthetic artifact"
    spec = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    calls = []

    def fetch(request):
        calls.append(request.url)
        return httpx.Response(200, content=content)

    with httpx.Client(transport=httpx.MockTransport(fetch)) as client:
        path = ensure_artifact(tmp_path, "model.onnx", spec, client)
        assert path.read_bytes() == content
        ensure_artifact(tmp_path, "model.onnx", spec, client)
        assert len(calls) == 1
        path.write_bytes(b"corrupt")
        ensure_artifact(tmp_path, "model.onnx", spec, client)
        assert len(calls) == 2


def test_bad_download_cannot_be_published(tmp_path):
    from counterparty.embeddings import EmbeddingError, ensure_artifact

    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"bad"))
        ) as client,
        pytest.raises(EmbeddingError),
    ):
        ensure_artifact(tmp_path, "model.onnx", {"bytes": 3, "sha256": "0" * 64}, client)
    assert not (tmp_path / "model.onnx").exists()
    assert not list(tmp_path.glob("*.part"))


def test_runtime_hybrid_requires_complete_scores_and_never_hashes(monkeypatch):
    from counterparty.analysis.retrieval import retrieve

    def forbidden(*args):
        raise AssertionError("hash embedder called")

    monkeypatch.setattr("counterparty.analysis.engine.embed_text", forbidden)
    chunks = [{"id": "a", "text": "Multifactor access"}, {"id": "b", "text": "Holiday plans"}]
    assert retrieve("access", chunks, semantic_scores={"a": 0.9, "b": 0.1})[0]["id"] == "a"
    with pytest.raises(ValueError, match="complete"):
        retrieve("access", chunks, semantic_scores={"a": 0.9})


def _probe_child(pipe):
    import os
    import time

    loads = 0
    while True:
        command = pipe.recv()
        if command == "hang":
            time.sleep(30)
        elif command == "die":
            return
        elif command == "prepare":
            loads += 1
            pipe.send((os.getpid(), loads))
        else:
            pipe.send((os.getpid(), loads))


def test_supervisor_reuses_child_and_enforces_deadline():
    import time

    from counterparty.worker import ChildSupervisor

    supervisor = ChildSupervisor(_probe_child)
    try:
        prepared = supervisor.command("prepare", 5)
        assert prepared[1] == 1
        assert supervisor.command("work", 5) == prepared
        assert supervisor.command("work", 5) == prepared
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            supervisor.command("hang", 0.1)
        assert time.monotonic() - start < 6
        assert not supervisor.process.is_alive()
    finally:
        supervisor.close()
    replacement = ChildSupervisor(_probe_child)
    try:
        assert replacement.command("prepare", 5)[0] != prepared[0]
        with pytest.raises(EOFError):
            replacement.command("die", 5)
    finally:
        replacement.close()


def test_api_import_never_loads_native_model_runtime():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import counterparty.main, sys; "
            "assert 'onnxruntime' not in sys.modules; "
            "assert 'tokenizers' not in sys.modules",
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr.decode()


def test_runtime_has_no_retrieval_switches():
    from uuid import uuid4

    from pydantic import ValidationError

    from counterparty.analysis.retrieval import retrieve
    from counterparty.schemas import RunCreate

    assert "retrieval_variant" not in RunCreate.model_fields
    for variant in ("lexical", "semantic", "hybrid"):
        with pytest.raises(ValidationError):
            RunCreate(policy_version_id=uuid4(), retrieval_variant=variant)
        with pytest.raises(TypeError):
            retrieve("query", [], variant=variant, semantic_scores={})
    with pytest.raises(TypeError):
        retrieve("query", [], algorithm="e5-v1", semantic_scores={})
    with pytest.raises(TypeError):
        retrieve("query", [])


def test_hybrid_combines_keywords_and_ranks_negative_cosines():
    from counterparty.analysis.retrieval import retrieve

    chunks = [
        {"id": "relevant", "text": "Wymagamy dodatkowego czynnika logowania."},
        {"id": "distractor", "text": "MFA MFA marketing MFA"},
    ]
    assert (
        retrieve("MFA", chunks, top_k=1, semantic_scores={"relevant": 0.9, "distractor": 0.7})[0][
            "id"
        ]
        == "distractor"
    )
    assert [
        c["id"]
        for c in retrieve("query", chunks, semantic_scores={"relevant": -0.1, "distractor": -0.9})
    ] == ["relevant", "distractor"]
