import { expect, test, type Page } from "@playwright/test";

// The durable store makes the shared e2e database stateful: these tests
// use corridor-b exclusively, which no other spec mutates. Order inside
// the file matters — acceptance runs first while the revision is still 0,
// then saves advance the revision deterministically.
async function loadCorridorB(page: Page) {
  await page.goto("/");
  await page.getByLabel("dataset").selectOption("corridor-b");
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-b/, {
    timeout: 15000,
  });
}

async function selectB1(page: Page) {
  await page.getByRole("button", { name: /^B1/ }).click();
}

async function editB1AndCommit(page: Page, z: string) {
  await selectB1(page);
  const zInput = page.getByTestId("coord-b-2");
  await zInput.click();
  await zInput.fill(z);
  await page.getByRole("button", { name: "Commit" }).click();
}

test("a clean run can be accepted for the current revision", async ({
  page,
}) => {
  await loadCorridorB(page);
  await selectB1(page);
  await page.getByTestId("run-button").click();
  await expect(page.getByTestId("run-status")).toContainText("succeeded", {
    timeout: 15000,
  });
  await expect(page.getByTestId("run-status")).toContainText("0 issue");
  await page.getByTestId("accept-button").click();
  await expect(page.getByTestId("accepted-badge")).toContainText("accepted");
});

test("save then reopen restores the durable correction", async ({ page }) => {
  await loadCorridorB(page);
  // B1's predicted attach_b is (48, 0, 11.5) — correct it to the
  // Q2:mid candidate height.
  await editB1AndCommit(page, "10");
  await page.getByTestId("save-button").click();
  await expect(page.getByTestId("unsaved-note")).toHaveCount(0);
  await expect(page.getByTestId("revision")).toHaveText("rev 1");

  // Reopen: the saved constraint is the restored baseline, not a lost draft.
  // The dataset selector resets on reload — reopen corridor-b explicitly.
  await loadCorridorB(page);
  await selectB1(page);
  await expect(page.getByTestId("coord-b-2")).toHaveValue("10.00");
  await expect(page.getByTestId("unsaved-note")).toHaveCount(0);
});

test("a stale save is rejected and the losing edits stay inspectable", async ({
  page,
  context,
}) => {
  await loadCorridorB(page);
  const page2 = await context.newPage();
  await loadCorridorB(page2);

  // Session 2 commits and saves first, advancing the revision.
  await editB1AndCommit(page2, "9.5");
  await page2.getByTestId("save-button").click();
  await expect(page2.getByTestId("unsaved-note")).toHaveCount(0);

  // Session 1 loaded at the older revision; its save must conflict.
  await editB1AndCommit(page, "9");
  await page.getByTestId("save-button").click();
  await expect(page.getByTestId("save-conflict")).toBeVisible();
  // The losing session's edit is preserved as an inspectable local change.
  await expect(page.getByTestId("unsaved-note")).toContainText(
    "1 local edit",
  );
  await expect(page.getByTestId("coord-b-2")).toHaveValue("9.00");

  await page2.close();
});

test("the exported review reconstructs through the verifier", async ({
  page,
}) => {
  await loadCorridorB(page);
  const doc = await page.request
    .get("/api/datasets/corridor-b/review/export")
    .then((r) => r.json());
  expect(doc.schema_version).toBe(1);
  const verified = await page.request
    .post("/api/export/verify", { data: { export: doc } })
    .then((r) => r.json());
  expect(verified.ok).toBe(true);
  expect(verified.dataset_id).toBe("corridor-b");
});
