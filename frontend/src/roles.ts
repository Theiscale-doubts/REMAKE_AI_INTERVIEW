/**
 * The four interview domains the product supports. This list is the single
 * source of truth on the frontend and must stay in sync with DOMAIN_QUESTIONS
 * in backend/agent.py — the value sent to the API is matched there, and an
 * unknown value falls back to the HR interview.
 */
export const ROLES = [
  { value: "hr", label: "HR / Managerial" },
  { value: "data_analytics", label: "Data Analytics" },
  { value: "datascience", label: "Data Science" },
  { value: "ai_engineer", label: "AI Engineer" },
] as const;

export type RoleValue = (typeof ROLES)[number]["value"];

export const DEFAULT_ROLE: RoleValue = "hr";

/** Human-readable name for a stored role value (results, headers, PDFs). */
export function roleLabel(value: string): string {
  const match = ROLES.find((r) => r.value === value);
  if (match) return match.label;
  // Legacy/unknown values (e.g. interviews recorded before the domain list was
  // narrowed) still need to render something readable rather than a raw slug.
  if (!value) return "";
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
