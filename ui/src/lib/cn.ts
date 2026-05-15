import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind 클래스 병합 (shadcn/ui 표준). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
