"""Create and assess an Atlas synthetic case through the real local API and worker.

Run on a disposable demo stack: python3 scripts/verify_demo.py
This explicitly creates a case, evidence and report; it never resets the workspace.
"""

import argparse
import http.cookiejar
import json
import time
import urllib.request
from pathlib import Path
from uuid import uuid4


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
    policy = next(
        p
        for p in api("/policies")
        if p["name"] == "Northstar Labs Third-Party Assurance Standard"
        and p["status"] == "approved"
    )
    case = api(
        "/cases",
        {
            "name": f"Atlas verification {uuid4().hex[:8]}",
            "counterparty_name": "Atlas Compute Services (synthetic)",
            "relationship": {
                "purpose": "Hosted customer operations analytics",
                "data_shared": "Synthetic customer contact and usage data",
                "system_access": (
                    "Privileged support access to the analytics administration console"
                ),
                "business_criticality": "high",
                "personal_data": True,
                "privileged_access": True,
            },
        },
    )
    path = (
        Path(__file__).resolve().parents[1] / "datasets/synthetic/evidence/atlas-assurance-pack.md"
    )
    boundary = uuid4().hex
    fields = {"kind": "evidence", "case_id": case["id"], "evidence_type": "declaration"}
    data = b"".join(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
        ).encode()
        for key, value in fields.items()
    )
    data += (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{path.name}"\r\nContent-Type: text/markdown\r\n\r\n'
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    with opener.open(
        urllib.request.Request(
            args.base_url + "/api/documents",
            data=data,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        ),
        timeout=30,
    ) as response:
        assert response.status == 201
        document = json.load(response)
    deadline = time.monotonic() + 720
    while document["index_status"] != "ready":
        assert document["index_status"] != "error", document.get("index_error")
        assert time.monotonic() < deadline, "Evidence indexing did not finish within 720 seconds"
        time.sleep(1)
        document = api(f"/documents/{document['id']}")
    run = api(
        f"/cases/{case['id']}/runs",
        {
            "policy_version_id": policy["id"],
            "retrieval_variant": "semantic",
        },
    )
    deadline = time.monotonic() + 90
    while run["status"] != "awaiting_review":
        assert run["status"] != "failed", run.get("error")
        assert time.monotonic() < deadline, "Worker did not finish within 90 seconds"
        time.sleep(0.5)
        run = api(f"/runs/{run['id']}")
    report = run["report"]
    assert report["risk"] == "Unable to assess" and report["completeness"] == 30
    assert sum(f["status"] == "pass" for f in report["findings"]) == 6
    assert sum(f["status"] == "unknown" for f in report["findings"]) == 14
    quotes = 0
    for finding in report["findings"]:
        for citation in finding["evidence"]:
            doc = api(f"/documents/{citation['document_id']}")
            chunk = next(c for c in doc["chunks"] if c["id"] == citation["chunk_id"])
            assert citation["quote"] in chunk["text"]
            assert citation["location"] == chunk["location"]
            quotes += 1
    api(
        f"/runs/{run['id']}/decision",
        {
            "decision": "needs_information",
            "rationale": "Provide support-portal assurance coverage and clarify US support access.",
        },
    )
    print(
        json.dumps(
            {
                "case_id": case["id"],
                "run_id": run["id"],
                "risk": report["risk"],
                "completeness": report["completeness"],
                "resolved_quotes": quotes,
                "decision": "needs_information",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
