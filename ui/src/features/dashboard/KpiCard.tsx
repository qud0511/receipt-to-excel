import { cn } from "@/lib/cn";

interface KpiCardProps {
  label: string;
  value: string;
  delta?: string;
  deltaTone?: "up" | "down" | "neutral";
}

const TONE: Record<NonNullable<KpiCardProps["deltaTone"]>, string> = {
  up: "text-success",
  down: "text-conf-low",
  neutral: "text-text-3",
};

export function KpiCard({ label, value, delta, deltaTone = "neutral" }: KpiCardProps) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-text-3">{label}</div>
      <div className="num text-[22px] font-bold tracking-tight">{value}</div>
      {delta ? <div className={cn("mt-1 text-[11px]", TONE[deltaTone])}>{delta}</div> : null}
    </div>
  );
}
