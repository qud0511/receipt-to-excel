import { apiFetch } from "./client";
import type { AttendeeView, ProjectView, TeamGroupView, VendorView } from "./types";

export function getVendors(q = "", limit = 8): Promise<VendorView[]> {
  const sp = new URLSearchParams({ q, limit: String(limit) });
  return apiFetch(`/vendors?${sp.toString()}`);
}

export function getProjects(vendorId: number, limit = 8): Promise<ProjectView[]> {
  const sp = new URLSearchParams({ vendor_id: String(vendorId), limit: String(limit) });
  return apiFetch(`/projects?${sp.toString()}`);
}

export function getAttendees(q: string): Promise<AttendeeView[]> {
  const sp = new URLSearchParams({ q });
  return apiFetch(`/attendees?${sp.toString()}`);
}

export function getTeamGroups(): Promise<TeamGroupView[]> {
  return apiFetch("/team-groups");
}
