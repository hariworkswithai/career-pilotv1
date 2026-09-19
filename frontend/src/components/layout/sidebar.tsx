"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ADMIN_NAV_ITEM, NAV_ITEMS, SECONDARY_NAV_ITEMS } from "@/lib/navigation";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { BrandMark } from "@/components/ui/brand-mark";
import {
  BellIcon,
  BookmarkIcon,
  BriefcaseIcon,
  ClipboardDocumentListIcon,
  CogIcon,
  DocumentTextIcon,
  HomeIcon,
  ShieldIcon,
  SparklesIcon,
  UserCircleIcon,
  XIcon,
} from "@/components/ui/icons";

const NAV_ICONS: Record<string, (props: { className?: string }) => React.ReactNode> = {
  Dashboard: (p) => <HomeIcon {...p} />,
  Jobs: (p) => <BriefcaseIcon {...p} />,
  Internships: (p) => <SparklesIcon {...p} />,
  Resume: (p) => <DocumentTextIcon {...p} />,
  Applications: (p) => <ClipboardDocumentListIcon {...p} />,
  Profile: (p) => <UserCircleIcon {...p} />,
  Saved: (p) => <BookmarkIcon {...p} />,
  Recommended: (p) => <SparklesIcon {...p} />,
  Settings: (p) => <CogIcon {...p} />,
  Notifications: (p) => <BellIcon {...p} />,
  Admin: (p) => <ShieldIcon {...p} />,
};

function FallbackIcon(props: { className?: string }) {
  return <HomeIcon {...props} />;
}

function NavLink({
  href,
  label,
  pathname,
  onClose,
}: {
  href: string;
  label: string;
  pathname: string | null;
  onClose: () => void;
}) {
  const isActive = pathname === href || (pathname ?? "").startsWith(`${href}/`);
  const Icon = NAV_ICONS[label] ?? FallbackIcon;
  return (
    <Link
      href={href}
      onClick={onClose}
      aria-current={isActive ? "page" : undefined}
      className={`
        flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors
        ${isActive
          ? "bg-indigo-950 text-white shadow-sm dark:bg-indigo-600"
          : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"}
      `}
    >
      <Icon className="h-5 w-5 shrink-0" />
      {label}
    </Link>
  );
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void getAccessToken().then((token) => {
      if (!token || cancelled) return;
      // Server enforces admin access; this only decides whether to show the link.
      api
        .adminStatus(token)
        .then(() => {
          if (!cancelled) setIsAdmin(true);
        })
        .catch(() => {});
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-slate-900/50 transition-opacity lg:hidden ${
          isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 w-72 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800
          transform transition-transform lg:translate-x-0
          ${isOpen ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        <div className="flex items-center justify-between h-16 px-4 border-b border-slate-200 dark:border-slate-800">
          <Link href="/dashboard" className="flex items-center gap-2.5" onClick={onClose}>
            <BrandMark className="h-8 w-8" />
            <span className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">CareerPilot</span>
          </Link>
          <button
            className="lg:hidden p-2 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            onClick={onClose}
            aria-label="Close navigation menu"
          >
            <XIcon />
          </button>
        </div>
        <nav className="p-4 space-y-1" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.href} href={item.href} label={item.label} pathname={pathname} onClose={onClose} />
          ))}
        </nav>
        <div className="px-4 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
          Library
        </div>
        <nav className="px-4 space-y-1" aria-label="Secondary">
          {SECONDARY_NAV_ITEMS.map((item) => (
            <NavLink key={item.href} href={item.href} label={item.label} pathname={pathname} onClose={onClose} />
          ))}
          {isAdmin && (
            <NavLink
              href={ADMIN_NAV_ITEM.href}
              label={ADMIN_NAV_ITEM.label}
              pathname={pathname}
              onClose={onClose}
            />
          )}
        </nav>
      </aside>
    </>
  );
}