import { cn } from "@/lib/cn";
import { Icon } from "@/components/Icon";
import type { TemplateSummary } from "@/lib/api/types";

interface TemplateListProps {
  items: TemplateSummary[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onUpload: () => void;
}

export function TemplateList({ items, activeId, onSelect, onUpload }: TemplateListProps) {
  return (
    <aside className="flex h-full w-[280px] shrink-0 flex-col border-r border-border bg-surface">
      <header className="flex items-center justify-between border-b border-border px-4 py-3.5">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-text-3">템플릿</div>
        <span className="num rounded bg-bg px-1.5 py-0.5 text-[10px] font-bold text-text-3">
          {items.length}
        </span>
      </header>

      <div className="flex-1 space-y-0.5 overflow-y-auto p-1.5">
        {items.map((t) => {
          const active = t.id === activeId;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onSelect(t.id)}
              className={cn(
                "flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left transition-colors",
                active ? "bg-brand-soft text-brand" : "hover:bg-surface-2",
              )}
            >
              <span className="num grid h-8 w-8 shrink-0 place-items-center rounded-md bg-success text-[9px] font-bold tracking-wider text-white">
                XLSX
              </span>
              <span className="min-w-0 flex-1">
                <span className={cn("block truncate text-[13px] font-semibold", active ? "text-brand" : "text-text")}>
                  {t.name}
                </span>
                <span
                  className={cn(
                    "text-[11px]",
                    t.mapping_status === "mapped" ? "text-success" : "text-conf-medium",
                  )}
                >
                  {t.mapping_status === "mapped" ? "매핑 완료" : "매핑 필요"}
                  {t.is_default ? " · 기본" : ""}
                </span>
              </span>
            </button>
          );
        })}

        <button
          type="button"
          onClick={onUpload}
          className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-border-strong px-3 py-3 text-[12.5px] font-medium text-text-3 hover:border-brand hover:bg-brand-soft hover:text-brand"
        >
          <Icon name="Plus" /> 템플릿 추가
        </button>
      </div>
    </aside>
  );
}
