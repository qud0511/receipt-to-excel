import { cn } from "@/lib/cn";

export type SessionStatus = "parsing" | "awaiting_user" | "submitted" | "failed" | "generated";

const SESSION_STATUS_LABEL: Record<SessionStatus, string> = {
  parsing: "작성중",
  awaiting_user: "미입력",
  generated: "작성중",
  submitted: "제출완료",
  failed: "실패",
};

const SESSION_STATUS_TONE: Record<SessionStatus, string> = {
  parsing: "bg-brand-soft text-brand",
  awaiting_user: "bg-surface-2 text-text-2",
  generated: "bg-brand-soft text-brand",
  submitted: "bg-success-soft text-success",
  failed: "bg-conf-low/10 text-conf-low",
};

interface StatusPillProps {
  /** Transaction-level — tagged true 면 입력완료, false 면 미입력 */
  tagged?: boolean;
  /** Session-level — 4 enum 중 하나 */
  sessionStatus?: SessionStatus;
  className?: string;
}

export function StatusPill({ tagged, sessionStatus, className }: StatusPillProps) {
  if (sessionStatus) {
    const label = SESSION_STATUS_LABEL[sessionStatus];
    const tone = SESSION_STATUS_TONE[sessionStatus];
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold",
          tone,
          className,
        )}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
        {label}
      </span>
    );
  }
  const isTagged = !!tagged;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold",
        isTagged ? "bg-success-soft text-success" : "bg-surface-2 text-text-3",
        className,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {isTagged ? "입력완료" : "미입력"}
    </span>
  );
}
