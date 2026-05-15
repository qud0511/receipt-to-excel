import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { TopNav } from "./TopNav";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <TopNav userName="홍길동" />
    </MemoryRouter>,
  );
}

describe("TopNav", () => {
  it("브랜드 로고 + 이름을 표시", () => {
    renderAt("/");
    expect(screen.getByText("CreditXLSX")).toBeInTheDocument();
    expect(screen.getByText("CX")).toBeInTheDocument();
  });

  it("/ 에서는 탭 nav (Dashboard / Templates)", () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: /대시보드/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /템플릿/ })).toBeInTheDocument();
  });

  it("/upload 에서는 step indicator 표시", () => {
    renderAt("/upload");
    expect(screen.getByText("업로드")).toBeInTheDocument();
    expect(screen.getByText(/검수/)).toBeInTheDocument();
  });

  it("/verify/:id 에서도 step indicator", () => {
    renderAt("/verify/42");
    expect(screen.getByText(/검수/).closest("li")?.className).toMatch(/active/);
  });

  it("사용자 이름과 avatar 표시", () => {
    renderAt("/");
    expect(screen.getByText("홍길동")).toBeInTheDocument();
  });
});
