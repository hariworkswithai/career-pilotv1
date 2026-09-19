"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() ?? "";
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const token = await getAccessToken();
      if (!token) {
        if (!cancelled) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
        return;
      }
      if (pathname === "/onboarding") {
        if (!cancelled) setReady(true);
        return;
      }
      try {
        const profile = await api.getProfile(token);
        if (!cancelled && profile && profile.onboarding_completed === false) {
          router.replace("/onboarding");
          return;
        }
        if (!cancelled) setReady(true);
      } catch {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  if (!ready) {
    return (
      <div className="flex items-center justify-center py-24" aria-busy="true">
        <div className="h-8 w-8 rounded-full border-2 border-slate-300 border-t-indigo-600 animate-spin" />
      </div>
    );
  }
  return <>{children}</>;
}