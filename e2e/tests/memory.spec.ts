import { test, expect } from "@playwright/test";

// 長期記憶が有効なとき（/healthz の memory=true）だけ動くテスト。
// 事前条件: MEMORY_USER_EMAIL / MEMORY_USER_PASSWORD のユーザーが過去の会話で
// 「名前は太郎」「好きな飲み物はコーヒー」と述べており、その履歴がバックフィル済みであること。
const email = process.env.MEMORY_USER_EMAIL || "";
const password = process.env.MEMORY_USER_PASSWORD || "Passw0rd123";

test("新しい会話で過去会話の長期記憶が参照される", async ({ page, request }) => {
  const health = await (await request.get("/api/healthz")).json();
  test.skip(!health.memory, "memory integration is disabled");
  test.skip(!email, "MEMORY_USER_EMAIL is not set");

  await page.goto("/");
  await page.getByTestId("email").fill(email);
  await page.getByTestId("password").fill(password);
  await page.getByTestId("auth-submit").click();
  await expect(page.getByTestId("me")).toHaveText(email);
  await expect(page.locator("#memory-badge")).toBeVisible();

  // まったく新しい会話（この会話には名前も飲み物も書いていない）
  await page.getByTestId("new-chat").click();
  await expect(page.getByTestId("msg-user")).toHaveCount(0);
  await page.getByTestId("input").fill("私の好きな飲み物を覚えていますか？一文で答えてください。");
  await page.getByTestId("send").click();

  await expect(page.getByTestId("memory-note")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("memory-note")).toContainText("長期記憶を");
  await expect(page.getByTestId("assistant-final")).toHaveCount(1, { timeout: 90_000 });
  const reply = await page.getByTestId("assistant-final").innerText();
  // 取得はセマンティック検索の上位 K 件なので、レコードが増えると名前の事実は外れることがある。
  // 記憶パイプラインの疎通確認としては、質問に強く関係する「コーヒー」が返ることだけを断定する。
  expect(reply).toMatch(/コーヒー/);
  await page.screenshot({ path: "test-results/memory-recall.png" });
});
