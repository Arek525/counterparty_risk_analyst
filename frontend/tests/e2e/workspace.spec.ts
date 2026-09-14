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
  await page.getByRole("button", { name: /sekcja 4/ }).click();
  await expect(
    page.getByRole("dialog", { name: "Evidence source" }),
  ).toContainText("Kopie są przechowywane przez 30 dni.");
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
