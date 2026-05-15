import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DropZone } from "./DropZone";

function file(name: string, type = "image/jpeg", size = 1024) {
  const f = new File(["x"], name, { type });
  Object.defineProperty(f, "size", { value: size });
  return f;
}

describe("DropZone", () => {
  it("안내 문구 표시 + accept 형식 설명", () => {
    render(<DropZone onFiles={() => {}} />);
    expect(screen.getByText(/드래그/)).toBeInTheDocument();
    expect(screen.getByText(/PDF/)).toBeInTheDocument();
  });

  it("드롭 시 onFiles 호출", () => {
    const fn = vi.fn();
    render(<DropZone onFiles={fn} />);
    const drop = screen.getByLabelText(/업로드/);
    const f1 = file("a.pdf", "application/pdf");
    const f2 = file("b.jpg");
    const dataTransfer = {
      files: [f1, f2],
      items: [],
      types: ["Files"],
    };
    drop.dispatchEvent(
      Object.assign(new Event("drop", { bubbles: true, cancelable: true }), { dataTransfer }),
    );
    expect(fn).toHaveBeenCalledWith([f1, f2]);
  });

  it("input 클릭 시 파일 선택 핸들러 동작", async () => {
    const fn = vi.fn();
    render(<DropZone onFiles={fn} />);
    const input = screen.getByTestId("dropzone-input") as HTMLInputElement;
    const f1 = file("c.pdf", "application/pdf");
    await userEvent.upload(input, f1);
    expect(fn).toHaveBeenCalledWith([f1]);
  });
});
