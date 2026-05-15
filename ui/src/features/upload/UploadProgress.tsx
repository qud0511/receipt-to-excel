import type { SSEMessage, SSEStage } from "@/lib/api/types";
import { cn } from "@/lib/cn";

const STAGE_LABEL: Record<SSEStage, string> = {
  uploaded: "업로드 수신",
  ocr: "OCR 진행 중",
  llm: "AI 추출 중",
  rule_based: "규칙 기반 파서 실행",
  resolved: "추출 완료",
  vendor_failed: "거래처 추정 실패",
  done: "완료",
  error: "오류",
};

interface UploadProgressProps {
  events: SSEMessage[];
}

export function UploadProgress({ events }: UploadProgressProps) {
  const last = events.at(-1);
  if (!last) return null;

  const pct =
    last.stage === "done"
      ? 100
      : last.total > 0
        ? Math.min(100, Math.round((last.file_idx / last.total) * 100))
        : 0;

  const isError = last.stage === "error";

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="mb-2 flex items-center justify-between text-[13px]">
        <span className={cn("font-semibold", isError ? "text-conf-low" : "text-text")}>
          {STAGE_LABEL[last.stage]}
          {last.filename ? <span className="ml-2 text-text-3">· {last.filename}</span> : null}
        </span>
        <span className="num font-bold text-brand">{pct}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-bg">
        <div
          className={cn("h-full transition-all", isError ? "bg-conf-low" : "bg-brand")}
          style={{ width: `${pct}%` }}
        />
      </div>
      <ul className="mt-3 max-h-32 overflow-y-auto text-[12px] text-text-3">
        {events.slice(-6).map((e, i) => (
          <li key={`${e.stage}-${e.file_idx}-${i}`}>
            <span className="num text-text-4">[{String(e.file_idx).padStart(2, "0")}/{e.total}]</span>{" "}
            {STAGE_LABEL[e.stage]} {e.filename ? `· ${e.filename}` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
