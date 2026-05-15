import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TemplateGrid } from "./TemplateGrid";
import type { GridResponse } from "@/lib/api/types";

const grid: GridResponse = {
  sheets: {
    지출결의서: {
      sheet_name: "지출결의서",
      max_row: 5,
      max_col: 3,
      cells: [
        { row: 1, col: 1, value: "지출결의서", is_formula: false },
        { row: 3, col: 1, value: "작성자", is_formula: false },
        { row: 3, col: 2, value: "홍길동", is_formula: false },
        { row: 5, col: 3, value: "=SUM(C7:C18)", is_formula: true },
      ],
    },
    증빙요약: {
      sheet_name: "증빙요약",
      max_row: 2,
      max_col: 2,
      cells: [],
    },
  },
};

describe("TemplateGrid", () => {
  it("기본 시트 cells 렌더", () => {
    render(<TemplateGrid grid={grid} />);
    // "지출결의서" 는 시트 탭 + cell (1,1) 둘 다 매칭
    expect(screen.getAllByText("지출결의서").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("작성자")).toBeInTheDocument();
    expect(screen.getByText("홍길동")).toBeInTheDocument();
  });

  it("Sheet tab 다중 시트 표시", () => {
    render(<TemplateGrid grid={grid} />);
    // 시트 탭이 시트명을 보여줌
    expect(screen.getAllByText("지출결의서").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /증빙요약/ })).toBeInTheDocument();
  });

  it("빈 grid 시 안내", () => {
    render(<TemplateGrid grid={{ sheets: {} }} />);
    expect(screen.getByText(/없습니다/)).toBeInTheDocument();
  });
});
