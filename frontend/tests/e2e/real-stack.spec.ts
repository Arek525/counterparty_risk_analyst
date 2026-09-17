import { expect, test } from "@playwright/test";
import path from "node:path";
import { locateSource } from "../../lib/source";
import type { AnalysisRun, DocumentRecord, PolicyVersion } from "../../lib/types";

test("the complete MVP journey works on the real local stack", async ({
  page,
}) => {
  test.setTimeout(900_000);
  const metaResponse = await page.request.get("/api/meta");
  expect(metaResponse.ok()).toBeTruthy();
  expect((await metaResponse.json()).model_mode, "This check must not call a real model").toBe("demo");
  const caseName = `E2E assessment ${Date.now()}`;
  const evidencePath = path.resolve(
    process.cwd(),
    "../datasets/synthetic/evidence/atlas-assurance-pack.md",
  );

  await page.goto("/login");
  await page.getByRole("button", { name: /Demo Reviewer/ }).click();
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Counterparty cases" }),
  ).toBeVisible();

  const seededCases = await page.request.get("/api/cases");
  expect(seededCases.ok()).toBeTruthy();
  const seededCase = (await seededCases.json()).find((value: { name: string }) => value.name === "Atlas — recorded Gemini assessment");
  expect(seededCase).toBeDefined();
  const seededRuns = await page.request.get(`/api/cases/${seededCase.id}/runs`);
  expect(seededRuns.ok()).toBeTruthy();
  const seededRun: AnalysisRun = (await seededRuns.json())[0];
  expect(seededRun.report?.model_mode).toBe("gemini");
  expect(seededRun.report?.recorded_example).toBeDefined();
  expect(seededRun.report?.findings.some(finding => finding.status === "pass")).toBe(true);
  expect(seededRun.decision).toBeNull();
  await page.goto(`/runs/${seededRun.id}`);
  await expect(page.getByText("Recorded Gemini example", { exact: true })).toBeVisible();
  await page.locator(".evidence-quote").first().click();
  await expect(page.getByRole("dialog", { name: "Evidence source" })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await page.goto("/cases");

  await page.getByRole("link", { name: "New case" }).click();
  await page.getByLabel("Case name").fill(caseName);
  await page.getByLabel("Counterparty name").fill("Atlas Compute Services (synthetic)");
  await page
    .getByLabel("Relationship purpose")
    .fill("Hosted customer operations analytics");
  await page.getByLabel("Data shared").fill("Synthetic customer contact and usage data");
  await page.getByLabel("System access").fill("Privileged support access to the analytics administration console");
  await page.getByLabel("Business criticality").selectOption("high");
  await page
    .getByText("The relationship involves personal data processing")
    .click();
  await page.getByText("The counterparty will receive privileged access").click();
  await page.getByRole("button", { name: "Create case" }).click();
  await expect(page.getByRole("heading", { name: caseName })).toBeVisible();

  const caseId = new URL(page.url()).pathname.split("/").at(-1)!;
  await page.getByLabel("Evidence document").setInputFiles(evidencePath);
  await page.getByLabel("Evidence type").selectOption("declaration");
  await page.getByRole("button", { name: "Add document" }).click();
  await expect(page.getByText("atlas-assurance-pack.md")).toBeVisible();
  await expect(
    page.locator(".document-row .subtle").filter({ hasText: "Counterparty declaration" }),
  ).toBeVisible();

  await expect.poll(async () => {
    const response = await page.request.get(`/api/documents?case_id=${caseId}`);
    expect(response.ok()).toBeTruthy();
    const documents: DocumentRecord[] = await response.json();
    return documents.find(document => document.filename === "atlas-assurance-pack.md")?.index_status;
  }, {timeout: 720_000}).toBe("ready");
  const policyResponse = await page.request.get("/api/policies");
  expect(policyResponse.ok()).toBeTruthy();
  const policies: PolicyVersion[] = await policyResponse.json();
  const policy = policies.find(value => value.name === "Northstar Labs Third-Party Assurance Standard — recorded Gemini example" && value.version === 1 && value.status === "approved");
  expect(policy).toBeDefined();
  await expect.poll(async () => {
    const response = await page.request.get(`/api/policies/${policy!.id}`);
    expect(response.ok()).toBeTruthy();
    return (await response.json()).requirement_index_status;
  }, {timeout: 120_000}).toBe("ready");
  await page.getByRole("button", { name: "Run analysis" }).first().click();
  await expect(
    page.getByRole("dialog", { name: "Run analysis" }),
  ).toBeVisible();
  await page
    .getByLabel("Approved policy")
    .selectOption(policy!.id);
  await page.getByRole("button", { name: "Run analysis" }).last().click();
  await expect(page.getByText("Risk", { exact: true })).toBeVisible({
    timeout: 360_000,
  });
  await expect(
    page.getByText("Evidence completeness", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Human decision", { exact: true }),
  ).toBeVisible();
  const runId = new URL(page.url()).pathname.split("/").at(-1)!;
  const runResponse = await page.request.get(`/api/runs/${runId}`);
  expect(runResponse.ok()).toBeTruthy();
  const run: AnalysisRun = await runResponse.json();
  expect(run.status).toBe("awaiting_review");
  expect(run.report?.prompt_version).toBe("semantic-assessment-v6");
  expect(run.report?.rules_version).toBe("semantic-risk-v2");
  expect(run.progress?.completed).toBe(policy!.requirements.length);
  expect(run.progress?.total).toBe(policy!.requirements.length);
  expect(run.report?.findings.map(finding => finding.requirement_id).sort())
    .toEqual(policy!.requirements.map(requirement => requirement.id).sort());
  await expect(page.getByText(`${policy!.requirements.length} of ${policy!.requirements.length} requirements assessed`)).toBeVisible();
  expect(run.report!.risk).toBe("Unable to assess");
  expect(run.report!.completeness).toBe(0);
  expect(run.report!.findings.every(finding => finding.status === "unknown")).toBe(true);
  const sourceDocuments = new Map<string, DocumentRecord>();
  for (const finding of run.report!.findings) {
    expect(["pass", "fail", "unknown", "conflict", "not_applicable"]).toContain(finding.status);
    expect(finding.explanation.trim()).not.toBe("");
    expect(finding.requirement_description?.trim()).toBeTruthy();
    expect(finding.requirement_source).toBeDefined();
    for (const source of [finding.requirement_source!, ...finding.evidence]) {
      if (!sourceDocuments.has(source.document_id)) {
        const response = await page.request.get(`/api/documents/${source.document_id}`);
        expect(response.ok()).toBeTruthy();
        sourceDocuments.set(source.document_id, await response.json());
      }
      const chunk = sourceDocuments.get(source.document_id)!.chunks?.find(value => value.id === source.chunk_id);
      expect(chunk).toBeDefined();
      const document = sourceDocuments.get(source.document_id)!;
      const selection = locateSource(document, source.chunk_id, source.quote);
      expect(selection.notice).toBeUndefined();
      expect(selection.start).toBeDefined();
      expect(document.text!.slice(selection.start, selection.end).replace(/\s+/g, " "))
        .toBe(source.quote.replace(/\s+/g, " "));
      expect(source.location).toEqual(chunk!.location);
    }
  }
  await expect(page.getByRole("heading", {name: "Policy requirement", exact: true})).toHaveCount(policy!.requirements.length);
  await expect(page.getByRole("heading", {name: "Counterparty evidence", exact: true})).toHaveCount(policy!.requirements.length);

  const citation = page.locator(".evidence-quote").first();
  await expect(citation).toBeVisible();
  await citation.click();
  await expect(
    page.getByRole("dialog", { name: "Evidence source" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await page.getByRole("button", { name: "Request information" }).click();
  await page
    .getByRole("textbox", { name: "Information request", exact: true })
    .fill("Please provide support-portal assurance coverage and clarify US support access for reviewer assessment.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Draft saved for reviewer review.");
  await page.reload();
  await expect(page.getByRole("textbox", { name: "Information request", exact: true })).toHaveCount(0);
  await expect(page.getByText("Please provide support-portal assurance coverage and clarify US support access for reviewer assessment.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Save decision" }).click();
  await expect(
    page
      .locator("section.card")
      .filter({ has: page.getByRole("heading", { name: "Decision", exact: true }) })
      .getByText("Information required"),
  ).toBeVisible();

  await expect(page.getByRole("button", { name: "Save draft", exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("Please provide support-portal assurance coverage and clarify US support access for reviewer assessment.", { exact: true })).toBeVisible();
});
