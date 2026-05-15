import type { SVGProps } from "react";
import { cn } from "@/lib/cn";

type IconName =
  | "Search"
  | "Filter"
  | "Calendar"
  | "Download"
  | "Plus"
  | "Receipt"
  | "Close"
  | "Chevron"
  | "Check"
  | "Sparkle"
  | "Upload";

interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  alias?: string;
  size?: number;
}

const PATHS: Record<IconName, JSX.Element> = {
  Search: (
    <>
      <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M11 11l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </>
  ),
  Filter: (
    <path
      d="M2 4h12M4 8h8M6 12h4"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      fill="none"
    />
  ),
  Calendar: (
    <>
      <rect x="2" y="3" width="12" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M2 6h12M6 1.5v3M10 1.5v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </>
  ),
  Download: (
    <path
      d="M8 2v9m0 0l-3-3m3 3l3-3M2.5 13.5h11"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
  ),
  Plus: <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />,
  Receipt: (
    <>
      <path
        d="M5 3h14v18l-2.5-1.5L14 21l-2-1.5L10 21l-2.5-1.5L5 21V3z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M8 8h8M8 12h8M8 16h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </>
  ),
  Close: <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />,
  Chevron: (
    <path
      d="M5 6l3 3 3-3"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
  ),
  Check: (
    <path
      d="M3 8l3.5 3.5L13 5"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
  ),
  Sparkle: (
    <path d="M8 2l1.5 4.5L14 8l-4.5 1.5L8 14l-1.5-4.5L2 8l4.5-1.5L8 2z" fill="currentColor" opacity="0.85" />
  ),
  Upload: (
    <path
      d="M8 14V5m0 0l-3 3m3-3l3 3M2.5 2.5h11"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
  ),
};

const VIEW_BOX: Record<IconName, string> = {
  Search: "0 0 16 16",
  Filter: "0 0 16 16",
  Calendar: "0 0 16 16",
  Download: "0 0 16 16",
  Plus: "0 0 16 16",
  Receipt: "0 0 24 24",
  Close: "0 0 16 16",
  Chevron: "0 0 16 16",
  Check: "0 0 16 16",
  Sparkle: "0 0 16 16",
  Upload: "0 0 16 16",
};

export function Icon({ name, alias, size = 14, className, ...rest }: IconProps) {
  const a11y = alias ? { role: "img" as const, "aria-label": alias } : { "aria-hidden": true as const };
  return (
    <svg
      width={size}
      height={size}
      viewBox={VIEW_BOX[name]}
      fill="none"
      className={cn("inline-block shrink-0", className)}
      {...a11y}
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}

export function BrandLogo({ size = 30 }: { size?: number }) {
  return (
    <span
      aria-hidden
      style={{ width: size, height: size }}
      className="inline-grid place-items-center rounded-lg bg-gradient-to-br from-brand to-brand-2 font-mono text-[13px] font-extrabold tracking-tighter text-white"
    >
      CX
    </span>
  );
}
