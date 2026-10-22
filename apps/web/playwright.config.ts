import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:4173" },
  webServer: [
    {
      command: "npm run build && npm run preview -- --port 4173 --strictPort",
      url: "http://localhost:4173",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "cd ../../backend && uv run uvicorn cateniq.app:app --port 8000",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
