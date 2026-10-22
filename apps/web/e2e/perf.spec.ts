import { expect, test } from "@playwright/test";

// Perf harness spec — run via `npx playwright test -c playwright.perf.config.ts`.
// Measures the ~100k-point corridor workload; numbers feed the budgets in
// docs/project/features/workbench.md.

test("100k-point workload: load, select, edit latency", async ({ page }) => {
  const t0 = Date.now();
  await page.goto("/");
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-perf/, {
    timeout: 60000,
  });
  const loadMs = Date.now() - t0;

  // Let the render loop settle, then sample frame deltas.
  await page.waitForTimeout(1500);
  const frames = await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.frameStats(),
  );

  const selT0 = performance.now();
  await page.getByRole("button", { name: /^K2-3/ }).click();
  await expect(page.getByTestId("endpoint-dev")).toBeVisible();
  const selectMs = performance.now() - selT0;

  // Numeric endpoint edit latency.
  const zInput = page.getByTestId("coord-b-2");
  const eT0 = performance.now();
  await zInput.click();
  await zInput.fill("12.4");
  await expect(page.getByTestId("draft-panel")).toBeVisible();
  const editMs = performance.now() - eT0;

  const commitT0 = performance.now();
  await page.getByRole("button", { name: "Commit" }).click();
  await expect(page.getByTestId("unsaved-note")).toContainText("1 local edit");
  const commitMs = performance.now() - commitT0;

  const pointCount = await page.evaluate(() => {
    const scene = (window as any).__cateniq_perf.scene;
    return scene.countPoints();
  });

  console.log(
    `PERF ${JSON.stringify({ pointCount, loadMs, selectMs, editMs, commitMs, frames })}`,
  );
  expect(pointCount).toBeGreaterThan(95000);
});
