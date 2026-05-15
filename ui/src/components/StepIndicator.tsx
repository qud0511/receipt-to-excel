import { cn } from "@/lib/cn";

export type StepKey = "upload" | "verify" | "result";

const STEPS: Array<{ key: StepKey; label: string }> = [
  { key: "upload", label: "업로드" },
  { key: "verify", label: "검수·수정" },
  { key: "result", label: "다운로드" },
];

interface StepIndicatorProps {
  current: StepKey;
  className?: string;
}

function stateOf(stepKey: StepKey, current: StepKey): "done" | "active" | "pending" {
  const order: StepKey[] = ["upload", "verify", "result"];
  const a = order.indexOf(stepKey);
  const b = order.indexOf(current);
  if (a < b) return "done";
  if (a === b) return "active";
  return "pending";
}

export function StepIndicator({ current, className }: StepIndicatorProps) {
  return (
    <ol
      aria-label="진행 단계"
      className={cn("flex items-center gap-1", className)}
    >
      {STEPS.map((s, idx) => {
        const state = stateOf(s.key, current);
        return (
          <li
            key={s.key}
            data-state={state}
            className={cn(
              "inline-flex h-8 items-center gap-2 rounded-md px-2.5 text-[12.5px] font-medium",
              state === "active" && "active bg-brand-soft text-brand",
              state === "done" && "done text-text-2",
              state === "pending" && "text-text-3",
            )}
          >
            <span
              className={cn(
                "grid h-4 w-4 place-items-center rounded-full font-mono text-[10px] font-bold",
                state === "active" && "bg-brand text-white",
                state === "done" && "bg-success text-white",
                state === "pending" && "bg-surface-2 text-text-3",
              )}
              aria-hidden
            >
              {idx + 1}
            </span>
            {s.label}
          </li>
        );
      })}
    </ol>
  );
}
