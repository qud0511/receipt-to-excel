import { test, expect } from "@playwright/test";
import { mountMocks } from "./_mocks";

test("Dashboard 진입 시 인사 + KPI 4 + 최근 결의서 렌더", async ({ page }) => {
  await mountMocks(page);
  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1 })).toContainText("홍길동");
  await expect(page.getByText("1,230,000원").first()).toBeVisible();
  await expect(page.getByText(/이번 달 총 지출/)).toBeVisible();
  await expect(page.getByText(/결제 건수/)).toBeVisible();
  await expect(page.getByText(/완료된 결의서/)).toBeVisible();
  await expect(page.getByText(/절약된 시간/)).toBeVisible();
  await expect(page.getByText("A사 파견용 양식")).toBeVisible();
});

test("Dashboard '지출결의서 작성' 클릭 시 /upload 로 이동", async ({ page }) => {
  await mountMocks(page);
  await page.goto("/");
  await page.getByRole("link", { name: /지출결의서 작성/ }).click();
  await expect(page).toHaveURL(/\/upload$/);
});
