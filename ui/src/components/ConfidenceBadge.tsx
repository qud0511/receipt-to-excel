import { cn } from "@/lib/cn";

export type Confidence = "high" | "medium" | "low" | "none";

const CONF_ALIAS: Record<Confidence, string> = {
  high: "신뢰도 높음",
  medium: "신뢰도 중간",
  low: "신뢰도 낮음",
  none: "신뢰도 미상",
};

const CONF_CLASS: Record<Confidence, string> = {
  high: "bg-conf-high/15 text-conf-high",
  medium: "bg-conf-medium/15 text-conf-medium",
  low: "bg-conf-low/15 text-conf-low",
  none: "bg-conf-none/10 text-conf-none",
};

interface ConfidenceBadgeProps {
  level: Confidence;
  className?: string;
  /** 컴팩트 점만 표시 (그리드 셀 용) */
  dotOnly?: boolean;
}

export function ConfidenceBadge({ level, className, dotOnly }: ConfidenceBadgeProps) {
  if (dotOnly) {
    return (
      <span
        role="img"
        aria-label={CONF_ALIAS[level]}
        className={cn(
          "inline-block h-2 w-2 shrink-0 rounded-full",
          CONF_CLASS[level].split(" ")[0] ?? "",
          className,
        )}
      />
    );
  }
  return (
    <span
      role="img"
      aria-label={CONF_ALIAS[level]}
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider",
        CONF_CLASS[level],
        className,
      )}
    >
      {level}
    </span>
  );
}
