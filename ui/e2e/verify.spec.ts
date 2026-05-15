import { test, expect } from "@playwright/test";
import { mountMocks } from "./_mocks";

test("Verify 화면: split view + 그리드 + filter chips + summary", async ({ page }) => {
  await mountMocks(page);
  await page.goto("/verify/1");

  // 그리드의 가맹점 표시
  await expect(page.getByText("본가설렁탕 강남점")).toBeVisible();
  await expect(page.getByText("광화문 미진")).toBeVisible();

  // FilterChips
  await expect(page.getByRole("button", { name: /전체/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /필수 누락/ })).toBeVisible();

  // SummaryBar 합계
  await expect(page.getByText(/234,000원/)).toBeVisible();

  // ReceiptPane 좌 패널의 활성 row 가맹점
  await expect(page.getByText("본가설렁탕 강남점")).toBeVisible();
});

test("Verify '완료하고 다운로드' → /result/{id}", async ({ page }) => {
  await mountMocks(page);
  await page.goto("/verify/1");
  await page.getByRole("link", { name: /다운로드/ }).first().click();
  await expect(page).toHaveURL(/\/result\/1$/);
});
