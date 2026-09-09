// 新しい会話でメッセージを送り、応答完了後の画面（長期記憶の参照注記を含む）を撮る。
//   node capture-live.mjs <email> <password> "<message>" <out.png>
import { chromium } from "@playwright/test";

const [email, password, message, out] = process.argv.slice(2);
const baseURL = process.env.BASE_URL;
if (!baseURL) throw new Error("BASE_URL is required (terraform output cloudfront_url)");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, locale: "ja-JP" });
await page.goto(baseURL);
await page.getByTestId("email").fill(email);
await page.getByTestId("password").fill(password);
await page.getByTestId("auth-submit").click();
await page.getByTestId("me").waitFor();
await page.getByTestId("new-chat").click();
await page.getByTestId("input").fill(message);
await page.getByTestId("send").click();
await page.getByTestId("assistant-final").waitFor({ timeout: 90_000 });
await page.waitForTimeout(800);
await page.screenshot({ path: out });
console.log(`saved ${out}`);
console.log("reply:", await page.getByTestId("assistant-final").innerText());
const note = page.getByTestId("memory-note");
if (await note.count()) console.log("note:", await note.innerText());
await browser.close();
