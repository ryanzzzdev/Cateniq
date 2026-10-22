import { expect, test } from "@playwright/test";

test("workbench shell loads and reports API health", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Cateniq/);
  await expect(page.getByRole("heading", { name: "Cateniq" })).toBeVisible();
  await expect(page.getByTestId("api-status")).toHaveText("ok");
});
