import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Autocomplete } from "./Autocomplete";

describe("Autocomplete", () => {
  const options = [
    { value: "신용정보원", recent: true },
    { value: "한국은행" },
    { value: "금융결제원" },
  ];

  it("초기 value 를 input 에 표시", () => {
    render(<Autocomplete value="신용정보원" placeholder="거래처" options={[]} onCommit={() => {}} />);
    expect(screen.getByDisplayValue("신용정보원")).toBeInTheDocument();
  });

  it("focus 시 dropdown 표시 + options 렌더", async () => {
    render(<Autocomplete value="" placeholder="거래처" options={options} onCommit={() => {}} />);
    const input = screen.getByPlaceholderText("거래처");
    await userEvent.click(input);
    expect(screen.getByText("신용정보원")).toBeInTheDocument();
    expect(screen.getByText("한국은행")).toBeInTheDocument();
    // recent 뱃지
    expect(screen.getByText("최근")).toBeInTheDocument();
  });

  it("option 클릭 시 onCommit 호출 + dropdown close", async () => {
    const fn = vi.fn();
    render(<Autocomplete value="" placeholder="거래처" options={options} onCommit={fn} />);
    const input = screen.getByPlaceholderText("거래처");
    await userEvent.click(input);
    await userEvent.click(screen.getByText("한국은행"));
    expect(fn).toHaveBeenCalledWith("한국은행");
  });

  it("Enter 키로 현재 typing 값 commit", async () => {
    const fn = vi.fn();
    render(<Autocomplete value="" placeholder="거래처" options={[]} onCommit={fn} />);
    const input = screen.getByPlaceholderText("거래처");
    await userEvent.type(input, "새 거래처");
    await userEvent.keyboard("{Enter}");
    expect(fn).toHaveBeenCalledWith("새 거래처");
  });

  it("Escape 키로 초기값 복원 + dropdown close", async () => {
    const fn = vi.fn();
    render(<Autocomplete value="원본" placeholder="거래처" options={options} onCommit={fn} />);
    const input = screen.getByPlaceholderText("거래처") as HTMLInputElement;
    await userEvent.click(input);
    await userEvent.clear(input);
    await userEvent.type(input, "변경");
    await userEvent.keyboard("{Escape}");
    expect(input.value).toBe("원본");
    expect(fn).not.toHaveBeenCalled();
  });

  it("disabled 시 input 비활성", () => {
    render(<Autocomplete value="" placeholder="프로젝트" options={[]} onCommit={() => {}} disabled />);
    expect(screen.getByPlaceholderText("프로젝트")).toBeDisabled();
  });
});
