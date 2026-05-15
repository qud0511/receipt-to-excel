import { apiFetch } from "./client";
import type { DashboardSummaryResponse } from "./types";

export function getDashboardSummary(): Promise<DashboardSummaryResponse> {
  return apiFetch("/dashboard/summary");
}
