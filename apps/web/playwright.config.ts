import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // perf runs under playwright.perf.config.ts; demo recordings under
  // playwright.demo.config.ts with their own database — neither may
  // mutate the shared verification database this suite uses.
  testIgnore: ["perf.spec.ts", "demo.spec.ts"],
  use: { baseURL: "http://localhost:4173" },
  webServer: [
    {
      command: "npm run build && npm run preview -- --port 4173 --strictPort",
      url: "http://localhost:4173",
      reuseExistingServer: !process.env.CI,
    },
    {
      command:
        "cd ../../backend && rm -f .e2e-reviews.db && CATENIQ_DB_PATH=.e2e-reviews.db uv run uvicorn cateniq.app:app --port 8000",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
