import { expect, test } from "@playwright/test";
import path from "node:path";

test("pełna ścieżka MVP działa na rzeczywistym lokalnym stosie", async ({
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
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await expect(
    page.getByRole("heading", { name: "Sprawy kontrahentów" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Nowa sprawa" }).click();
  await page.getByLabel("Nazwa sprawy").fill(caseName);
  await page.getByLabel("Nazwa kontrahenta").fill("E2E Synthetic Vendor");
  await page
    .getByLabel("Cel współpracy")
    .fill("Obsługa krytycznej platformy wsparcia");
  await page.getByLabel("Udostępniane dane").fill("Syntetyczne dane klientów");
  await page.getByLabel("Dostęp do systemów").fill("Konsola administracyjna");
  await page.getByLabel("Krytyczność biznesowa").selectOption("high");
  await page
    .getByText("Relacja obejmuje przetwarzanie danych osobowych")
    .click();
  await page.getByText("Kontrahent otrzyma dostęp uprzywilejowany").click();
  await page.getByRole("button", { name: "Utwórz sprawę" }).click();
  await expect(page.getByRole("heading", { name: caseName })).toBeVisible();

  await page.getByLabel("Dokument dowodowy").setInputFiles(evidencePath);
  await page.getByLabel("Rodzaj dowodu").selectOption("independent");
  await page.getByRole("button", { name: "Dodaj dokument" }).click();
  await expect(page.getByText("complete.md")).toBeVisible();
  await expect(
    page.locator(".document-row .subtle").filter({ hasText: "Niezależny dowód" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Uruchom analizę" }).first().click();
  await expect(
    page.getByRole("dialog", { name: "Uruchom analizę" }),
  ).toBeVisible();
  await page
    .getByLabel("Zatwierdzona polityka")
    .selectOption({ label: "Synthetic Northstar policy · v1" });
  await page.getByRole("button", { name: "Uruchom analizę" }).last().click();
  await expect(page.getByText("Ryzyko", { exact: true })).toBeVisible({
    timeout: 120_000,
  });
  await expect(
    page.getByText("Kompletność dowodów", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Decyzja człowieka", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(".stat").filter({ hasText: "Ryzyko" }).getByText("Low"),
  ).toBeVisible();
  await expect(
    page.locator(".stat").filter({ hasText: "Kompletność" }).getByText("100%"),
  ).toBeVisible();
  await expect(page.getByText("Brakująca informacja:")).toHaveCount(0);

  const citation = page.getByRole("button", { name: /otwórz źródło/ }).first();
  await expect(citation).toBeVisible();
  await citation.click();
  await expect(
    page.getByRole("dialog", { name: "Źródło dowodu" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Zamknij" }).click();

  await page.getByRole("button", { name: "Akceptuję" }).click();
  await page
    .getByLabel("Uzasadnienie decyzji")
    .fill("Dowody są kompletne, a ustalenia spełniają zatwierdzone wymagania.");
  await page.getByRole("button", { name: "Zapisz decyzję" }).click();
  await expect(
    page
      .locator("section.card")
      .filter({ has: page.getByRole("heading", { name: "Decyzja", exact: true }) })
      .getByText("Zaakceptowano"),
  ).toBeVisible();

  await page
    .getByLabel("Treść")
    .fill("Zgłoszenie weryfikujące bezpieczny, zatwierdzony zapis integracyjny.");
  await page.getByRole("button", { name: "Pokaż podgląd propozycji" }).click();
  await expect(
    page.getByText(/Uzupełnienie informacji — analiza/),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Zapisz dokładną propozycję" })
    .click();
  await page.getByRole("button", { name: "Zatwierdź dokładne dane" }).click();
  await page.getByRole("button", { name: "Wykonaj zapis" }).click();
  await expect(page.getByText(/Ticket [0-9a-f-]+/)).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: "Odśwież status" }).click();
});
