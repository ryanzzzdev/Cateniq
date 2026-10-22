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

  // Local edits after acceptance: the badge must scope itself to the
  // saved revision and Accept must stay disabled while dirty — the
  // displayed geometry is no longer the accepted geometry.
  await editB1AndCommit(page, "9");
  await expect(page.getByTestId("accepted-badge")).toContainText(
    "unsaved edits differ",
  );
  await expect(page.getByTestId("accept-button")).toBeDisabled();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("accepted-badge")).not.toContainText(
    "unsaved edits differ",
  );
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

test("a save landing late preserves edits made while it was in flight", async ({
  page,
}) => {
  let release!: () => void;
  const held = new Promise<void>((r) => {
    release = r;
  });
  await page.route("**/review/operations", async (route) => {
    const response = await route.fetch();
    await held;
    await route.fulfill({ response });
  });
  await loadCorridorB(page);
  await editB1AndCommit(page, "10.2");
  await page.getByTestId("save-button").click();
  await expect(
    page.getByRole("button", { name: "Saving…" }),
  ).toBeVisible();

  // A newer local edit commits while the save response is delayed.
  await editB1AndCommit(page, "10.4");
  release();
  // The response acks only the submitted edits — the newer one survives
  // as an unsaved local change on top of the saved baseline.
  await expect(page.getByTestId("unsaved-note")).toContainText(
    "1 local edit",
    { timeout: 15000 },
  );
  await expect(page.getByTestId("coord-b-2")).toHaveValue("10.40");
});

test("an undo during a pending save survives as an unsaved edit", async ({
  page,
}) => {
  let release!: () => void;
  const held = new Promise<void>((r) => {
    release = r;
  });
  await page.route("**/review/operations", async (route) => {
    const response = await route.fetch();
    await held;
    await route.fulfill({ response });
  });
  await loadCorridorB(page);
  await selectB1(page);
  const baseline = await page.getByTestId("coord-b-2").inputValue();
  await editB1AndCommit(page, "10.8");
  await page.getByTestId("save-button").click();
  await expect(page.getByRole("button", { name: "Saving…" })).toBeVisible();

  // The user undoes the submitted edit while the save is in flight.
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByTestId("coord-b-2")).toHaveValue(baseline);
  release();

  // The ack must not silently reverse the undo: the saved baseline is
  // z=10.80 but the user's reverted geometry stays as an unsaved edit.
  await expect(page.getByTestId("unsaved-note")).toContainText(
    "1 local edit",
    { timeout: 15000 },
  );
  await expect(page.getByTestId("coord-b-2")).toHaveValue(baseline);
  // And it remains undoable — removing it reveals the saved baseline.
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByTestId("coord-b-2")).toHaveValue("10.80");
});

test("a failed save re-enables retry and replays the operation", async ({
  page,
}) => {
  await loadCorridorB(page);
  await editB1AndCommit(page, "10.6");

  // The first attempt never reaches the server.
  let aborted = false;
  await page.route("**/review/operations", async (route) => {
    if (!aborted) {
      aborted = true;
      await route.abort();
    } else {
      await route.continue();
    }
  });
  await page.getByTestId("save-button").click();
  // The error is reported and — critically — Save is usable again:
  // the local edit is preserved and retry is not permanently disabled.
  await expect(page.getByTestId("save-button")).toBeEnabled({
    timeout: 15000,
  });
  await expect(page.getByTestId("unsaved-note")).toContainText(
    "1 local edit",
  );

  await page.getByTestId("save-button").click();
  await expect(page.getByTestId("unsaved-note")).toHaveCount(0, {
    timeout: 15000,
  });
  const rev = await page.getByTestId("revision").textContent();
  expect(rev).toMatch(/rev \d+/);
});
