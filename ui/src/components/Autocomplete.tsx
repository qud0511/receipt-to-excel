import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/cn";

export interface AutocompleteOption {
  value: string;
  /** 최근 사용 표기 (last_used_at desc 상위) */
  recent?: boolean;
  /** 추가 메타 (예: usage_count) */
  meta?: string;
}

interface AutocompleteProps {
  value: string;
  placeholder: string;
  options: AutocompleteOption[];
  /** 사용자가 값을 확정했을 때 호출 (Enter / option click / blur 시 변경된 경우) */
  onCommit: (next: string) => void;
  disabled?: boolean;
  className?: string;
  /** input 변경 시 호출 (typing — 부모가 옵션을 동적으로 가져올 때) */
  onInputChange?: (q: string) => void;
}

/**
 * 셀 인라인 autocomplete. Combobox 패턴 (ARIA 1.2):
 * - input 의 onFocus / 클릭 시 dropdown 열림 (options 비어있어도 열림 — typing 으로 fetch trigger)
 * - 마우스 hover 또는 ↑↓ 로 highlight, Enter 로 확정, Escape 로 복원
 * - blur 시 dropdown close + value 변경 시 onCommit
 */
export function Autocomplete({
  value,
  placeholder,
  options,
  onCommit,
  disabled,
  className,
  onInputChange,
}: AutocompleteProps) {
  const [v, setV] = useState(value);
  const [open, setOpen] = useState(false);
  const [hl, setHl] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => setV(value), [value]);

  // 외부 클릭 시 dropdown close
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  function commit(next: string) {
    setOpen(false);
    setHl(-1);
    if (next !== value) onCommit(next);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setHl((i) => (options.length === 0 ? -1 : (i + 1) % options.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHl((i) => (options.length === 0 ? -1 : (i <= 0 ? options.length - 1 : i - 1)));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (hl >= 0 && options[hl]) {
        const picked = options[hl];
        setV(picked.value);
        commit(picked.value);
      } else {
        commit(v);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setV(value);
      setOpen(false);
      setHl(-1);
      inputRef.current?.blur();
    }
  }

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <input
        ref={inputRef}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        value={v}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => {
          setV(e.target.value);
          setOpen(true);
          onInputChange?.(e.target.value);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          // option 클릭 시점에 blur 가 먼저 발화하므로 약간 지연
          setTimeout(() => {
            setOpen(false);
            if (v !== value) onCommit(v);
          }, 120);
        }}
        onKeyDown={onKeyDown}
        className="h-9 w-full bg-transparent px-2.5 text-[13px] outline-none focus:bg-surface focus:shadow-[inset_0_0_0_2px_var(--brand)]"
      />
      {open && options.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 top-full z-30 mt-0.5 max-h-56 min-w-[220px] overflow-y-auto rounded-md border border-border-strong bg-surface p-1 shadow-lg"
        >
          {options.map((opt, i) => (
            <li
              key={opt.value}
              role="option"
              aria-selected={i === hl}
              onMouseDown={(e) => {
                // blur 보다 먼저 click 처리
                e.preventDefault();
                setV(opt.value);
                commit(opt.value);
              }}
              onMouseEnter={() => setHl(i)}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded px-2.5 py-1.5 text-[13px]",
                i === hl ? "bg-brand-soft text-brand" : "text-text hover:bg-surface-2",
              )}
            >
              {opt.recent && (
                <span className="rounded bg-brand px-1 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white">
                  최근
                </span>
              )}
              <span className="flex-1 truncate">{opt.value}</span>
              {opt.meta && <span className="text-[11px] text-text-3">{opt.meta}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
