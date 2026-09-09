import { defineConfig, devices } from "@playwright/test";

function requireBaseUrl(): string {
  const url = process.env.BASE_URL;
  if (!url) throw new Error("BASE_URL is required (terraform output cloudfront_url)");
  return url;
}

// 実環境に対して実行する。BASE_URL は terraform output cloudfront_url（必須）。
export default defineConfig({
  testDir: "./tests",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: requireBaseUrl(),
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    viewport: { width: 1280, height: 800 },
    locale: "ja-JP",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
