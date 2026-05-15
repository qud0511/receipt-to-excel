import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MappingChips } from "./MappingChips";
import type { SheetConfigView } from "@/lib/api/types";

const sheet: SheetConfigView = {
  sheet_name: "지출결의서",
  sheet_kind: null,
  mode: "field",
  analyzable: true,
  date_col: "A",
  merchant_col: "B",
  project_col: "C",
  total_col: "F",
  note_col: null,
  category_cols: {},
  formula_cols: ["F"],
  data_start_row: 7,
  data_end_row: 18,
  sum_row: 19,
  header_row: 6,
};

describe("MappingChips", () => {
  it("매핑된 컬럼 chip 표시", () => {
    render(<MappingChips sheet={sheet} />);
    expect(screen.getByText(/거래일/)).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
  });

  it("매핑 안 된 컬럼은 'unmapped' 스타일", () => {
    render(<MappingChips sheet={{ ...sheet, note_col: null }} />);
    const note = screen.getByText(/비고/).closest("span");
    expect(note?.className).toMatch(/unmapped|dashed|opacity/);
  });
});
