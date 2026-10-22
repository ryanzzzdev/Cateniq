import { expect, test, type Page } from "@playwright/test";

// Demo walkthrough — recorded to video by playwright.demo.config.ts.
// Not part of the verification suite: paced for viewing, uses its own
// database (.e2e-demo.db) so it can run in any order alongside the tests.

const BEAT = 700; // ms pause so a viewer can follow each step

async function load(page: Page, dataset: string) {
  await page.goto("/");
  await page.getByLabel("dataset").selectOption(dataset);
  await expect(page.getByTestId("load-status")).toHaveText(
    new RegExp(dataset),
    { timeout: 15000 },
  );
  await page.waitForTimeout(BEAT);
}

test("correction journey: diagnose, correct, save, reopen, export", async ({
  page,
}) => {
  await load(page, "corridor-a");

  // The diagnostic queue flags S2's endpoint and S4's residuals.
  await expect(
    page.getByRole("button", { name: /^S2/ }).locator(".queue-issue"),
  ).toBeVisible();
  await page.getByRole("button", { name: /^S2/ }).click();
  await page.waitForTimeout(BEAT);

  // S2's attach_b sits at 10.50 — the prediction deviates from the
  // observed pole top. Correct it to 12.
  const zInput = page.getByTestId("coord-b-2");
  await zInput.click();
  await zInput.fill("12");
  await page.waitForTimeout(BEAT);
  await page.getByRole("button", { name: "Commit" }).click();
  await page.waitForTimeout(BEAT);

  // Corrections are reversible — undo, redo, then keep it.
  await page.keyboard.press("Control+z");
  await expect(zInput).toHaveValue("10.50");
  await page.waitForTimeout(BEAT);
  await page.keyboard.press("Control+y");
  await expect(zInput).toHaveValue("12.00");
  await page.waitForTimeout(BEAT);

  // Save the correction as a durable revision.
  await page.getByTestId("save-button").click();
  await expect(page.getByTestId("revision")).toHaveText("rev 1");
  await page.waitForTimeout(BEAT);

  // Revalidate: S2 is resolved; S4's two residual issues honestly remain.
  await page.getByTestId("run-button").click();
  await expect(page.getByTestId("run-status")).toContainText("succeeded", {
    timeout: 15000,
  });
  await expect(page.getByTestId("run-status")).toContainText("2 issue(s)");
  await page.waitForTimeout(BEAT);

  // Reopen: the saved correction is the restored baseline.
  await load(page, "corridor-a");
  await page.getByRole("button", { name: /^S2/ }).click();
  await expect(zInput).toHaveValue("12.00");
  await expect(page.getByTestId("revision")).toHaveText("rev 1");
  await page.waitForTimeout(BEAT);

  // Provenance: the export reconstructs through the verifier.
  const doc = await page.request
    .get("/api/datasets/corridor-a/review/export")
    .then((r) => r.json());
  const verified = await page.request
    .post("/api/export/verify", { data: { export: doc } })
    .then((r) => r.json());
  expect(verified.ok).toBe(true);
  await page.waitForTimeout(BEAT);
});

test("review completion: validate, accept, and a conflicting session", async ({
  page,
  context,
}) => {
  await load(page, "corridor-b");

  // corridor-b's predictions validate clean as extracted — a run at the
  // initial revision reports no issues and can be accepted directly.
  await page.getByRole("button", { name: /^B1/ }).click();
  await page.waitForTimeout(BEAT);
  await page.getByTestId("run-button").click();
  await expect(page.getByTestId("run-status")).toContainText("0 issue", {
    timeout: 15000,
  });
  await page.getByTestId("accept-button").click();
  await expect(page.getByTestId("accepted-badge")).toContainText("accepted");
  await page.waitForTimeout(BEAT);

  // A second session edits from the shared base — a proposed correction.
  const page2 = await context.newPage();
  await load(page2, "corridor-b");
  await page2.getByRole("button", { name: /^B1/ }).click();
  await page2.getByTestId("coord-b-2").fill("9");
  await page2.getByRole("button", { name: "Commit" }).click();
  await page.waitForTimeout(BEAT);

  // Session 1 also edits B1 and saves first, advancing the revision.
  await page.getByRole("button", { name: /^B1/ }).click();
  const zInput = page.getByTestId("coord-b-2");
  await zInput.click();
  await zInput.fill("10.5");
  await page.getByRole("button", { name: "Commit" }).click();
  await page.getByTestId("save-button").click();
  await expect(page.getByTestId("revision")).toHaveText("rev 1");
  await page.waitForTimeout(BEAT);

  // Session 2's save conflicts — its edit survives as an inspectable
  // local change, nothing is silently overwritten.
  await page2.getByTestId("save-button").click();
  await expect(page2.getByTestId("save-conflict")).toBeVisible();
  await expect(page2.getByTestId("unsaved-note")).toContainText(
    "1 local edit",
  );
  await page.waitForTimeout(BEAT * 2);
});
