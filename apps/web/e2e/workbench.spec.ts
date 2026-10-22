import { expect, test, type Page } from "@playwright/test";

type Vec3 = [number, number, number];

interface SceneProbe {
  worldToScreen(p: Vec3): { x: number; y: number };
}

async function loadCorridorA(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-a/, {
    timeout: 15000,
  });
}

async function selectS2(page: Page) {
  await page.getByRole("button", { name: /^S2/ }).click();
  await expect(page.getByTestId("endpoint-dev")).toContainText("b 1.5");
}

test("endpoint correction journey: inspect → edit → commit → validate → undo/redo", async ({
  page,
}) => {
  await loadCorridorA(page);

  // Diagnostic queue surfaces the computed endpoint mismatch on S2.
  await expect(
    page.getByRole("button", { name: /^S2/ }).locator(".queue-issue"),
  ).toContainText("endpoint_mismatch");
  await selectS2(page);

  // Numeric editing: z 10.5 → 12 (the true P3:high candidate).
  const zInput = page.getByTestId("coord-b-2");
  await zInput.click();
  await expect(page.getByTestId("draft-panel")).toBeVisible();
  await zInput.fill("12");
  await expect(page.getByTestId("displacement")).toHaveText("1.500 m");

  await page.getByRole("button", { name: "Commit" }).click();
  await expect(page.getByTestId("unsaved-note")).toContainText("1 local edit");

  // Validate: constrained refit against the corrected attachments.
  await page.getByRole("button", { name: "Validate correction" }).click();
  await expect(page.getByTestId("fit-result")).toContainText("refit: ok");
  await expect(page.getByTestId("fit-result")).toContainText("rms 0.0");

  // Undo restores the prediction; redo reapplies.
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("coord-b-2")).toHaveValue("10.50");
  await expect(page.getByTestId("fit-result")).toContainText("stale");
  await page.keyboard.press("Control+Shift+z");
  await expect(page.getByTestId("coord-b-2")).toHaveValue("12.00");
});

test("cancel restores the pre-draft endpoint", async ({ page }) => {
  await loadCorridorA(page);
  await selectS2(page);
  const z = page.getByTestId("coord-b-2");
  await z.click();
  await z.fill("9.9");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("coord-b-2")).toHaveValue("10.50");
  await expect(page.getByTestId("unsaved-note")).toHaveCount(0);
});

test("ambiguous/no-hit click does not move an arbitrary object", async ({
  page,
}) => {
  await loadCorridorA(page);
  await selectS2(page);
  // Click near the top-left corner of the viewport — empty sky.
  await page.locator('[data-testid="viewport"]').click({
    position: { x: 15, y: 15 },
  });
  // Nothing selected, nothing moved.
  await expect(page.getByTestId("endpoint-dev")).toHaveCount(0);
  await page.getByRole("button", { name: /^S2/ }).click();
  await expect(page.getByTestId("coord-b-2")).toHaveValue("10.50");
  await expect(page.getByTestId("unsaved-note")).toHaveCount(0);
});

test("dragging the endpoint handle snaps to a support candidate", async ({
  page,
}) => {
  await loadCorridorA(page);
  await selectS2(page);
  const probe = await page.evaluate(
    () => (window as any).__cateniq_perf.scene as SceneProbe | undefined,
  );
  expect(probe).toBeDefined();
  const to = await page.evaluate(() => {
    const scene = (window as any).__cateniq_perf.scene as SceneProbe;
    return scene.worldToScreen([95, 0, 12]); // P3:high candidate
  });
  const from = await page.evaluate(() => {
    const scene = (window as any).__cateniq_perf.scene as SceneProbe;
    return scene.worldToScreen([95, 0, 10.5]); // predicted attach_b
  });
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(to.x, to.y, { steps: 8 });
  await page.mouse.up();
  await expect(page.getByTestId("unsaved-note")).toContainText("1 local edit");
  await expect(page.getByTestId("coord-b-2")).toHaveValue("12.00");
});
