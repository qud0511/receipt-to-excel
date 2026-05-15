import { NavLink, useLocation } from "react-router-dom";
import { cn } from "@/lib/cn";
import { BrandLogo } from "./Icon";
import { StepIndicator, type StepKey } from "./StepIndicator";

interface TopNavProps {
  userName?: string;
  className?: string;
}

function stepFromPath(pathname: string): StepKey | null {
  if (pathname.startsWith("/upload")) return "upload";
  if (pathname.startsWith("/verify")) return "verify";
  if (pathname.startsWith("/result")) return "result";
  return null;
}

export function TopNav({ userName, className }: TopNavProps) {
  const { pathname } = useLocation();
  const step = stepFromPath(pathname);

  return (
    <header
      className={cn(
        "flex h-14 shrink-0 items-center gap-6 border-b border-border bg-surface px-6",
        className,
      )}
    >
      <NavLink to="/" className="flex items-center gap-2.5 font-bold tracking-tight">
        <BrandLogo />
        <span>CreditXLSX</span>
      </NavLink>

      <nav className="flex items-center gap-1">
        {step ? (
          <StepIndicator current={step} />
        ) : (
          <>
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                cn(
                  "inline-flex h-8 items-center rounded-md px-3 text-[13px] font-medium",
                  isActive ? "bg-bg text-text font-semibold" : "text-text-3 hover:bg-bg hover:text-text",
                )
              }
            >
              대시보드
            </NavLink>
            <NavLink
              to="/templates"
              className={({ isActive }) =>
                cn(
                  "inline-flex h-8 items-center rounded-md px-3 text-[13px] font-medium",
                  isActive ? "bg-bg text-text font-semibold" : "text-text-3 hover:bg-bg hover:text-text",
                )
              }
            >
              템플릿
            </NavLink>
          </>
        )}
      </nav>

      <div className="ml-auto flex items-center gap-3">
        {userName ? (
          <>
            <span className="text-[12px] text-text-3">{userName}</span>
            <span
              aria-label={`${userName} 프로필`}
              className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-brand to-brand-2 text-[11px] font-bold text-white"
            >
              {userName.slice(0, 1)}
            </span>
          </>
        ) : null}
      </div>
    </header>
  );
}
