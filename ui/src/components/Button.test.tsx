import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";

describe("Button", () => {
  it("primary variant 가 디폴트로 적용된다", () => {
    render(<Button>저장</Button>);
    const btn = screen.getByRole("button", { name: "저장" });
    expect(btn.className).toMatch(/bg-brand/);
  });

  it("ghost variant", () => {
    render(<Button variant="ghost">취소</Button>);
    expect(screen.getByRole("button").className).not.toMatch(/bg-brand/);
  });

  it("onClick 핸들러 호출", async () => {
    const fn = vi.fn();
    render(<Button onClick={fn}>클릭</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(fn).toHaveBeenCalledOnce();
  });

  it("disabled 시 클릭 무시 + aria-disabled", async () => {
    const fn = vi.fn();
    render(
      <Button onClick={fn} disabled>
        잠금
      </Button>,
    );
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
    await userEvent.click(btn);
    expect(fn).not.toHaveBeenCalled();
  });
});
