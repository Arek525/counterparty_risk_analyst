import { expect, test, type Page, type Route } from "@playwright/test";

const now = "2026-09-14T10:00:00Z";

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockApi(page: Page) {
  let loggedIn = false;
  let ticketStep = 0;
  const ticketResponse = () => ({
    id: "50000000-0000-4000-8000-000000000001",
    run_id: "run-1",
    action: "create_ticket",
    arguments: {
      title: "Information request",
      body: "Please respond.",
      run_id: "run-1",
      organization_id: "organization-1",
    },
    arguments_hash: "hash",
    status: ["", "proposed", "approved", "executed"][ticketStep],
    requested_by: "user-1",
    approved_by: ticketStep >= 2 ? "user-1" : null,
    expires_at: "2026-09-14T10:15:00Z",
    created_at: now,
    ticket:
      ticketStep === 3
        ? {
            id: "60000000-0000-4000-8000-000000000001",
            status: "open",
            title: "Information request",
            body: "Please respond.",
            run_id: "run-1",
            created_at: now,
            service: "demo-ticketing",
          }
        : null,
    error: null,
  });
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/meta")
      return json(route, {
        demo_mode: true,
        model_mode: "demo",
        model_name: "deterministic-demo-v1",
        version: "0.1.0",
      });
    if (path === "/api/demo/accounts")
      return json(route, [
        {
          email: "reviewer@demo.local",
          password: "demo-reviewer",
          role: "reviewer",
          name: "Marta Recenzent",
        },
      ]);
    if (path === "/api/auth/login") {
      loggedIn = true;
      return json(route, {
        id: "user-1",
        name: "Marta Recenzent",
        email: "reviewer@demo.local",
        role: "reviewer",
      });
    }
    if (path === "/api/auth/me")
      return loggedIn
        ? json(route, {
            id: "user-1",
            name: "Marta Recenzent",
            email: "reviewer@demo.local",
            role: "reviewer",
          })
        : json(route, { detail: "No session" }, 401);
    if (path === "/api/auth/logout") {
      loggedIn = false;
      return json(route, {});
    }
    if (path === "/api/cases" && request.method() === "GET")
      return json(route, [
        {
          id: "case-1",
          name: "Northstar assessment",
          counterparty_name: "Northstar Labs",
          relationship: {
            purpose: "Customer data support",
            data_shared: "Contact details",
            system_access: "Support portal",
            business_criticality: "high",
            personal_data: true,
            privileged_access: false,
          },
          created_at: now,
          updated_at: now,
        },
      ]);
    if (path === "/api/policies")
      return json(route, [
        {
          id: "policy-1",
          name: "Supplier policy",
          version: 2,
          status: "approved",
          document_ids: ["doc-policy"],
          requirements: [],
          created_at: now,
          approved_at: now,
        },
      ]);
    if (path === "/api/audit")
      return json(route, [
        {
          id: "audit-1",
          event: "run.completed",
          actor_name: "Marta Recenzent",
          case_id: "case-1",
          run_id: "run-1",
          details: { decision: "accepted" },
          created_at: now,
        },
      ]);
    if (path === "/api/cases/case-1")
      return json(route, {
        id: "case-1",
        name: "Northstar assessment",
        counterparty_name: "Northstar Labs",
        relationship: {
          purpose: "Customer data support",
          data_shared: "Contact details",
          system_access: "Support portal",
          business_criticality: "high",
          personal_data: true,
          privileged_access: false,
        },
        created_at: now,
        updated_at: now,
      });
    if (
      path === "/api/documents" &&
      url.searchParams.get("case_id") === "case-1"
    )
      return json(route, [
        {
          id: "doc-1",
          filename: "security-questionnaire.md",
          kind: "evidence",
          version: 1,
          media_type: "text/markdown",
          created_at: now,
        },
      ]);
    if (path === "/api/cases/case-1/runs")
      return json(route, [
        {
          id: "run-1",
          case_id: "case-1",
          policy_version_id: "policy-1",
          status: "awaiting_review",
          retrieval_variant: "hybrid",
          model_mode: "demo",
          created_at: now,
          finished_at: now,
        },
      ]);
    if (path === "/api/runs/run-1")
      return json(route, {
        id: "run-1",
        case_id: "case-1",
        policy_version_id: "policy-1",
        status: "awaiting_review",
        retrieval_variant: "hybrid",
        model_mode: "demo",
        created_at: now,
        finished_at: now,
        events: [{ event: "run.awaiting_review", created_at: now }],
        report: {
          risk: "High",
          completeness: 72,
          summary: "Backup encryption has not been confirmed.",
          model_mode: "demo",
          model_name: "deterministic-demo-v1",
          rules_version: "risk-v1",
          prompt_version: "demo-v1",
          metrics: {
            input_tokens: 0,
            output_tokens: 0,
            cost_usd: null,
            duration_ms: 120,
          },
          questions: ["Are backups encrypted?"],
          discrepancies: [
            {
              type: "possible_discrepancy",
              description:
                "The retention declaration does not match the contract period.",
              evidence: [],
            },
          ],
          workflow_error: "Workflow trace finalization must be retried.",
          findings: [
            {
              requirement_id: "req-1",
              title: "Backup encryption",
              status: "pass",
              severity: "High",
              explanation: "The document does not describe backup encryption.",
              missing_information: [],
              evidence: [
                {
                  chunk_id: "chunk-1",
                  document_id: "doc-1",
                  location: "sekcja 4",
                  quote: "Kopie są przechowywane przez 30 dni.",
                  evidence_type: "declaration",
                },
              ],
            },
          ],
        },
      });
    if (path === "/api/documents/doc-1")
      return json(route, {
        id: "doc-1",
        filename: "security-questionnaire.md",
        kind: "evidence",
        version: 1,
        media_type: "text/markdown",
        created_at: now,
        chunks: [
          {
            id: "chunk-1",
            text: "Kopie są przechowywane przez 30 dni.",
            location: "sekcja 4",
          },
        ],
      });
    if (
      path === "/api/runs/run-1/ticket-proposals" &&
      request.method() === "POST"
    ) {
      ticketStep = 1;
      return json(route, ticketResponse(), 201);
    }
    if (
      path === "/api/approvals/50000000-0000-4000-8000-000000000001/approve" &&
      request.method() === "POST"
    ) {
      ticketStep = 2;
      return json(route, ticketResponse());
    }
    if (
      path === "/api/approvals/50000000-0000-4000-8000-000000000001/execute" &&
      request.method() === "POST"
    ) {
      ticketStep = 3;
      return json(route, ticketResponse());
    }
    if (path === "/api/runs/run-1/tickets")
      return json(route, ticketStep ? [ticketResponse()] : []);
    return json(
      route,
      { detail: `No mock for ${request.method()} ${path}` },
      404,
    );
  });
}

test("demo account sign-in opens the protected workspace", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/login");
  await expect(page.getByText("Demo mode", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Marta Recenzent/ }).click();
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/cases/);
  await expect(
    page.getByRole("heading", { name: "Counterparty cases" }),
  ).toBeVisible();
  await expect(page.getByText("Northstar Labs")).toBeVisible();
});

test("report separates risk, completeness and decision and opens its source", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/login");
  await page.getByRole("button", { name: /Marta Recenzent/ }).click();
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("link", { name: "Northstar assessment" }).click();
  await page.getByRole("link", { name: /Open analysis/ }).click();
  await expect(page.getByText("Risk", { exact: true })).toBeVisible();
  await expect(
    page
      .locator(".stat")
      .filter({ hasText: "Risk" })
      .getByText("High", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("72%")).toBeVisible();
  await expect(page.getByText("Awaiting decision")).toBeVisible();
  await expect(page.getByText("Cost unavailable")).toBeVisible();
  await expect(
    page.getByText("Workflow trace finalization must be retried."),
  ).toBeVisible();
  await expect(
    page.getByText("The retention declaration does not match the contract period."),
  ).toBeVisible();
  await expect(page.getByText("Missing information:")).toHaveCount(0);
  await expect(page.getByText("Run.awaiting review")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /security-questionnaire.md/ })).toBeVisible();
  await page.getByRole("button", { name: /Kopie są przechowywane przez 30 dni/ }).click();
  await expect(
    page.getByRole("dialog", { name: "Evidence source" }),
  ).toContainText("Kopie są przechowywane przez 30 dni.");
});

test("policy cards show scope and sources without duplicate descriptions or obsolete assessment modes", async ({ page }) => {
  await mockApi(page);
  const source = { document_id: "doc-policy", chunk_id: "chunk-policy", location: { line_start: 47, line_end: 55 }, quote: "Stored customer records must be encrypted." };
  await page.route("**/api/policies/policy-1", (route) => json(route, {
    id: "policy-1", name: "Northstar policy", version: 1, status: "approved", created_at: now,
    document_ids: ["doc-policy"], requirements: [
      { id: "SEC-02", title: "Storage protection", field: "encryption_at_rest", operator: "eq", expected: true,
        severity: "High", evaluation_method: "deterministic", applicability: { personal_data: true, privileged_access: false }, source },
      { id: "CUSTOM-2", title: "Data removal", field: "retention_days", operator: "lte", expected: 30,
        severity: "High", evaluation_method: "deterministic", applicability: {}, source },
      { id: "CUSTOM-3", title: "Contract interpretation", field: "custom_obligation", operator: "manual", expected: null,
        severity: "Medium", evaluation_method: "manual", applicability: {}, source },
    ],
  }));
  await page.route("**/api/documents", (route) => json(route, [
    { id: "doc-policy", filename: "information-security.md", version: 2, kind: "policy", created_at: now },
  ]));
  await page.goto("/login");
  await page.getByRole("button", { name: /Marta Recenzent/ }).click();
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.goto("/policies/policy-1");
  await expect(page.getByText("Stored customer records must be encrypted.", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Automatic rule check", { exact: true })).toHaveCount(0);
  await expect(page.getByText("The counterparty processes personal data; The counterparty does not have privileged access")).toBeVisible();

  await expect(page.getByText("Reviewer assessment", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", {name: "Storage protection"})).toBeVisible();
  await expect(page.getByText("Requirement ID: SEC-02")).toBeVisible();
  await expect(page.getByText(/SEC means Information Security/)).toBeVisible();
  const link = page.getByRole("link", { name: /information-security.md · v2/ }).first();
  await expect(link).toHaveAttribute("href", "/documents/doc-policy#chunk=chunk-policy&quote=Stored+customer+records+must+be+encrypted.");
  await expect(link).toContainText("View quoted passage");
  await expect(page.getByText(/lines 47–55/)).toHaveCount(0);
  await expect(page.getByText("encryption_at_rest eq true")).toHaveCount(0);
});

test("ticket requires preview, approval and separate execution", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/login");
  await page.getByRole("button", { name: /Marta Recenzent/ }).click();
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.goto("/runs/run-1");

  await page.getByRole("button", { name: "Preview proposal" }).click();
  await expect(
    page.getByText(/Information request — analysis/),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Save exact proposal" })
    .click();
  await expect(page.getByText("Awaiting approval")).toBeVisible();
  await page.getByRole("button", { name: "Approve exact details" }).click();
  await expect(
    page.getByRole("button", { name: "Execute write" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Execute write" }).click();
  await expect(
    page.getByText(/Ticket 60000000-0000-4000-8000-000000000001/),
  ).toBeVisible();
});

test("policy extraction is read-only, approved after review, and regenerated only explicitly", async ({ page }) => {
  await mockApi(page);
  const source = {document_id: "policy-doc", chunk_id: "policy-chunk", location: {line_start: 2}, quote: "Encrypt all customer records."};
  const document = {id: "policy-doc", kind: "policy", filename: "security.md", version: 1, created_at: now, index_status: "ready", text: "Security policy\nEncrypt all customer records.\nEnd of policy.", chunks: [{id: "policy-chunk", text: source.quote, location: source.location}]};
  let policy = {id: "natural-policy", name: "Security", version: 1, status: "draft", extraction_status: "ready", requirement_index_status: "ready", created_at: now, document_ids: [document.id], requirements: [{id: "SEC-1", title: "Encryption", description: "Customer records must be encrypted.", applicability_text: "When customer records are stored", severity: "High", source}]};
  let extractions = 0;
  let regenerate = false;
  await page.route("**/api/documents/policy-doc", route => json(route, document));
  await page.route("**/api/documents", route => json(route, [document]));
  await page.route("**/api/policies", route => json(route, extractions ? [policy] : []));
  await page.route("**/api/policies/propose", route => {
    extractions++;
    regenerate = route.request().postDataJSON().regenerate === true;
    return json(route, policy);
  });
  await page.route("**/api/policies/natural-policy", route => json(route, policy));
  await page.route("**/api/policies/natural-policy/approve", route => { policy = {...policy, status: "approved"}; return json(route, policy); });
  await page.goto("/login");
  await page.getByRole("button", {name: /Marta Recenzent/}).click();
  await page.getByRole("button", {name: "Sign in"}).click();
  await page.goto("/documents/policy-doc");
  await expect(page.getByRole("heading", {name: "Full document"})).toBeVisible();
  await expect(page.getByText(/End of policy/)).toBeVisible();
  expect(extractions).toBe(0);
  await page.getByRole("button", {name: "Extract requirements", exact: true}).click();
  await expect(page).toHaveURL(/policies\/natural-policy/);
  await expect(page.getByRole("button", {name: "Edit requirements"})).toHaveCount(0);
  await expect(page.getByRole("button", {name: "Clone for editing"})).toHaveCount(0);
  await expect(page.getByText("When customer records are stored", {exact: true})).toBeVisible();
  await page.getByText("Review full extracted wording", {exact: true}).click();
  await expect(page.getByText("Customer records must be encrypted.", {exact: true})).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await page.getByRole("button", {name: "Approve version"}).click();
  await expect(page.getByText("Immutable approved version")).toBeVisible();
  await expect(page.getByRole("button", {name: "Clone for editing"})).toHaveCount(0);
  await page.goto("/documents/policy-doc");
  await page.getByRole("link", {name: /Security · v1/}).click();
  expect(extractions).toBe(1);
  page.once("dialog", dialog => dialog.dismiss());
  await page.getByRole("button", {name: "Regenerate requirements"}).click();
  expect(extractions).toBe(1);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", {name: "Regenerate requirements"}).click();
  await expect.poll(() => extractions).toBe(2);
  expect(regenerate).toBe(true);
});

test("failed semantic analysis resumes unfinished requirements and pairs policy with counterparty sources", async ({page}) => {
  await mockApi(page);
  const requirementSource = {document_id: "policy-doc", chunk_id: "policy-chunk", location: "section 2", quote: "Encrypt customer records."};
  await page.route("**/api/documents/policy-doc", route => json(route, {id: "policy-doc", filename: "security.md", chunks: [{id: "policy-chunk", text: requirementSource.quote, location: requirementSource.location}]}));
  const evidence = {document_id: "doc-1", chunk_id: "chunk-1", location: "section 3", quote: "Our stored records use AES-256."};
  const report = {risk: "Low", completeness: 100, summary: "Requirement assessed.", questions: [], discrepancies: [], model_name: "mock-semantic", model_mode: "demo", rules_version: "semantic-v2", prompt_version: "v2", metrics: {input_tokens: 10, output_tokens: 10, duration_ms: 100, cost_usd: null}, findings: [{requirement_id: "SEC-1", title: "Encryption", severity: "High", status: "pass", explanation: "The declaration supports the encryption requirement.", requirement_description: "Customer records must be encrypted.", requirement_source: requirementSource, evidence: [evidence]}]};
  let retries = 0;
  let completed = false;
  await page.route("**/api/runs/resume-run", route => json(route, {id: "resume-run", case_id: "case-1", status: completed ? "awaiting_review" : retries ? "running" : "failed", retrieval_variant: "hybrid", created_at: now, progress: {completed: completed ? 2 : 1, total: 2, current_requirement_id: completed ? null : "SEC-2"}, error: retries ? null : "Provider request failed", report}));
  await page.route("**/api/runs/resume-run/tickets", route => json(route, []));
  await page.route("**/api/runs/resume-run/retry", route => {retries++; return json(route, {});});
  await page.goto("/login");
  await page.getByRole("button", {name: /Marta Recenzent/}).click();
  await page.getByRole("button", {name: "Sign in"}).click();
  await page.goto("/runs/resume-run");
  await expect(page.getByText("1 of 2 requirements assessed")).toBeVisible();
  await expect(page.getByText("Risk", {exact: true})).toHaveCount(0);
  await page.getByRole("button", {name: "Resume unfinished requirements"}).click();
  await expect(page.getByText("Retrieving evidence and evaluating requirements…")).toBeVisible();
  expect(retries).toBe(1);
  await expect(page.getByText("Risk", {exact: true})).toHaveCount(0);
  completed = true;
  await expect(page.getByText("2 of 2 requirements assessed")).toBeVisible();
  await expect(page.getByRole("heading", {name: "Policy requirement"})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Counterparty evidence"})).toBeVisible();
  await expect(page.getByText("Encrypt customer records.", {exact: true})).toHaveCount(0);
  await page.getByRole("button", {name: /Policy source · View quoted passage/}).click();
  await expect(page.getByRole("dialog", {name: "Evidence source"})).toBeVisible();
  await expect(page.getByRole("dialog").getByText("Encrypt customer records.", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Close"}).click();
  await expect(page.getByRole("button", {name: /Our stored records use AES-256/})).toBeVisible();
});

test("deletion requires confirmation, shows dependency errors and removes saved reports", async ({page}) => {
  await mockApi(page);
  const deletions: string[] = [];
  let blocked = true;
  await page.route("**/api/runs/run-1", async route => {
    if (route.request().method() !== "DELETE") return route.fallback();
    deletions.push("run-1");
    return blocked ? json(route, {detail: "Analysis is running. Wait until it finishes."}, 409) : json(route, {ok: true});
  });
  await page.goto("/login");
  await page.getByRole("button", {name: /Marta Recenzent/}).click();
  await page.getByRole("button", {name: "Sign in"}).click();
  await page.goto("/runs/run-1");
  page.once("dialog", dialog => dialog.dismiss());
  await page.getByRole("button", {name: "Delete report", exact: true}).click();
  expect(deletions).toEqual([]);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", {name: "Delete report", exact: true}).click();
  await expect(page.getByText("Analysis is running. Wait until it finishes.")).toBeVisible();
  expect(deletions).toEqual(["run-1"]);
  blocked = false;
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", {name: "Delete report", exact: true}).click();
  await expect(page).toHaveURL(/\/cases\/case-1$/);
  await expect(page.getByRole("button", {name: "Delete case", exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Delete security-questionnaire.md"})).toBeVisible();
  await page.route("**/api/cases/case-1", route => route.request().method() === "DELETE"
    ? json(route, {ok: true, cleanup_pending: true}) : route.fallback());
  const messages: string[] = [];
  page.on("dialog", async dialog => { messages.push(dialog.message()); await dialog.accept(); });
  await page.getByRole("button", {name: "Delete case", exact: true}).click();
  await expect(page).toHaveURL(/\/cases$/);
  expect(messages).toContain("The record was deleted. Original file cleanup is pending and will retry automatically.");
});
