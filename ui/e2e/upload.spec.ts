import { test, expect } from "@playwright/test";
import { mountMocks } from "./_mocks";

test("Upload 화면: 헤더 + DropZone + 양식 selector 렌더", async ({ page }) => {
  await mountMocks(page);
  await page.goto("/upload");

  await expect(page.getByRole("heading", { name: /일괄 업로드/ })).toBeVisible();
  await expect(page.getByText(/파일을 여기로 드래그/)).toBeVisible();
  // 템플릿 selector 가 로드되면 A사 파견용 양식 option 노출
  await expect(page.locator("select").first()).toContainText("A사 파견용 양식");
});

test("Upload TopNav step indicator: ① 업로드 active", async ({ page }) => {
  await mountMocks(page);
  await page.goto("/upload");
  const step1 = page.locator("li").filter({ hasText: "업로드" }).first();
  await expect(step1).toHaveAttribute("data-state", "active");
});
