import type { ArtifactKind } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/Icon";

interface DownloadCardProps {
  kind: ArtifactKind | "mail";
  name: string;
  desc: string;
  href?: string;
  primary?: boolean;
  disabled?: boolean;
  disabledLabel?: string;
}

const KIND_TONE: Record<ArtifactKind | "mail", string> = {
  xlsx: "bg-success",
  layout_pdf: "bg-conf-low",
  merged_pdf: "bg-conf-low/80",
  zip: "bg-brand",
  mail: "bg-text-3",
};

const KIND_BADGE: Record<ArtifactKind | "mail", string> = {
  xlsx: "XLSX",
  layout_pdf: "PDF",
  merged_pdf: "PDF",
  zip: "ZIP",
  mail: "✉",
};

export function DownloadCard({ kind, name, desc, href, primary, disabled, disabledLabel }: DownloadCardProps) {
  return (
    <div className="flex items-center gap-3.5 rounded-xl border border-border bg-surface p-4">
      <div
        className={cn(
          "grid h-11 w-11 shrink-0 place-items-center rounded-xl font-mono text-[14px] font-bold text-white",
          KIND_TONE[kind],
        )}
      >
        {KIND_BADGE[kind]}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[14px] font-semibold">{name}</div>
        <div className="text-[12px] text-text-3">{desc}</div>
      </div>
      {disabled ? (
        <button
          type="button"
          disabled
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-surface-2 px-4 text-[13px] font-semibold text-text-3"
        >
          {disabledLabel ?? "Phase 7+ 예정"}
        </button>
      ) : (
        <a
          href={href ?? "#"}
          download
          className={cn(
            "inline-flex h-9 items-center gap-1.5 rounded-lg px-4 text-[13px] font-semibold text-white",
            primary ? "bg-brand hover:bg-brand-2" : "bg-text hover:bg-brand",
          )}
        >
          <Icon name="Download" /> 다운로드
        </a>
      )}
    </div>
  );
}
