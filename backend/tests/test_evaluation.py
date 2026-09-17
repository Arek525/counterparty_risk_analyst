"""Evaluation accounting must not hide failed requests or replay completed steps."""

import importlib.util
from pathlib import Path

import pytest


def runner():
    path = Path("/evaluations/run.py")
    if not path.exists():
        path = Path(__file__).resolve().parents[2] / "evaluations/run.py"
    spec = importlib.util.spec_from_file_location("evaluation_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_usage_includes_thinking_and_does_not_invent_failed_call_tokens():
    m = runner()
    calls = [
        {
            "usage": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 10,
                "thoughtsTokenCount": 5,
                "cachedContentTokenCount": 20,
            }
        }
    ]
    assert m.usage(calls) == {
        "input_tokens": 100,
        "output_tokens": 15,
        "cached_tokens": 20,
        "thinking_tokens": 5,
        "requests": 1,
        "unknown_usage_requests": 0,
    }
    calls.append({"usage": None})
    assert m.usage(calls)["input_tokens"] is None
    assert m.usage(calls)["unknown_usage_requests"] == 1


def test_request_budget_is_durable_and_blocks_before_network(tmp_path):
    m = runner()
    path = tmp_path / "result.json"
    result = {"steps": {"x": {"requests": []}}}
    trace = m.Trace(result, path, result["steps"]["x"], 1)
    trace.reserve()
    assert path.exists()
    with pytest.raises(m.BudgetExceeded):
        trace.reserve()
    assert len(result["steps"]["x"]["requests"]) == 1


def test_case_corpus_validates_and_keeps_labels_out_of_model_requirements():
    m = runner()
    families = m.load_cases("development", [])
    assert len(families) == 6
    for family in families:
        chunks = m.chunks_for([family["policy"]["document"]])
        requirements = m.requirements_for(family["policy"], chunks)
        assert len(requirements) == 3
        assert all("components" not in r and "rationale" not in r for r in requirements)


@pytest.mark.parametrize("compressed", [False, True])
def test_capture_stream_records_usage_without_credentials(tmp_path, compressed):
    import json

    import httpx

    m = runner()
    result = {"steps": {"x": {"requests": []}}}
    path = tmp_path / "result.json"
    trace = m.Trace(result, path, result["steps"]["x"], 2)
    payload = {
        "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 3},
        "candidates": [{"content": {"parts": [{"text": "answer"}]}, "finishReason": "STOP"}],
    }
    import gzip

    body = json.dumps(payload).encode()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            stream=httpx.ByteStream(gzip.compress(body) if compressed else body),
            headers={"content-encoding": "gzip"} if compressed else {},
        )
    )
    with (
        httpx.Client(transport=transport) as client,
        trace.capture(),
        client.stream(
            "POST",
            "https://generativelanguage.googleapis.com/test",
            headers={"x-goog-api-key": "secret-test-value"},
        ) as response,
    ):
        response.read()
    stored = json.loads(path.read_text())
    assert stored["steps"]["x"]["requests"][0]["usage"] == payload["usageMetadata"]
    assert "secret-test-value" not in path.read_text()


def test_completed_step_is_not_replayed_even_with_retry(tmp_path):
    m = runner()
    result = {"steps": {"x": {"status": "completed", "output": 42, "requests": []}}}

    def forbidden():
        pytest.fail("Completed paid work must not be replayed")

    assert m.run_step(result, tmp_path / "r.json", "x", 1, forbidden, retry=True)["output"] == 42


def test_quota_failure_is_counted_and_captured(tmp_path):
    import json

    import httpx

    m = runner()
    result = {"steps": {"x": {"requests": []}}}
    trace = m.Trace(result, tmp_path / "result.json", result["steps"]["x"], 1)
    body = json.dumps(
        {
            "error": {
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "30s"}
                ],
            }
        }
    ).encode()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(429, stream=httpx.ByteStream(body))
    )
    with (
        httpx.Client(transport=transport) as client,
        trace.capture(),
        client.stream("POST", "https://generativelanguage.googleapis.com/test") as response,
    ):
        assert response.status_code == 429
    request = result["steps"]["x"]["requests"][0]
    assert request["provider_error"] == "RESOURCE_EXHAUSTED"
    assert request["quota_details"][0]["retryDelay"] == "30s"
    assert m.usage([request])["unknown_usage_requests"] == 1
