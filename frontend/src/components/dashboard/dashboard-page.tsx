"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { Application, OpportunityRecord } from "@/lib/opportunities/types";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Alert } from "@/components/ui/alert";
import { ArrowRightIcon, BookmarkIcon, BriefcaseIcon, ClipboardDocumentListIcon } from "@/components/ui/icons";
import { OpportunityCard } from "@/components/opportunity/opportunity-card";

export function DashboardPage() {
  const [token, setToken] = useState<string | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [saved, setSaved] = useState<OpportunityRecord[]>([]);
  const [recent, setRecent] = useState<OpportunityRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    void (async () => {
      try {
        const t = await getAccessToken();
        setToken(t);
        if (t) {
          const [appsList, savedList] = await Promise.all([
            api.listApplications(t),
            api.listSaved(t),
          ]);
          setApps(appsList);
          setSaved(savedList);
        }
        const jobs = await api.listJobs({}, 1, 5, t);
        setRecent(jobs.items.slice(0, 5));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load dashboard");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const appliedCount = apps.filter((a) => a.status === "applied").length;
  const inProgressCount = apps.filter((a) =>
    ["prepared", "interview", "saved"].includes(a.status)
  ).length;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        subtitle="Your India job search at a glance."
        actions={
          <Link href="/jobs">
            <Button size="sm">
              Find jobs <ArrowRightIcon className="h-4 w-4" />
            </Button>
          </Link>
        }
      />

      {error && <Alert>{error}</Alert>}

      <div className="grid sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Applications</p>
              <p className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">{apps.length}</p>
              <p className="text-xs text-slate-400 mt-1">{appliedCount} applied, {inProgressCount} in progress</p>
            </div>
            <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
              <ClipboardDocumentListIcon className="h-5 w-5" aria-hidden="true" />
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Saved jobs</p>
              <p className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">{saved.length}</p>
              <p className="text-xs text-slate-400 mt-1">Shortlisted for later</p>
            </div>
            <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
              <BookmarkIcon className="h-5 w-5" aria-hidden="true" />
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Recent roles</p>
              <p className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">{recent.length}</p>
              <p className="text-xs text-slate-400 mt-1">Freshly discovered</p>
            </div>
            <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
              <BriefcaseIcon className="h-5 w-5" aria-hidden="true" />
            </span>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-white">Latest roles</h2>
            <Link
              href="/jobs"
              className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              Browse all <ArrowRightIcon className="h-4 w-4" />
            </Link>
          </div>
          {loading ? (
            <div className="animate-pulse space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-28 rounded-2xl bg-slate-200/70 dark:bg-slate-800" />
              ))}
            </div>
          ) : recent.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-sm text-slate-500">
                No roles discovered yet.
              </CardContent>
            </Card>
          ) : (
            recent.map((opp) => (
              <OpportunityCard key={opp.id} opportunity={opp} token={token} />
            ))
          )}
        </div>

        <aside className="space-y-4">
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold tracking-tight text-slate-900 dark:text-white">
                  Application tracker
                </h2>
                <Link
                  href="/applications"
                  className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline"
                >
                  View all <ArrowRightIcon className="h-3.5 w-3.5" />
                </Link>
              </div>
              {apps.length === 0 ? (
                <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                  Nothing tracked yet. Save a role and start your first application.
                </p>
              ) : (
                <ul className="mt-3 space-y-2.5">
                  {apps.slice(0, 4).map((app) => (
                    <li key={app.id} className="flex items-center justify-between gap-2 text-sm">
                      <span className="min-w-0 truncate text-slate-700 dark:text-slate-300">
                        {typeof app.role_snapshot?.title === "string" && app.role_snapshot.title
                          ? app.role_snapshot.title
                          : "Role"}
                      </span>
                      <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                        {app.status.replace("_", " ")}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
          {token && (
            <Card>
              <CardContent className="p-5">
                <h2 className="text-base font-semibold tracking-tight text-slate-900 dark:text-white">
                  Better matches
                </h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Complete your profile so every role gets an accurate match score.
                </p>
                <Link href="/profile" className="mt-3 block">
                  <Button variant="outline" size="sm" className="w-full">
                    Complete your profile
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}