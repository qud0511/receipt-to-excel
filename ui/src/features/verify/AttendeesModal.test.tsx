import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AttendeesModal } from "./AttendeesModal";
import type { TeamGroupView } from "@/lib/api/types";

const groups: TeamGroupView[] = [
  {
    id: 1,
    name: "개발1팀",
    members: [
      { id: 1, name: "홍길동" },
      { id: 2, name: "김지호" },
      { id: 3, name: "박서연" },
    ],
  },
  {
    id: 2,
    name: "기획팀",
    members: [
      { id: 5, name: "오세훈" },
      { id: 6, name: "윤아름" },
    ],
  },
];

describe("AttendeesModal", () => {
  it("팀 그룹 chip + 멤버 grid 렌더", () => {
    render(
      <AttendeesModal open initial={[]} groups={groups} onClose={() => {}} onSave={() => {}} />,
    );
    expect(screen.getByRole("button", { name: /개발1팀/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /기획팀/ })).toBeInTheDocument();
    expect(screen.getByText("홍길동")).toBeInTheDocument();
    expect(screen.getByText("박서연")).toBeInTheDocument();
  });

  it("초기 attendees 가 selected 로 표시", () => {
    render(
      <AttendeesModal
        open
        initial={["홍길동"]}
        groups={groups}
        onClose={() => {}}
        onSave={() => {}}
      />,
    );
    const tile = screen.getByText("홍길동").closest("button");
    expect(tile?.className).toMatch(/brand|selected/);
  });

  it("팀 chip 클릭 시 팀 멤버 일괄 토글", async () => {
    render(
      <AttendeesModal open initial={[]} groups={groups} onClose={() => {}} onSave={() => {}} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /개발1팀/ }));
    expect(screen.getByText("홍길동").closest("button")?.className).toMatch(/brand|selected/);
    expect(screen.getByText("김지호").closest("button")?.className).toMatch(/brand|selected/);
  });

  it("자유 텍스트 입력 후 추가 → 멤버에 포함", async () => {
    const onSave = vi.fn();
    render(
      <AttendeesModal open initial={[]} groups={groups} onClose={() => {}} onSave={onSave} />,
    );
    const input = screen.getByPlaceholderText(/이름 입력/);
    await userEvent.type(input, "외부인");
    await userEvent.click(screen.getByRole("button", { name: /추가/ }));
    await userEvent.click(screen.getByRole("button", { name: /저장/ }));
    expect(onSave).toHaveBeenCalledWith(["외부인"]);
  });

  it("저장 시 선택된 멤버 배열 전달", async () => {
    const onSave = vi.fn();
    render(
      <AttendeesModal open initial={[]} groups={groups} onClose={() => {}} onSave={onSave} />,
    );
    await userEvent.click(screen.getByText("홍길동"));
    await userEvent.click(screen.getByText("박서연"));
    await userEvent.click(screen.getByRole("button", { name: /저장/ }));
    expect(onSave).toHaveBeenCalledWith(["홍길동", "박서연"]);
  });

  it("open=false 면 렌더 안 함", () => {
    const { container } = render(
      <AttendeesModal open={false} initial={[]} groups={groups} onClose={() => {}} onSave={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
