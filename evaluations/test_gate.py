"""Regression acceptance tests for the offline CI gate, without provider access."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "evaluation_runner", Path(__file__).with_name("run.py")
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.fixture
def baseline():
    dataset = json.loads(Path(__file__).with_name("held_out.json").read_text())
    return {
        "mode": "demo",
        "dataset_version": dataset["version"],
        "variants": [
            runner.evaluate(dataset["cases"], variant, "demo")
            for variant in ["lexical", "hybrid"]
        ],
    }


def test_fixed_demo_baseline_passes_gate(baseline):
    assert runner.regression_gate(baseline)["passed"] is True


@pytest.mark.parametrize(
    "metric,value",
    [
        ("status_accuracy", 0.89),
        ("risk_accuracy", 0.89),
        ("citation_resolution_rate", 0.99),
    ],
)
def test_gate_rejects_metric_regression(baseline, metric, value):
    baseline["variants"][1][metric] = value
    assert runner.regression_gate(baseline)["passed"] is False


def test_gate_rejects_injection_override_despite_passing_aggregate(baseline):
    injected = next(
        case
        for case in baseline["variants"][1]["results"]
        if case["id"] == "malicious-appendix"
    )
    injected["actual_statuses"] = ["pass"]
    injected["actual_risk"] = "Low"
    result = runner.regression_gate(baseline)
    assert result["passed"] is False
    assert any("injection" in issue for issue in result["failures"])


def test_gate_rejects_missing_adversarial_case_and_non_demo(baseline):
    smaller = copy.deepcopy(baseline)
    smaller["variants"][1]["results"] = [
        case
        for case in smaller["variants"][1]["results"]
        if case["id"] != "malicious-appendix"
    ]
    assert runner.regression_gate(smaller)["passed"] is False
    baseline["mode"] = "gemini"
    assert runner.regression_gate(baseline)["passed"] is False


def test_check_cli_returns_failure_and_writes_reviewable_report(
    baseline, tmp_path, monkeypatch
):
    dataset_path = Path(__file__).with_name("held_out.json")
    (tmp_path / "held_out.json").write_text(dataset_path.read_text())
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["run.py", "--check"])
    baseline["variants"][1]["risk_accuracy"] = 0.5
    monkeypatch.setattr(
        runner,
        "evaluate",
        lambda cases, variant, mode: next(
            row for row in baseline["variants"] if row["variant"] == variant
        ),
    )
    assert runner.main() == 1
    report = json.loads((tmp_path / "results-demo.json").read_text())
    assert report["regression_gate"]["passed"] is False
    assert report["real_model_quality_validated"] is False
