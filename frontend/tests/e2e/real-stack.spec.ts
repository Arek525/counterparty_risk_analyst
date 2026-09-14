import { expect, test } from "@playwright/test";
import path from "node:path";

test("the complete MVP journey works on the real local stack", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const caseName = `E2E assessment ${Date.now()}`;
  const evidencePath = path.resolve(
    process.cwd(),
    "../datasets/synthetic/evidence/complete.md",
  );

  await page.goto("/login");
  await page.getByRole("button", { name: /Demo Reviewer/ }).click();
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Counterparty cases" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "New case" }).click();
  await page.getByLabel("Case name").fill(caseName);
  await page.getByLabel("Counterparty name").fill("E2E Synthetic Vendor");
  await page
    .getByLabel("Relationship purpose")
    .fill("Support for a critical service platform");
  await page.getByLabel("Data shared").fill("Synthetic customer data");
  await page.getByLabel("System access").fill("Administration console");
  await page.getByLabel("Business criticality").selectOption("high");
  await page
    .getByText("The relationship involves personal data processing")
    .click();
  await page.getByText("The counterparty will receive privileged access").click();
  await page.getByRole("button", { name: "Create case" }).click();
  await expect(page.getByRole("heading", { name: caseName })).toBeVisible();

  await page.getByLabel("Evidence document").setInputFiles(evidencePath);
  await page.getByLabel("Evidence type").selectOption("independent");
  await page.getByRole("button", { name: "Add document" }).click();
  await expect(page.getByText("complete.md")).toBeVisible();
  await expect(
    page.locator(".document-row .subtle").filter({ hasText: "Independent evidence" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Run analysis" }).first().click();
  await expect(
    page.getByRole("dialog", { name: "Run analysis" }),
  ).toBeVisible();
  await page
    .getByLabel("Approved policy")
    .selectOption({ label: "Synthetic Northstar policy · v1" });
  await page.getByRole("button", { name: "Run analysis" }).last().click();
  await expect(page.getByText("Risk", { exact: true })).toBeVisible({
    timeout: 120_000,
  });
  await expect(
    page.getByText("Evidence completeness", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Human decision", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(".stat").filter({ hasText: "Risk" }).getByText("Low"),
  ).toBeVisible();
  await expect(
    page.locator(".stat").filter({ hasText: "Completeness" }).getByText("100%"),
  ).toBeVisible();
  await expect(page.getByText("Missing information:")).toHaveCount(0);

  const citation = page.getByRole("button", { name: /open source/ }).first();
  await expect(citation).toBeVisible();
  await citation.click();
  await expect(
    page.getByRole("dialog", { name: "Evidence source" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await page.getByRole("button", { name: "Accept" }).click();
  await page
    .getByLabel("Decision rationale")
    .fill("The evidence is complete and the findings meet the approved requirements.");
  await page.getByRole("button", { name: "Save decision" }).click();
  await expect(
    page
      .locator("section.card")
      .filter({ has: page.getByRole("heading", { name: "Decision", exact: true }) })
      .getByText("Accepted"),
  ).toBeVisible();

  await page
    .getByLabel("Body")
    .fill("Ticket verifying a safe, approved integration write.");
  await page.getByRole("button", { name: "Preview proposal" }).click();
  await expect(
    page.getByText(/Information request — analysis/),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Save exact proposal" })
    .click();
  await page.getByRole("button", { name: "Approve exact details" }).click();
  await page.getByRole("button", { name: "Execute write" }).click();
  await expect(page.getByText(/Ticket [0-9a-f-]+/)).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: "Refresh status" }).click();
});
