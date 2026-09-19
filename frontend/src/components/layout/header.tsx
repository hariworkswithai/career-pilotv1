"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BellIcon, MenuIcon, UserCircleIcon, LogoutIcon } from "@/components/ui/icons";
import { BrandMark } from "@/components/ui/brand-mark";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { getAccessToken, signOut } from "@/lib/auth";

interface HeaderUser {
  name: string;
  email: string;
}

export function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const [user, setUser] = useState<HeaderUser>({ name: "User", email: "" });
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const pathname = usePathname();

  useEffect(() => {
    const supabase = createClient();

    async function loadUser() {
      const {
        data: { user: sessionUser },
      } = await supabase.auth.getUser();
      if (sessionUser) {
        setUser({
          name: sessionUser.user_metadata.full_name || sessionUser.email?.split("@")[0] || "User",
          email: sessionUser.email || "",
        });
      }
    }

    loadUser();

    getAccessToken()
      .then((token) => {
        if (!token) return;
        return api.listNotifications(token);
      })
      .then((items) => {
        if (items) setUnread(items.filter((n) => !n.read_at).length);
      })
      .catch(() => {});

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        setUser({
          name: session.user.user_metadata.full_name || session.user.email?.split("@")[0] || "User",
          email: session.user.email || "",
        });
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [pathname]);

  return (
    <header className="sticky top-0 z-30 h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm border-b border-slate-200 dark:border-slate-800">
      <div className="h-full px-4 lg:px-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            className="lg:hidden"
            onClick={onMenuClick}
            aria-label="Open navigation menu"
          >
            <MenuIcon />
          </Button>
          <Link href="/dashboard" className="hidden items-center gap-2.5 lg:flex" aria-label="CareerPilot Home">
            <BrandMark className="h-8 w-8" />
            <span className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">CareerPilot</span>
          </Link>
        </div>

        <div className="flex items-center gap-1">
          <Link
            href="/notifications"
            aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
            className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          >
            <BellIcon className="h-5 w-5" />
            {unread > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-indigo-600 px-1 text-[10px] font-bold text-white">
                {unread > 9 ? "9+" : unread}
              </span>
            )}
          </Link>
          <div className="relative">
          <Button
            variant="ghost"
            size="sm"
            className="flex items-center gap-2 px-3 py-1.5"
            onClick={() => setDropdownOpen((open) => !open)}
            aria-expanded={dropdownOpen}
            aria-haspopup="true"
          >
            <div className="h-8 w-8 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
              <UserCircleIcon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <span className="hidden sm:block text-sm font-medium text-slate-700 dark:text-slate-300">
              {user.name}
            </span>
          </Button>

          {dropdownOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setDropdownOpen(false)} aria-hidden="true" />
              <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 shadow-lg py-1 z-50">
                <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-700">
                  <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{user.name}</p>
                  {user.email && (
                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{user.email}</p>
                  )}
                </div>
                <Link
                  href="/profile"
                  className="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
                  onClick={() => setDropdownOpen(false)}
                >
                  <UserCircleIcon className="h-4 w-4" aria-hidden="true" />
                  Profile
                </Link>
                <button
                  onClick={async () => {
                    await signOut();
                    setDropdownOpen(false);
                  }}
                  className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-slate-100 dark:hover:bg-slate-700"
                >
                  <LogoutIcon className="h-4 w-4" aria-hidden="true" />
                  Sign out
                </button>
              </div>
            </>
          )}
          </div>
        </div>
      </div>
    </header>
  );
}