import { expect, test, type Page } from "@playwright/test";

async function workspace(page: Page, role: "analyst" | "reviewer", decided: boolean, reportReady = false, overrides: () => Record<string, unknown> = () => ({})) {
  const created_at = "2026-09-16T10:00:00Z";
  const caseItem = { id: "shared", name: "Shared case", counterparty_name: "Example", owner_id: "another-user", is_decided: decided, created_at, updated_at: created_at, relationship: { purpose: "Support", data_shared: "None", system_access: "None", business_criticality: "low", personal_data: false, privileged_access: false } };
  const documents = [
    { id: "policy-source", kind: "policy", filename: "Policy.txt", version: 1, text: "Policy wording", created_at, index_status: "ready" },
    { id: "evidence", kind: "evidence", case_id: "shared", case_is_decided: decided, filename: "Evidence.txt", version: 1, text: "Evidence wording", created_at, index_status: "ready" },
  ];
  const policy = { id: "policy", name: "Draft policy", version: 1, status: "draft", document_ids: ["policy-source"], requirements: [], created_at };
  const run = { id: "report", case_id: "shared", case_is_decided: decided, status: "failed", error: "Assessment interrupted", retrieval_variant: "hybrid", model_mode: "demo", created_at };
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let body: unknown = {};
    if (path === "/api/auth/me") body = { id: "current-user", role, name: "Current user" };
    else if (path === "/api/meta") body = { demo_mode: true, model_mode: "demo" };
    else if (path === "/api/cases") body = [caseItem];
    else if (path === "/api/cases/shared") body = caseItem;
    else if (path === "/api/cases/shared/runs") body = [run];
    else if (path === "/api/runs/report") body = reportReady ? { ...run, status: "awaiting_review", ...overrides(), report: { findings: [], risk: "Low", completeness: 100, summary: "Ready", questions: ["Please confirm."], discrepancies: [], model_mode: "demo", model_name: "demo", metrics: { input_tokens: 0, output_tokens: 0, cost_usd: null }, rules_version: "v1", prompt_version: "v1" } } : run;
    else if (path === "/api/policies") body = [policy];
    else if (path === "/api/policies/policy") body = policy;
    else if (path === "/api/documents") {
      expect(["policy", "evidence"]).toContain(url.searchParams.get("kind"));
      body = documents.filter((doc) => doc.kind === url.searchParams.get("kind"));
    } else if (path.startsWith("/api/documents/")) body = documents.find((doc) => path.endsWith(doc.id));
    else if (path === "/api/embedding-status") body = { status: "ready" };
    await route.fulfill({ json: body });
  });
}

for (const role of ["analyst", "reviewer"] as const) {
  for (const decided of [false, true]) {
    test(`${role} sees permitted actions on ${decided ? "decided" : "open"} shared cases`, async ({ page }) => {
      await workspace(page, role, decided);
      const canWrite = role === "reviewer" || !decided;
      await page.goto("/cases/shared");
      await expect(page.getByRole("heading", { name: "Shared case", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Delete case", exact: true })).toHaveCount(role === "reviewer" ? 1 : 0);
      for (const name of ["Edit", "Run analysis", "Delete Evidence.txt", "Delete report"]) {
        await expect(page.getByRole("button", { name, exact: true })).toHaveCount(canWrite ? 1 : 0);
      }
      await expect(page.getByLabel("Evidence document", { exact: true })).toHaveCount(canWrite ? 1 : 0);
      await page.goto("/documents/evidence");
      await expect(page.getByRole("heading", { name: "Full document", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Delete", exact: true })).toHaveCount(canWrite ? 1 : 0);
      await page.getByText("Technical details", { exact: true }).click();
      await expect(page.getByRole("button", { name: "Reindex document", exact: true })).toHaveCount(canWrite ? 1 : 0);
      await page.goto("/runs/report");
      await expect(page.getByRole("heading", { name: "Assessment report", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Delete report", exact: true })).toHaveCount(canWrite ? 1 : 0);
      await expect(page.getByRole("button", { name: "Resume unfinished requirements", exact: true })).toHaveCount(canWrite ? 1 : 0);
    });
  }
  test(`${role} can read drafts but only reviewers manage policies`, async ({ page }) => {
    await workspace(page, role, false);
    const count = role === "reviewer" ? 1 : 0;
    await page.goto("/policies");
    await expect(page.getByRole("cell", { name: "Draft policy", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "New policy set", exact: true })).toHaveCount(count);
    await expect(page.getByRole("button", { name: "Delete policy set", exact: true })).toHaveCount(count);
    await expect(page.getByRole("button", { name: "Delete Policy.txt", exact: true })).toHaveCount(count);
    await page.goto("/policies/policy");
    await expect(page.getByRole("heading", { name: "Draft policy", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Regenerate requirements", exact: true })).toHaveCount(count);
    await page.goto("/documents/policy-source");
    await expect(page.getByRole("heading", { name: "Full document", exact: true })).toBeVisible();
    await page.getByText("Technical details", { exact: true }).click();
    for (const name of ["Delete", "Extract requirements", "Reindex document"]) {
      await expect(page.getByRole("button", { name, exact: true })).toHaveCount(count);
    }
  });
}

for (const role of ["analyst", "reviewer"] as const) {
  for (const decided of [false, true]) {
    test(`${role} draft and decision controls on ${decided ? "decided" : "open"} case`, async ({ page }) => {
      await workspace(page, role, decided, true);
      await page.goto("/runs/report");
      await expect(page.getByRole("heading", { name: "Decision", exact: true })).toBeVisible();
      for (const name of ["Accept", "Reject", "Request information", "Save decision"]) {
        await expect(page.getByRole("button", { name, exact: true })).toHaveCount(role === "reviewer" ? 1 : 0);
      }
      await expect(page.getByRole("button", { name: "Save draft", exact: true })).toHaveCount(decided && role !== "reviewer" ? 0 : 1);
      if (!decided || role === "reviewer") {
        await expect(page.getByRole("textbox", { name: "Information request", exact: true })).toHaveValue("Please confirm.");
        const saved = page.waitForRequest(request => request.url().endsWith("/information-request-draft") && request.method() === "PUT");
        await page.getByRole("button", { name: "Save draft", exact: true }).click();
        expect((await saved).postDataJSON()).toEqual({ text: "Please confirm." });
        await expect(page.getByRole("status")).toHaveText("Draft saved for reviewer review.");
      }
    });
  }
}

test("reviewer edits an analyst draft, preserves edits after refresh and records final questions", async ({ page }) => {
  let decision: unknown = null;
  let draft = { text: "Analyst question", actor_id: "analyst-id", actor_email: "analyst@example.test", updated_at: "2026-09-16T10:00:00Z" };
  await workspace(page, "reviewer", false, true, () => ({ information_request_draft: draft, decision }));
  await page.route("**/api/runs/report/information-request-draft", async route => {
    draft = { ...draft, text: route.request().postDataJSON().text, actor_id: "current-user", actor_email: "reviewer@example.test" };
    await route.fulfill({ json: {} });
  });
  await page.route("**/api/runs/report/decision", async route => {
    decision = { ...route.request().postDataJSON(), id: "decision", created_at: "2026-09-16T10:00:00Z" };
    await route.fulfill({ json: decision });
  });
  await page.goto("/runs/report");
  const field = page.getByRole("textbox", { name: "Information request", exact: true });
  await expect(field).toHaveCount(0);
  await expect(page.getByText("Analyst question", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Edit", exact: true}).click();
  await expect(field).toHaveValue("Analyst question");
  await expect(page.getByText(/Draft saved by analyst@example.test/)).toBeVisible();
  await field.fill("Please provide an independent audit report.");
  await page.getByRole("button", { name: "Accept", exact: true }).click();
  await page.getByLabel("Decision rationale").fill("Separate acceptance rationale");
  await page.getByRole("button", { name: "Request information", exact: true }).click();
  await expect(field).toHaveValue("Please provide an independent audit report.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Draft saved for reviewer review.");
  await expect(field).toHaveCount(0);
  await page.getByRole("button", {name: "Edit", exact: true}).click();
  await expect(field).toHaveValue("Please provide an independent audit report.");
  await expect(page.getByText(/Draft saved by reviewer@example.test/)).toBeVisible();
  await field.fill("Final reviewed questions.\nPlease include the audit period.");
  await page.getByRole("button", { name: "Save decision", exact: true }).click();
  await expect(field).toHaveCount(0);
  expect(decision).toMatchObject({ decision: "needs_information", rationale: "Final reviewed questions.\nPlease include the audit period." });
  await expect(page.getByText("Final reviewed questions. Please include the audit period.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save draft", exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("Final reviewed questions. Please include the audit period.", { exact: true })).toBeVisible();
});

test("analyst can continue an information-required case while its recorded questions stay immutable", async ({ page }) => {
  await workspace(page, "analyst", false, true, () => ({
    status: "completed",
    decision: { id: "decision", decision: "needs_information", rationale: "Please provide the audit report.", created_at: "2026-09-16T10:00:00Z" },
  }));
  await page.goto("/runs/report");
  await expect(page.getByText("Please provide the audit report.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save draft", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save decision", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Delete report", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Back to case" }).click();
  await expect(page.getByLabel("Evidence document", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run analysis", exact: true })).toBeVisible();
});

test("a failed draft save retains analyst edits for retry", async ({ page }) => {
  await workspace(page, "analyst", false, true);
  let attempts = 0;
  await page.route("**/api/runs/report/information-request-draft", async route => {
    attempts++;
    expect(route.request().postDataJSON()).toEqual({ text: "Please provide the latest audit." });
    await route.fulfill(attempts === 1 ? { status: 503, json: { detail: "Save temporarily unavailable" } } : { json: {} });
  });
  await page.goto("/runs/report");
  const field = page.getByRole("textbox", { name: "Information request", exact: true });
  await expect(field).toHaveAttribute("maxlength", "10000");
  await field.fill(" abcd ");
  await expect(page.getByRole("button", { name: "Save draft", exact: true })).toBeDisabled();
  await field.fill("Please provide the latest audit.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByText("Save temporarily unavailable")).toBeVisible();
  await expect(field).toHaveValue("Please provide the latest audit.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Draft saved for reviewer review.");
  expect(attempts).toBe(2);
});


test("analyst submission becomes a read-only message, including after reload", async ({ page }) => {
  let draft: Record<string, unknown> | null = null;
  await workspace(page, "analyst", false, true, () => ({
    information_request_draft: draft,
    events: [{ event: "run.awaiting_review" }, { event: "information_request.draft_saved" }],
  }));
  await page.route("**/api/runs/report/information-request-draft", async route => {
    draft = { text: route.request().postDataJSON().text, actor_id: "current-user",
      actor_email: "analyst@example.test", updated_at: "2026-09-17T10:00:00Z" };
    await route.fulfill({ json: {} });
  });
  await page.goto("/runs/report");
  await page.getByRole("textbox", { name: "Information request", exact: true }).fill("Please provide the audit report.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  for (let visit = 0; visit < 2; visit++) {
    await expect(page.getByText("Please provide the audit report.", {exact: true})).toBeVisible();
    await expect(page.getByRole("textbox", {name: "Information request", exact: true})).toHaveCount(0);
    await expect(page.getByRole("button", {name: "Edit", exact: true})).toHaveCount(0);
    await expect(page.getByRole("button", {name: "Save draft", exact: true})).toHaveCount(0);
    await expect(page.getByText("Report awaiting review", {exact: true})).toBeVisible();
    await expect(page.getByText(/Information request.draft saved|information_request.draft_saved/)).toHaveCount(0);
    if (visit === 0) await page.reload();
  }
});
