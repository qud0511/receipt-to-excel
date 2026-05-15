import { test, expect } from "@playwright/test";
import { mountMocks } from "./_mocks";

test("Result 화면: 4 다운로드 카드 + 통계 + 검수 화면 link", async ({ page }) => {
  await mountMocks(page);
  await page.goto("/result/7");

  await expect(page.getByRole("heading", { name: /지출결의서 완성/ })).toBeVisible();

  // 4 다운로드 link
  const links = page.getByRole("link", { name: /다운로드/ });
  await expect(links).toHaveCount(4);

  // 메일 button disabled
  const mail = page.getByRole("button", { name: /메일/ });
  await expect(mail).toBeDisabled();

  // 검수 화면으로 link
  await expect(page.getByRole("link", { name: /검수 화면/ })).toHaveAttribute("href", "/verify/7");
});
