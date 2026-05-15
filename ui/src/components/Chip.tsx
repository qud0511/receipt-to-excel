import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const chipVariants = cva(
  "inline-flex items-center gap-1.5 rounded-md px-2.5 h-8 text-[13px] font-medium transition-colors disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-surface-2 text-text-2 hover:bg-bg",
        outline: "border border-border bg-transparent text-text-2 hover:bg-surface-2",
      },
      active: {
        true: "bg-brand-soft text-brand border border-brand-border",
        false: "",
      },
    },
    defaultVariants: { variant: "default", active: false },
  },
);

export interface ChipProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type">,
    VariantProps<typeof chipVariants> {}

export const Chip = forwardRef<HTMLButtonElement, ChipProps>(
  ({ className, variant, active, ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      className={cn(chipVariants({ variant, active }), className)}
      aria-pressed={active ? true : undefined}
      {...props}
    />
  ),
);
Chip.displayName = "Chip";
