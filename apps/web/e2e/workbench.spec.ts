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

test("co-located handles: the selected span's visible handle wins", async ({
  page,
}) => {
  await loadCorridorA(page);
  await page.getByRole("button", { name: /^S2/ }).click();
  await page.waitForTimeout(200); // let the camera settle on the selection
  // S1's b-handle and S2's a-handle share the world point (50, 0, 12).
  const px = await page.evaluate(() => {
    const scene = (window as any).__cateniq_perf.scene;
    return scene.worldToScreen([50, 0, 12]);
  });
  await page.mouse.move(px.x, px.y);
  await page.mouse.down();
  await page.mouse.move(px.x + 6, px.y + 6, { steps: 3 }); // keep draft alive
  await expect(page.getByTestId("draft-panel")).toContainText("endpoint a");
  await page.keyboard.press("Escape"); // cancel before release → no command
  await page.mouse.up();

  await page.getByRole("button", { name: /^S1/ }).click();
  await page.waitForTimeout(200); // camera re-aims at S1 — reproject
  const px1 = await page.evaluate(() => {
    const scene = (window as any).__cateniq_perf.scene;
    return scene.worldToScreen([50, 0, 12]);
  });
  await page.mouse.move(px1.x, px1.y);
  await page.mouse.down();
  await page.mouse.move(px1.x + 6, px1.y + 6, { steps: 3 });
  await expect(page.getByTestId("draft-panel")).toContainText("endpoint b");
  await page.keyboard.press("Escape"); // cancel before release → no command
  await page.mouse.up();
  // Neither ambiguous pick committed an edit — only drafts were exercised.
  await expect(page.getByTestId("unsaved-note")).toHaveCount(0);
});

test("occluded handle cannot be dragged through a pole", async ({ page }) => {
  await loadCorridorA(page);
  await selectS2(page);
  // Bird's-eye camera straight above P3: the pole post (top 12.0) occludes
  // the b-handle below it (10.5). The pick must be intercepted by the post.
  await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.setCamera([95, 0, 45], [95, 0, 10]),
  );
  await page.waitForTimeout(400); // let damped controls converge
  const px = await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.worldToScreen([95, 0, 10.5]),
  );
  // Identify what intercepts the click. Two blocker layers lie over the
  // handle: corridor context points and the P3 post. Peeling them must
  // change the identified interceptor at each step — discriminating
  // evidence that blocking, not incidental geometry, prevents the grab.
  const pickAt = () =>
    page.evaluate(
      (p) => (window as any).__cateniq_perf.scene.pickAtScreen(p.x, p.y),
      px,
    );
  const setBlocker = (id: string, on: boolean) =>
    page.evaluate(
      ([id, on]) =>
        (window as any).__cateniq_perf.scene.scene.traverse((o: any) => {
          if (o.userData?.pickId === id) o.userData.blocker = on;
        }),
      [id, on] as const,
    );

  await expect.poll(pickAt).toMatchObject({
    kind: "none",
    hitType: "blocker",
    hitId: "context",
  });
  // The context cloud is the first interceptor; hiding it (invisible objects
  // are skipped, not merely unblocked) exposes the P3 post underneath.
  await page.evaluate(() => {
    (window as any).__cateniq_perf.scene.scene.traverse((o: any) => {
      if (o.userData?.pickId === "context") o.visible = false;
    });
  });
  await expect.poll(pickAt).toMatchObject({
    kind: "none",
    hitType: "blocker",
    hitId: "pole:P3",
  });

  // Discriminating control — run while S2 is still selected so its handle is
  // visible. The ray's remaining stack above the handle is: S3's geometry
  // (endpoint at the same pole), then S2's own conductor points, then the
  // handle. Peeling each layer must change the pick outcome — evidence the
  // blockers were decisive, not incidental coordinates.
  await setBlocker("pole:P3", false);
  await expect.poll(pickAt).toMatchObject({ kind: "span", spanId: "S3" });
  const hideSpanGeometry = (id: string, show: boolean) =>
    page.evaluate(
      ([id, show]) =>
        (window as any).__cateniq_perf.scene.scene.traverse((o: any) => {
          if (o.userData?.spanId === id && !o.userData?.type) {
            o.visible = show;
          }
        }),
      [id, show] as const,
    );
  await hideSpanGeometry("S3", false);
  await expect.poll(pickAt).toMatchObject({ kind: "span", spanId: "S2" });
  await hideSpanGeometry("S2", false);
  await expect.poll(pickAt).toMatchObject({
    kind: "handle",
    spanId: "S2",
    which: "b",
  });
  await page.mouse.move(px.x, px.y);
  await page.mouse.down();
  await page.mouse.move(px.x + 6, px.y + 6, { steps: 3 });
  await expect(page.getByTestId("draft-panel")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.mouse.up();

  // Restore every peeled layer. The drag above re-aimed the camera at S2's
  // midpoint, so return overhead and reproject before the held-pointer
  // check: pressing the occluded pixel must start no draft and must clear
  // the selection while the button is still down.
  await setBlocker("pole:P3", true);
  await page.evaluate(() => {
    (window as any).__cateniq_perf.scene.scene.traverse((o: any) => {
      if (o.userData?.pickId === "context") o.visible = true;
    });
  });
  await hideSpanGeometry("S3", true);
  await hideSpanGeometry("S2", true);
  await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.setCamera([95, 0, 45], [95, 0, 10]),
  );
  await page.waitForTimeout(400);
  const px2 = await page.evaluate(() =>
    (window as any).__cateniq_perf.scene.worldToScreen([95, 0, 10.5]),
  );
  const restored = await page.evaluate(
    (p) => (window as any).__cateniq_perf.scene.pickAtScreen(p.x, p.y),
    px2,
  );
  expect(restored).toMatchObject({ kind: "none", hitType: "blocker" });
  await page.mouse.move(px2.x, px2.y);
  await page.mouse.down();
  await expect(page.getByTestId("draft-panel")).toHaveCount(0);
  await expect(page.getByTestId("endpoint-dev")).toHaveCount(0);
  await page.mouse.up();

  // Nothing was committed through either path.
  await page.getByRole("button", { name: /^S2/ }).click();
  await expect(page.getByTestId("coord-b-2")).toHaveValue("10.50");
  await expect(page.getByTestId("unsaved-note")).toHaveCount(0);
});
