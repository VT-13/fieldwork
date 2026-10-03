import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["json", { outputFile: "../docs/module3/browser-results.json" }],
  ],
  use: {
    baseURL: "http://localhost:13030",
    headless: true,
    trace: "retain-on-failure",
    launchOptions: {
      executablePath: process.env.FIELDWORK_BROWSER_EXECUTABLE || undefined,
    },
  },
  webServer: {
    command: "node scripts/test-server.mjs",
    url: "http://localhost:13030/login",
    reuseExistingServer: false,
    env: {
      APP_ORIGIN: "http://localhost:13030",
      BACKEND_URL: "http://127.0.0.1:18030",
    },
  },
});
