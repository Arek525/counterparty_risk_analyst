// Explicit live-provider smoke through the API. Uses configured local credentials;
// does not enable billing, choose another model, or run automatically in CI.
import { readFileSync, writeFileSync, existsSync } from "node:fs";

const base = process.env.APP_URL ?? "http://127.0.0.1:3000";
const output = process.argv[2];
if (!output) throw new Error("Pass a local results JSON path");
let cookie = "";
const result = existsSync(output) ? JSON.parse(readFileSync(output, "utf8")) : {};
const save = () => writeFileSync(output, JSON.stringify(result, null, 2) + "\n");
async function api(path, body, method = body ? "POST" : "GET") {
  const response = await fetch(base + "/api" + path, {
    method, headers: { ...(cookie ? { Cookie: cookie } : {}), ...(body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}) },
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(150000),
  });
  if (response.headers.get("set-cookie")) cookie = response.headers.get("set-cookie").split(";")[0];
  const value = await response.json();
  if (!response.ok) throw new Error(`API ${path}: ${response.status} ${JSON.stringify(value)}`);
  return value;
}
async function upload(name, text, caseId) {
  const form = new FormData();
  form.set("file", new File([text], name, { type: "text/plain" }));
  form.set("kind", caseId ? "evidence" : "policy");
  if (caseId) form.set("case_id", caseId);
  return api("/documents", form);
}
const pause = () => new Promise(resolve => setTimeout(resolve, 2000));
async function until(path, predicate) {
  for (let i = 0; i < 150; i++) {
    const value = await api(path);
    if (predicate(value)) return value;
    await pause();
  }
  throw new Error(`Timed out waiting for ${path}`);
}
try {
  const account = (await api("/demo/accounts")).find(a => a.role === "reviewer");
  if (!account) throw new Error("Local demo reviewer required for explicit smoke");
  await api("/auth/login", { email: account.email, password: account.password });
  if ((await api("/meta")).model_mode !== "gemini") throw new Error("Smoke requires explicit Gemini mode");
  const policyText = `# Synthetic verification customer policy
This fictional policy is solely an application evaluation fixture. It governs the production service handling customer personal data.

## Deletion
The supplier must delete production customer records within 30 calendar days after contract termination. Technically isolated backup copies are exempt from that production deadline provided they expire within 90 calendar days and cannot be used for ordinary processing.

## Incident notice
The supplier must send the initial customer incident notification within 24 hours after credible evidence of an incident affecting customer data reaches its response team. Waiting for root-cause confirmation does not postpone the deadline.

## Independent assurance
The supplier must provide an independent assurance report covering the production service for the current review period before onboarding.
`;
  if (!result.document_id) {
    result.document_id = (await upload("semantic-verification-policy.md", policyText)).id;
    save();
  }
  if (!result.policy_id) {
    const policy = await api("/policies/propose", { name: "Semantic verification policy", document_ids: [result.document_id] });
    result.policy_id = policy.id;
    result.extraction = policy;
    save();
  }
  const policy = await api(`/policies/${result.policy_id}`);
  if (policy.extraction_status !== "ready") throw new Error(policy.extraction_error ?? "Extraction not ready");
  if (policy.requirements.length > 5) throw new Error("Smoke budget: review extraction exceeding five requirements");
  const cached = await api("/policies/propose", { name: "Semantic verification policy", document_ids: [result.document_id] });
  if (cached.id !== policy.id) throw new Error("Extraction cache did not reuse saved version");
  result.cache_reused = true;
  if (policy.status === "draft") await api(`/policies/${policy.id}/approve`, {});
  await until(`/policies/${policy.id}`, p => {
    if (p.requirement_index_status === "error") throw new Error(p.requirement_index_error);
    return p.requirement_index_status === "ready";
  });
  if (!result.case_id) {
    result.case_id = (await api("/cases", { name: "Semantic assessment verification", counterparty_name: "Fictional Harbor Processing", relationship: { purpose: "Production customer data processing", personal_data: true, business_criticality: "high" } })).id;
    save();
  }
  if (!result.evidence_id) {
    result.evidence_id = (await upload("semantic-verification-counterparty.txt", `Fictional Harbor Processing — production service declaration, current review period.
Production customer records are deleted 20 calendar days after contract termination. Technically isolated backup copies expire after 80 calendar days; they are inaccessible for ordinary processing. Restore procedures reapply deletion requests before reopening access.
Our first customer incident notice is sent within 48 hours after credible evidence of customer impact reaches our response team. We do not wait for root-cause confirmation to start that period.
This document makes no other control declarations.
`, result.case_id)).id;
    save();
  }
  await until(`/documents/${result.evidence_id}`, d => {
    if (d.index_status === "error") throw new Error(d.index_error);
    return d.index_status === "ready";
  });
  if (!result.run_id) {
    result.run_id = (await api(`/cases/${result.case_id}/runs`, { policy_version_id: policy.id, retrieval_variant: "hybrid" })).id;
    save();
  }
  const run = await until(`/runs/${result.run_id}`, r => ["awaiting_review", "completed", "failed"].includes(r.status));
  result.run = run;
  save();
  if (run.status === "failed") throw new Error(run.error);
  const checks = [
    ["deletion", /delet|backup/i, "pass"],
    ["incident", /incident|notif/i, "fail"],
    ["assurance", /assurance|audit/i, "unknown"],
  ].map(([topic, pattern, expected]) => {
    const matching = run.report.findings.filter(f => pattern.test(f.title));
    return { topic, expected, actual: matching.map(f => f.status), passed: matching.length > 0 && matching.every(f => f.status === expected) };
  });
  result.checks = checks;
  result.passed = checks.every(c => c.passed) && run.progress.completed === policy.requirements.length;
  save();
  console.log(JSON.stringify({ run_id: result.run_id, requirements: policy.requirements.length, checks, progress: run.progress, metrics: run.report.metrics, passed: result.passed }));
  if (!result.passed) process.exitCode = 1;
} catch (error) {
  result.error = error.message;
  save();
  console.error(error.message);
  process.exitCode = 1;
}
