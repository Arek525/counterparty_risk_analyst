import { expect, test } from "@playwright/test";

const quote = "Notify us within 24 hours.";
const text = `Earlier agreement: ${quote}\n${"Background information.\n".repeat(100)}\nCurrent agreement:\nNotify us\twithin\n24 hours.\nKeep supporting records.`;

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path === "/api/auth/me"
      ? { id: "reviewer", name: "Reviewer", role: "reviewer" }
      : path === "/api/documents/source"
        ? {
            id: "source", filename: "Agreement.txt", kind: "evidence", version: 1,
            created_at: "2026-09-15T10:00:00Z", text,
            chunks: [
              { id: "earlier", text: `Earlier agreement: ${quote}`, location: { line_start: 1, line_end: 1 } },
              { id: "current", text: "Current agreement:\nNotify us within\n24 hours.\nKeep supporting records.", location: { line_start: 103, line_end: 106 } },
            ],
          }
        : { status: "ready" };
    await route.fulfill({ json: body });
  });
});

test("source link highlights only the anchored quote with original whitespace", async ({ page }) => {
  await page.goto(`/documents/source#${new URLSearchParams({ chunk: "current", quote })}`);
  const highlight = page.locator("mark.source-highlight");
  await expect(highlight).toHaveCount(1);
  await expect(highlight).toHaveText(quote);
  expect(await highlight.textContent()).toBe("Notify us\twithin\n24 hours.");
  expect(await highlight.evaluate((node) => node.previousSibling?.textContent)).toBe(text.slice(0, text.indexOf("Notify us\t")));
  await expect(highlight).toBeInViewport();
  await expect(page.getByText("Citation excerpts", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Cited excerpt", exact: true })).toHaveCount(0);
});

test("missing or malicious quotes and legacy links never highlight a whole chunk", async ({ page }) => {
  for (const query of [new URLSearchParams({ chunk: "current", quote: '<img src=x onerror="alert(1)">' }), new URLSearchParams({ chunk: "current" }), new URLSearchParams({ chunk: "missing", quote })]) {
    await page.goto(`/documents/source?${query}`);
    await expect(page.getByRole("heading", { name: "Full document", exact: true })).toBeVisible();
    await expect(page.locator("mark.source-highlight")).toHaveCount(0);
    await expect(page.getByRole("status").filter({ hasText: "highlight" })).toBeVisible();
    await expect(page.locator("img[src=x]")).toHaveCount(0);
  }
});

test("ambiguous passages are reported and punctuation stays literal", async () => {
  const { locateSource, sourceHref } = await import("../../lib/source");
  const document = {
    id: "source", filename: "Agreement.txt", kind: "evidence" as const,
    version: 1, created_at: "2026-09-15T10:00:00Z",
    text: "Repeated paragraph.\nRepeated paragraph.",
    chunks: [{ id: "repeated", text: "Repeated paragraph.", location: {} }],
  };
  expect(locateSource(document, "repeated", "paragraph").notice).toContain("Multiple matching");
  document.text = "Amount [1.5] (USD)?\nFinish.";
  document.chunks = [{ id: "literal", text: document.text, location: {} }];
  const selection = locateSource(document, "literal", "[1.5] (USD)?");
  expect(document.text.slice(selection.start, selection.end)).toBe("[1.5] (USD)?");
  document.text = "Repeat repeat repeat.";
  document.chunks = [{ id: "twice", text: document.text, location: {} }];
  expect(locateSource(document, "twice", "repeat").notice).toContain("more than once");
  const href = sourceHref({ document_id: "source", chunk_id: "literal", quote: "[1.5] (USD)?", location: {} });
  expect(href).toMatch(/^\/documents\/source#chunk=/);
  expect(new URLSearchParams(href.split("#")[1]).get("quote")).toBe("[1.5] (USD)?");
});

test("a citation starting in its anchor highlights original text across chunk boundaries", async ({ page }) => {
  const crossQuote = "Notify us within 24 hours of discovery.";
  const prefix = `${crossQuote}\n${crossQuote}\nCurrent obligations:\n`;
  const anchor = "Current obligations:\nNotify us within";
  const crossText = `${prefix}Notify us\twithin\n24 hours of discovery.\nUnrelated later obligation.`;
  await page.route("**/api/documents/source", (route) => route.fulfill({ json: {
    id: "source", filename: "Agreement.txt", kind: "evidence", version: 1,
    created_at: "2026-09-16T10:00:00Z", text: crossText,
    chunks: [
      { id: "current", text: anchor, location: { line_start: 3, line_end: 4 } },
      { id: "next", text: "24 hours of discovery.\nUnrelated later obligation.", location: { line_start: 5, line_end: 6 } },
    ],
  } }));
  await page.goto(`/documents/source#${new URLSearchParams({ chunk: "current", quote: crossQuote })}`);
  const highlight = page.locator("mark.source-highlight");
  await expect(highlight).toHaveCount(1);
  expect(await highlight.textContent()).toBe("Notify us\twithin\n24 hours of discovery.");
  expect(await highlight.evaluate((node) => node.previousSibling?.textContent)).toBe(prefix);
  await page.goto(`/documents/source#${new URLSearchParams({ chunk: "current", quote: "Unrelated later obligation." })}`);
  await expect(page.locator("mark.source-highlight")).toHaveCount(0);
  await expect(page.getByRole("status")).toContainText("could not be found");
});

test("cross-boundary matching rejects ambiguous starts and missing or repeated anchors", async () => {
  const { locateSource } = await import("../../lib/source");
  const document = {
    id: "source", filename: "Agreement.txt", kind: "evidence" as const,
    version: 1, created_at: "2026-09-16T10:00:00Z",
    text: "Intro repeat repeat repeat repeat end.",
    chunks: [{ id: "anchor", text: "Intro repeat repeat", location: {} }],
  };
  expect(locateSource(document, "anchor", "repeat repeat repeat").notice).toContain("more than once");
  document.text = "Intro repeat repeat\nIntro repeat repeat repeat repeat end.";
  expect(locateSource(document, "anchor", "repeat repeat repeat").notice).toContain("Multiple matching");
  document.text = "Unrelated text.";
  expect(locateSource(document, "anchor", "repeat repeat repeat").notice).toContain("could not be located");
});
