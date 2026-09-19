export const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Jobs", href: "/jobs" },
  { label: "Internships", href: "/internships" },
  { label: "Resume", href: "/resume" },
  { label: "Applications", href: "/applications" },
  { label: "Profile", href: "/profile" },
] as const;

export const SECONDARY_NAV_ITEMS = [
  { label: "Recommended", href: "/recommended" },
  { label: "Saved", href: "/saved" },
  { label: "Settings", href: "/settings" },
] as const;

export const ADMIN_NAV_ITEM = { label: "Admin", href: "/admin" } as const;

export type NavLabel = (typeof NAV_ITEMS)[number]["label"];