import { expect, test } from "@playwright/test";

test("workbench loads the corridor and populates the diagnostic queue", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Cateniq/);
  await expect(page.getByRole("heading", { name: "Cateniq" })).toBeVisible();
  await expect(page.getByTestId("load-status")).toHaveText(/corridor-a/, {
    timeout: 15000,
  });
  await expect(
    page.getByRole("button", { name: /^S2/ }).locator(".queue-issue"),
  ).toContainText("endpoint_mismatch");
});
