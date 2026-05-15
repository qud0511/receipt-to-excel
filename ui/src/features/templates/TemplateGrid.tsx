import { useMemo, useState } from "react";
import type { GridResponse, GridSheetView } from "@/lib/api/types";
import { cn } from "@/lib/cn";

interface TemplateGridProps {
  grid: GridResponse;
}

function colLetter(n: number): string {
  let s = "";
  let x = n;
  while (x > 0) {
    const r = ((x - 1) % 26) + 1;
    s = String.fromCharCode(64 + r) + s;
    x = Math.floor((x - r) / 26);
  }
  return s;
}

function renderSheet(sheet: GridSheetView): JSX.Element {
  const grid: Record<number, Record<number, GridSheetView["cells"][number]>> = {};
  for (const c of sheet.cells) {
    if (!grid[c.row]) grid[c.row] = {};
    grid[c.row]![c.col] = c;
  }
  const rows = Math.max(sheet.max_row, 20);
  const cols = Math.max(sheet.max_col, 8);
  return (
    <table className="border-collapse text-[11px]">
      <thead>
        <tr>
          <th className="sticky left-0 top-0 z-30 h-[22px] w-8 border border-[#d4d7dd] bg-[#f3f4f6]"></th>
          {Array.from({ length: cols }).map((_, i) => (
            <th
              key={i}
              className="sticky top-0 z-20 min-w-[80px] border border-[#d4d7dd] bg-[#f3f4f6] px-1 text-[10.5px] font-semibold text-[#5a5f6b]"
            >
              {colLetter(i + 1)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>
            <th className="sticky left-0 z-10 h-[22px] w-8 border border-[#d4d7dd] bg-[#f3f4f6] text-[10.5px] font-semibold text-[#5a5f6b]">
              {r + 1}
            </th>
            {Array.from({ length: cols }).map((_, c) => {
              const cell = grid[r + 1]?.[c + 1];
              return (
                <td
                  key={c}
                  className={cn(
                    "border border-[#d4d7dd] bg-white px-1.5",
                    cell?.is_formula && "text-conf-low",
                  )}
                  title={cell?.is_formula ? String(cell.value ?? "") : undefined}
                >
                  {cell ? String(cell.value ?? "") : ""}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function TemplateGrid({ grid }: TemplateGridProps) {
  const sheetNames = useMemo(() => Object.keys(grid.sheets), [grid]);
  const [active, setActive] = useState<string | null>(sheetNames[0] ?? null);

  if (sheetNames.length === 0) {
    return (
      <div className="grid flex-1 place-items-center text-[13px] text-text-3">
        시트가 없습니다. 양식을 등록하세요.
      </div>
    );
  }

  const current = sheetNames.includes(active ?? "") ? active! : sheetNames[0]!;
  const sheet = grid.sheets[current];

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-surface">
      <div className="flex-1 overflow-auto bg-white">{sheet && renderSheet(sheet)}</div>
      <div className="flex h-7 items-center gap-0.5 border-t border-[#d4d7dd] bg-[#f3f4f6] px-2">
        {sheetNames.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => setActive(name)}
            className={cn(
              "h-[22px] rounded-t px-3.5 text-[11px]",
              name === current
                ? "border border-[#d4d7dd] border-b-white bg-white font-semibold text-brand"
                : "text-text-2 hover:bg-surface-2",
            )}
          >
            {name}
          </button>
        ))}
      </div>
    </div>
  );
}
