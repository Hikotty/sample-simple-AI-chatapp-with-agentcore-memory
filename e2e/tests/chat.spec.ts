import { test, expect, Page } from "@playwright/test";

const email = `e2e-${Date.now()}@example.com`;
const password = "Passw0rd123";

async function signup(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("auth-submit")).toBeVisible();
  await page.getByTestId("auth-toggle").click();
  await expect(page.getByTestId("auth-submit")).toHaveText("アカウント作成");
  await page.getByTestId("email").fill(email);
  await page.getByTestId("password").fill(password);
  await page.getByTestId("auth-submit").click();
  await expect(page.getByTestId("me")).toHaveText(email);
}

async function login(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("auth-submit")).toBeVisible();
  await page.getByTestId("email").fill(email);
  await page.getByTestId("password").fill(password);
  await page.getByTestId("auth-submit").click();
  await expect(page.getByTestId("me")).toHaveText(email);
}

async function send(page: Page, text: string) {
  const before = await page.getByTestId("assistant-final").count();
  await page.getByTestId("input").fill(text);
  await page.getByTestId("send").click();
  await expect(page.getByTestId("msg-user").last()).toContainText(text);
  // ストリーミング完了（assistant-final が 1 つ増える）を待つ
  await expect(page.getByTestId("assistant-final")).toHaveCount(before + 1, { timeout: 90_000 });
  const reply = await page.getByTestId("assistant-final").last().innerText();
  expect(reply.length).toBeGreaterThan(0);
  expect(reply).not.toContain("エラー");
  return reply;
}

test.describe.serial("memchat E2E（実環境）", () => {
  test("サインアップ → 会話作成 → 送受信 → 2 つ目の会話 → 切り替え → 再ログインで履歴が残る", async ({ page }) => {
    await signup(page);
    await expect(page.getByTestId("conv-item")).toHaveCount(0);

    // 会話 1
    await page.getByTestId("new-chat").click();
    await expect(page.getByTestId("conv-item")).toHaveCount(1);
    const reply1 = await send(page, "私の名前は花子です。趣味は登山です。ひとことで挨拶してください。");
    expect(reply1).toMatch(/花子|登山|こんにちは|はじめまして|よろしく/);
    // タイトルが最初のメッセージから自動生成される
    await expect(page.getByTestId("conv-item").first()).toContainText("私の名前は花子です");
    await expect(page.getByTestId("conv-title")).toContainText("私の名前は花子です");

    // 会話 2（別トピック）
    await page.getByTestId("new-chat").click();
    await expect(page.getByTestId("conv-item")).toHaveCount(2);
    await expect(page.getByTestId("msg-user")).toHaveCount(0);
    await send(page, "日本で一番高い山は？一文で答えてください。");
    await expect(page.getByTestId("conv-item").first()).toContainText("日本で一番高い山");

    // 会話 1 に切り替えると会話 1 のメッセージだけが表示される
    await page.getByTestId("conv-item").nth(1).click();
    await expect(page.getByTestId("conv-title")).toContainText("私の名前は花子です");
    await expect(page.getByTestId("msg-user")).toHaveCount(1);
    await expect(page.getByTestId("msg-user").first()).toContainText("花子");
    await expect(page.getByTestId("msg-assistant")).toHaveCount(1);

    // 会話 1 の続き（同一会話内の文脈が維持される）
    const reply2 = await send(page, "私の名前と趣味をもう一度言ってください。");
    expect(reply2).toMatch(/花子/);
    expect(reply2).toMatch(/登山/);

    // ログアウト → 再ログインで履歴が RDS から復元される
    await page.getByTestId("logout").click();
    await expect(page.getByTestId("auth-submit")).toBeVisible();
    await login(page);
    await expect(page.getByTestId("conv-item")).toHaveCount(2);
    await expect(page.getByTestId("conv-item").first()).toContainText("私の名前は花子です"); // 直近更新が先頭
    await expect(page.getByTestId("msg-user")).toHaveCount(2);
    await expect(page.getByTestId("msg-assistant")).toHaveCount(2);

    // 会話削除
    page.once("dialog", (d) => d.accept());
    await page.getByTestId("conv-item").nth(1).hover();
    await page.getByTestId("conv-item").nth(1).getByTestId("conv-delete").click();
    await expect(page.getByTestId("conv-item")).toHaveCount(1);
    await page.screenshot({ path: "test-results/final-state.png", fullPage: true });
  });
});
