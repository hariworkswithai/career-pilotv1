import type {
  ExperienceLevel,
  EmploymentType,
  WorkplaceType,
} from "@/lib/opportunities/types";

export function formatSalaryMinMax(
  min?: number | null,
  max?: number | null,
  currency?: string | null,
  text?: string | null
): string {
  if (text) return text;
  if (min === undefined || min === null) return "Salary not disclosed";
  const symbol = currency === "EUR" ? "€" : currency === "GBP" ? "£" : "$";
  const fmt = (n: number) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(n));
  if (max) return `${symbol}${fmt(min)} – ${symbol}${fmt(max)}`;
  return `${symbol}${fmt(min)}+`;
}

export function formatPostedAt(iso: string | null | undefined, relative = false): string {
  if (!iso) return "Posted date unknown";
  const posted = new Date(iso);
  if (Number.isNaN(posted.getTime())) return "Posted date unknown";
  if (relative) {
    const days = Math.floor((Date.now() - posted.getTime()) / 86_400_000);
    if (days <= 0) return "Posted today";
    if (days === 1) return "Posted yesterday";
    if (days < 30) return `Posted ${days} days ago`;
    const months = Math.floor(days / 30);
    return `Posted ${months} month${months === 1 ? "" : "s"} ago`;
  }
  return `Posted ${posted.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  })}`;
}

export function locationLabel(location: {
  is_remote?: boolean;
  remote_scope?: string;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  raw?: string;
}): string {
  if (location.is_remote) {
    const scope = location.remote_scope || "none";
    if (scope === "worldwide") return "Remote (Worldwide)";
    if (scope === "india") return "Remote (India)";
    if (scope !== "none") return "Remote (outside India)";
    return "Remote";
  }
  const parts = [location.city, location.state, location.country].filter(Boolean);
  return parts.length ? parts.join(", ") : location.raw || "Location not specified";
}

export function employmentTypeLabel(value: EmploymentType | string): string {
  const labels: Record<string, string> = {
    full_time: "Full-time",
    part_time: "Part-time",
    internship: "Internship",
    contract: "Contract",
    temporary: "Temporary",
  };
  return labels[value] ?? value;
}

export function workplaceTypeLabel(value: WorkplaceType | string): string {
  const labels: Record<string, string> = {
    on_site: "On-site",
    hybrid: "Hybrid",
    remote: "Remote",
  };
  return labels[value] ?? value;
}

export function experienceLevelLabel(value?: ExperienceLevel | string | null): string {
  if (!value) return "Any level";
  const labels: Record<string, string> = {
    fresher: "Fresher",
    entry: "Entry level",
    mid: "Mid level",
    senior: "Senior",
    lead: "Lead",
  };
  return labels[value] ?? value;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}