// 記事用スクショ撮影ユーティリティ（テストではない）。
//   node capture.mjs <email> <password> <conversation-title-prefix> <out.png>
// ログインして、タイトルが一致する会話を開き、その画面を撮る。
import { chromium } from "@playwright/test";

const [email, password, titlePrefix, out] = process.argv.slice(2);
const baseURL = process.env.BASE_URL;
if (!baseURL) throw new Error("BASE_URL is required (terraform output cloudfront_url)");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, locale: "ja-JP" });
await page.goto(baseURL);
await page.getByTestId("email").fill(email);
await page.getByTestId("password").fill(password);
await page.getByTestId("auth-submit").click();
await page.getByTestId("me").waitFor();
const item = page.getByTestId("conv-item").filter({ hasText: titlePrefix }).first();
await item.click();
await page.getByTestId("msg-assistant").first().waitFor();
await page.waitForTimeout(500);
await page.screenshot({ path: out });
console.log(`saved ${out}`);
await browser.close();
