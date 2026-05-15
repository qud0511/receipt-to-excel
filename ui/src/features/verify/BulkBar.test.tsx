import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BulkBar } from "./BulkBar";

describe("BulkBar", () => {
  it("선택 0건이면 렌더 안 함", () => {
    const { container } = render(<BulkBar count={0} onApply={() => {}} onClear={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("선택 N건 + 일괄 적용 버튼", () => {
    render(<BulkBar count={3} onApply={() => {}} onClear={() => {}} />);
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /일괄 적용/ })).toBeInTheDocument();
  });

  it("일괄 적용 클릭 시 modal 열림 + apply 호출", async () => {
    const onApply = vi.fn();
    render(<BulkBar count={2} onApply={onApply} onClear={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /일괄 적용/ }));
    // modal 의 거래처 input
    const input = screen.getByPlaceholderText("거래처 입력 (선택)");
    await userEvent.type(input, "신용정보원");
    await userEvent.click(screen.getByRole("button", { name: "적용" }));
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ vendor: "신용정보원" }));
  });

  it("선택 해제 버튼", async () => {
    const onClear = vi.fn();
    render(<BulkBar count={5} onApply={() => {}} onClear={onClear} />);
    await userEvent.click(screen.getByRole("button", { name: /선택 해제/ }));
    expect(onClear).toHaveBeenCalledOnce();
  });
});
