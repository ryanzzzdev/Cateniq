import { expect, test } from "@playwright/test";

// Perf harness spec — run via `npx playwright test -c playwright.perf.config.ts`.
// Measures the ~100k-point corridor workload; numbers feed the budgets in
// docs/project/features/workbench.md and the evidence record.

test("100k-point workload: load, select, edit latency, resources", async ({
  page,
}) => {
  // corridor-perf is served alongside corridor-a/b/adverse by the harness.
  await page.goto("/");
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-a/, {
    timeout: 60000,
  });
  // Clock starts before the triggering action so the whole load is measured.
  const t0 = Date.now();
  await page.getByLabel("dataset").selectOption("corridor-perf");
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-perf/, {
    timeout: 60000,
  });
  const loadMs = Date.now() - t0;

  // Frame sampling must isolate the declared workload: fix the camera on the
  // perf corridor, let it settle, then reset the sample window and measure a
  // defined interval — no corridor-a or transition frames in the stats.
  await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.setCamera([200, -140, 90], [200, 0, 10]),
  );
  await page.waitForTimeout(1000);
  await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.resetFrameStats(),
  );
  await page.waitForTimeout(3000); // defined measurement window
  const frames = await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.frameStats(),
  );
  const heap0 = await page.evaluate(
    () => (performance as any).memory?.usedJSHeapSize ?? 0,
  );
  const res0 = await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.resourceStats(),
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

  // Dataset switch away and back — resource counts must return to baseline
  // (clearData disposes geometry/materials; no accumulation). The switch is
  // gated by the unsaved-edits confirm dialog — accept it.
  page.once("dialog", (d) => void d.accept());
  await page.getByLabel("dataset").selectOption("corridor-a");
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-a/, {
    timeout: 15000,
  });
  const resA = await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.resourceStats(),
  );
  await page.getByLabel("dataset").selectOption("corridor-perf");
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-perf/, {
    timeout: 60000,
  });
  await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.setCamera([200, -140, 90], [200, 0, 10]),
  );
  await page.waitForTimeout(120);
  const res1 = await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.resourceStats(),
  );
  const heap1 = await page.evaluate(
    () => (performance as any).memory?.usedJSHeapSize ?? 0,
  );
  // Second round-trip: object count must stay bounded.
  page.once("dialog", (d) => void d.accept());
  await page.getByLabel("dataset").selectOption("corridor-b");
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-b/, {
    timeout: 15000,
  });
  await page.getByLabel("dataset").selectOption("corridor-perf");
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-perf/, {
    timeout: 60000,
  });
  const heap2 = await page.evaluate(
    () => (performance as any).memory?.usedJSHeapSize ?? 0,
  );

  const pointCount = await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.countPoints(),
  );
  const children = await page.evaluate(
    () => (window as any).__cateniq_perf.scene.scene.children.length,
  );
  const geoProbe = await page.evaluate(() => {
    const scene = (window as any).__cateniq_perf.scene;
    let live = 0;
    scene.scene.traverse((o: any) => {
      if (o.geometry) live++;
    });
    return { liveGeometries: live };
  });
  console.log("GEOPROBE", JSON.stringify(geoProbe));

  console.log(
    `PERF ${JSON.stringify({
      pointCount,
      loadMs,
      selectMs,
      editMs,
      commitMs,
      frames,
      heapMB0: Math.round(heap0 / 1048576),
      heapMB1: Math.round(heap1 / 1048576),
      heapMB2: Math.round(heap2 / 1048576),
      children,
      res0,
      resA,
      res1,
    })}`,
  );
  expect(pointCount).toBeGreaterThan(95000);
  // Resource observations: scene objects rebuilt identically (no stale-object
  // growth) and draw load returns to baseline at the same camera pose.
  expect(children).toBe(geoProbe.liveGeometries);
  expect(res1.calls).toBeLessThanOrEqual(res0.calls + 1);
});
