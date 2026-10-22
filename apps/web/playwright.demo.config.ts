import { defineConfig } from "@playwright/test";

// Demo recording config — same app/backend as playwright.config.ts but an
// isolated database and always-on video. Run:
//   npx playwright test -c playwright.demo.config.ts
export default defineConfig({
  testDir: "./e2e",
  testMatch: "demo.spec.ts",
  workers: 1,
  use: {
    baseURL: "http://localhost:4173",
    video: { mode: "on", size: { width: 1280, height: 800 } },
  },
  webServer: [
    {
      command: "npm run build && npm run preview -- --port 4173 --strictPort",
      url: "http://localhost:4173",
      reuseExistingServer: !process.env.CI,
    },
    {
      command:
        "cd ../../backend && rm -f .e2e-demo.db* && CATENIQ_DB_PATH=.e2e-demo.db uv run uvicorn cateniq.app:app --port 8000",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
