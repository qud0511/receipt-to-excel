import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TemplateList } from "./TemplateList";
import type { TemplateSummary } from "@/lib/api/types";

const items: TemplateSummary[] = [
  {
    id: 1,
    name: "A사 파견용 양식",
    is_default: true,
    mapping_status: "mapped",
    created_at: "2026-05-01T00:00:00",
    updated_at: "2026-05-12T00:00:00",
  },
  {
    id: 2,
    name: "코스콤 외주 양식",
    is_default: false,
    mapping_status: "needs_mapping",
    created_at: "2026-04-15T00:00:00",
    updated_at: "2026-04-15T00:00:00",
  },
];

describe("TemplateList", () => {
  it("각 항목 name + mapping_status 표시", () => {
    render(<TemplateList items={items} activeId={1} onSelect={() => {}} onUpload={() => {}} />);
    expect(screen.getByText("A사 파견용 양식")).toBeInTheDocument();
    expect(screen.getByText("코스콤 외주 양식")).toBeInTheDocument();
    expect(screen.getByText(/매핑 완료/)).toBeInTheDocument();
    expect(screen.getByText(/매핑 필요/)).toBeInTheDocument();
  });

  it("active 항목 시각 강조", () => {
    render(<TemplateList items={items} activeId={1} onSelect={() => {}} onUpload={() => {}} />);
    const active = screen.getByText("A사 파견용 양식").closest("button");
    expect(active?.className).toMatch(/brand/);
  });

  it("항목 클릭 시 onSelect 호출", async () => {
    const fn = vi.fn();
    render(<TemplateList items={items} activeId={1} onSelect={fn} onUpload={() => {}} />);
    await userEvent.click(screen.getByText("코스콤 외주 양식"));
    expect(fn).toHaveBeenCalledWith(2);
  });

  it("'템플릿 추가' 버튼 → onUpload", async () => {
    const fn = vi.fn();
    render(<TemplateList items={items} activeId={1} onSelect={() => {}} onUpload={fn} />);
    await userEvent.click(screen.getByRole("button", { name: /템플릿 추가/ }));
    expect(fn).toHaveBeenCalledOnce();
  });
});
