"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "@/lib/navigation";
import {
  BriefcaseIcon,
  ClipboardDocumentListIcon,
  DocumentTextIcon,
  HomeIcon,
  SparklesIcon,
  UserCircleIcon,
} from "@/components/ui/icons";

const NAV_ICONS: Record<string, (props: { className?: string }) => React.ReactNode> = {
  Dashboard: (p) => <HomeIcon {...p} />,
  Jobs: (p) => <BriefcaseIcon {...p} />,
  Internships: (p) => <SparklesIcon {...p} />,
  Resume: (p) => <DocumentTextIcon {...p} />,
  Applications: (p) => <ClipboardDocumentListIcon {...p} />,
  Profile: (p) => <UserCircleIcon {...p} />,
};

/**
 * Mobile bottom tab bar (approved mobile direction). Same destinations as the
 * sidebar; visible below the lg breakpoint.
 */
export function MobileNav() {
  const pathname = usePathname() ?? "";

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-sm lg:hidden dark:border-slate-800 dark:bg-slate-900/95"
    >
      <div className="grid grid-cols-6">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = NAV_ICONS[item.label] ?? ((p) => <HomeIcon {...p} />);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={`flex flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors ${
                isActive
                  ? "text-indigo-700 dark:text-indigo-300"
                  : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
              }`}
            >
              <Icon className="h-5 w-5" />
              <span className="leading-none">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
