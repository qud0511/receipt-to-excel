import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { cn } from "@/lib/cn";
import type { TeamGroupView } from "@/lib/api/types";

interface AttendeesModalProps {
  open: boolean;
  initial: string[];
  groups: TeamGroupView[];
  onClose: () => void;
  onSave: (next: string[]) => void;
}

export function AttendeesModal({ open, initial, groups, onClose, onSave }: AttendeesModalProps) {
  const [selected, setSelected] = useState<string[]>(initial);
  const [freeText, setFreeText] = useState("");

  useEffect(() => {
    if (open) setSelected(initial);
  }, [open, initial]);

  const allMembers = useMemo(
    () => Array.from(new Set(groups.flatMap((g) => g.members.map((m) => m.name)))),
    [groups],
  );

  if (!open) return null;

  function toggle(name: string) {
    setSelected((prev) => (prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]));
  }

  function toggleGroup(g: TeamGroupView) {
    const names = g.members.map((m) => m.name);
    const allIn = names.every((n) => selected.includes(n));
    setSelected((prev) =>
      allIn ? prev.filter((n) => !names.includes(n)) : Array.from(new Set([...prev, ...names])),
    );
  }

  function addFree() {
    const v = freeText.trim();
    if (!v) return;
    if (!selected.includes(v)) setSelected((prev) => [...prev, v]);
    setFreeText("");
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        className="w-[560px] max-w-[90%] overflow-hidden rounded-2xl bg-surface shadow-lg"
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div className="text-[15px] font-bold">참석자 선택</div>
          <button onClick={onClose} aria-label="닫기">
            <Icon name="Close" />
          </button>
        </header>

        <div className="space-y-3.5 p-5">
          <div>
            <div className="mb-1.5 text-[11.5px] font-semibold text-text-3">팀 일괄 선택</div>
            <div className="flex flex-wrap gap-1.5">
              {groups.map((g) => {
                const names = g.members.map((m) => m.name);
                const allIn = names.length > 0 && names.every((n) => selected.includes(n));
                return (
                  <button
                    key={g.id}
                    type="button"
                    onClick={() => toggleGroup(g)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12px] font-semibold",
                      allIn
                        ? "border-brand bg-brand text-white"
                        : "border-brand-border bg-brand-soft text-brand hover:bg-brand hover:text-white",
                    )}
                  >
                    {g.name}
                    <span className="num rounded bg-white/40 px-1 text-[10px]">{g.members.length}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="mb-1.5 text-[11.5px] font-semibold text-text-3">멤버 (다중 선택)</div>
            <div className="grid max-h-60 grid-cols-3 gap-1.5 overflow-y-auto">
              {allMembers.map((name) => {
                const on = selected.includes(name);
                return (
                  <button
                    key={name}
                    type="button"
                    onClick={() => toggle(name)}
                    aria-pressed={on}
                    className={cn(
                      "flex items-center gap-2 rounded border px-2.5 py-2 text-[12.5px]",
                      on
                        ? "selected border-brand bg-brand-soft font-semibold text-brand"
                        : "border-border bg-surface text-text hover:border-brand-border",
                    )}
                  >
                    <span
                      className={cn(
                        "grid h-5.5 w-5.5 place-items-center rounded-full text-[10px] font-bold",
                        on ? "bg-brand text-white" : "bg-bg text-text-2",
                      )}
                    >
                      {name.slice(0, 1)}
                    </span>
                    {name}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="mb-1.5 text-[11.5px] font-semibold text-text-3">직접 추가</div>
            <div className="flex gap-2">
              <input
                value={freeText}
                onChange={(e) => setFreeText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addFree();
                  }
                }}
                placeholder="이름 입력 (외부 참석자)"
                className="h-9 flex-1 rounded-md border border-border bg-bg px-2.5"
              />
              <Button variant="soft" onClick={addFree} disabled={!freeText.trim()}>
                <Icon name="Plus" /> 추가
              </Button>
            </div>
          </div>

          {selected.length > 0 && (
            <div className="rounded-md bg-surface-2 p-2.5 text-[12px]">
              <strong>선택: {selected.length}명</strong> · {selected.join(", ")}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-border bg-surface-2 px-5 py-3">
          <Button variant="ghost" onClick={onClose}>
            취소
          </Button>
          <Button onClick={() => onSave(selected)}>저장</Button>
        </div>
      </div>
    </div>
  );
}
