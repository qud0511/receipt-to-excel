import type { TransactionView } from "@/lib/api/types";
import { Icon } from "@/components/Icon";
import { receiptUrl } from "@/lib/api/sessions";
import { formatDateDot, formatKRW } from "@/lib/format";

interface ReceiptPaneProps {
  sessionId: number;
  active: TransactionView | null;
  index: number;
  total: number;
  onPrev?: () => void;
  onNext?: () => void;
}

export function ReceiptPane({ sessionId, active, index, total, onPrev, onNext }: ReceiptPaneProps) {
  return (
    <aside className="flex h-full w-[380px] shrink-0 flex-col border-r border-border bg-[#20232a] text-white/90">
      <div className="flex items-center justify-between border-b border-white/10 bg-white/5 px-4 py-3">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-white/60">영수증</div>
        <div className="flex gap-1.5">
          <button
            aria-label="이전 영수증"
            disabled={!onPrev || index <= 0}
            onClick={() => onPrev?.()}
            className="grid h-7 w-7 place-items-center rounded-md border border-white/10 bg-white/10 text-white/85 hover:bg-white/20 disabled:opacity-30"
          >
            <Icon name="Chevron" className="rotate-90" />
          </button>
          <button
            aria-label="다음 영수증"
            disabled={!onNext || index >= total - 1}
            onClick={() => onNext?.()}
            className="grid h-7 w-7 place-items-center rounded-md border border-white/10 bg-white/10 text-white/85 hover:bg-white/20 disabled:opacity-30"
          >
            <Icon name="Chevron" className="-rotate-90" />
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col items-center gap-3 overflow-y-auto p-5">
        {active ? (
          <>
            <article className="w-full max-w-[320px] rounded-md bg-[#fefefe] p-5 font-mono text-[12px] leading-relaxed text-[#2a2a2a] shadow-lg">
              <div className="mb-2 border-b border-dashed border-[#aaa] pb-2 text-center text-[14px] font-bold">
                {active.가맹점명}
              </div>
              <div className="flex justify-between">
                <span>일시</span>
                <span className="font-mono">
                  {formatDateDot(active.거래일)} {active.거래시각 ?? ""}
                </span>
              </div>
              {active.업종 ? (
                <div className="flex justify-between">
                  <span>업종</span>
                  <span>{active.업종}</span>
                </div>
              ) : null}
              <div className="my-2 border-t border-dashed border-[#aaa]" />
              <div className="flex justify-between">
                <span className="font-bold">합계</span>
                <span className="num font-bold">{formatKRW(active.금액)}</span>
              </div>
              <div className="mt-2 border-t border-dashed border-[#aaa] pt-2 text-center text-[10px] text-[#888]">
                {active.카드사.toUpperCase()} · {active.카드번호_마스킹 ?? ""}
              </div>
            </article>

            <img
              src={receiptUrl(sessionId, active.id)}
              alt={`영수증 ${active.가맹점명}`}
              loading="lazy"
              className="max-h-72 w-full max-w-[320px] rounded-md object-contain"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          </>
        ) : (
          <div className="m-auto text-center text-[13px] text-white/60">선택된 거래가 없습니다.</div>
        )}
      </div>

      {total > 0 && (
        <div className="flex items-center justify-between border-t border-white/10 px-4 py-2.5 text-[12px] text-white/60">
          <span className="num">
            {index + 1} / {total}
          </span>
          <span>{active?.parser_used ?? ""}</span>
        </div>
      )}
    </aside>
  );
}
