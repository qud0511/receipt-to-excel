import { test, expect } from "@playwright/test";
import { mountMocks } from "./_mocks";

test("Templates 화면: sidebar list + grid preview", async ({ page }) => {
  await mountMocks(page);
  await page.goto("/templates");

  // sidebar 2 항목
  await expect(page.getByText("A사 파견용 양식")).toBeVisible();
  await expect(page.getByText("코스콤 외주 양식")).toBeVisible();
  await expect(page.getByText(/매핑 완료/).first()).toBeVisible();

  // grid 의 cell 값
  await expect(page.getByText("작성자")).toBeVisible();
  await expect(page.getByText("홍길동")).toBeVisible();

  // 양식만 받기 link
  await expect(page.getByRole("link", { name: /양식만 받기/ })).toBeVisible();
});

test("Templates '템플릿 추가' 클릭 시 modal 열림", async ({ page }) => {
  await mountMocks(page);
  await page.goto("/templates");
  await page.getByRole("button", { name: /템플릿 추가/ }).click();
  await expect(page.getByRole("heading", { name: /템플릿 업로드/ })).toBeVisible();
});
