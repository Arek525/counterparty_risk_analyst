"""Exercise seeded scenarios through the real API and worker; synthetic writes only.

Run after `docker compose run --rm seed`: python3 scripts/verify_demo.py
"""

import argparse
import http.cookiejar
import json
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def api(path, body=None):
        request = urllib.request.Request(
            args.base_url + "/api" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        with opener.open(request, timeout=15) as response:
            return json.load(response)

    assert api("/meta")["model_mode"] == "demo", "This check must not call a real model"
    api("/auth/login", {"email": "reviewer@northstar.demo", "password": "Demo-only-2026!"})
    policies = {policy["name"]: policy for policy in api("/policies")}
    cases = {case["name"]: case for case in api("/cases")}
    northstar = policies["Synthetic Northstar policy"]["id"]
    orchard = policies["Synthetic Orchard policy"]["id"]
    expected = {
        "complete": "Low",
        "missing": "High",
        "conflict": "High",
        "discrepancy": "Unable to assess",
        "injection": "High",
    }
    queue = [("complete", orchard, "Unable to assess", "alternate-policy")]
    queue += [(name, northstar, risk, name) for name, risk in expected.items()]
    pending = []
    for scenario, policy_id, risk, label in queue:
        case_id = cases[f"Synthetic scenario: {scenario}"]["id"]
        run = api(
            f"/cases/{case_id}/runs",
            {"policy_version_id": policy_id, "retrieval_variant": "hybrid"},
        )
        pending.append((run["id"], risk, label))
    results = []
    deadline = time.monotonic() + 90
    for run_id, risk, label in pending:
        while True:
            run = api(f"/runs/{run_id}")
            assert run["status"] != "failed", run.get("error")
            if run["status"] == "awaiting_review":
                break
            assert time.monotonic() < deadline, "Worker did not finish within 90 seconds"
            time.sleep(0.5)
        report = run["report"]
        assert report["risk"] == risk, (label, report["risk"], risk)
        assert run["input_snapshot"]["retrieval_config"]["backend"] == "pgvector-exact"
        quotes = 0
        for finding in report["findings"]:
            for citation in finding["evidence"]:
                doc = api(f"/documents/{citation['document_id']}")
                chunk = next(c for c in doc["chunks"] if c["id"] == citation["chunk_id"])
                assert citation["quote"] in chunk["text"]
                assert citation["location"] == chunk["location"]
                quotes += 1
        results.append(
            {
                "scenario": label,
                "run_id": run_id,
                "risk": risk,
                "completeness": report["completeness"],
                "resolved_quotes": quotes,
            }
        )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
