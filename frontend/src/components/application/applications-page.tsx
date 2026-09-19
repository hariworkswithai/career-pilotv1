"use client";

import { useEffect, useRef, useState } from "react";
import type { Application } from "@/lib/opportunities/types";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Alert } from "@/components/ui/alert";
import { externalUrlLabel } from "@/lib/application-label";

const STATUS_STYLES: Record<string, string> = {
  saved: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
  prepared: "bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
  applied: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  interview: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  rejected: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  offer: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  withdrawn: "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400",
};

const STATUS_OPTIONS = [
  "saved",
  "prepared",
  "applied",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

export function ApplicationsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
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
          setApps(await api.listApplications(t));
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load applications");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function updateStatus(id: string, status: string) {
    if (!token) return;
    try {
      const updated = await api.updateApplication(id, { status }, token);
      setApps((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update application");
    }
  }

  const roleTitle = (app: Application) => {
    const role = app.role_snapshot?.title;
    return typeof role === "string" && role ? role : "Role";
  };
  const company = (app: Application) => {
    const name = app.company_snapshot?.name;
    return typeof name === "string" && name ? name : "Company";
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Applications"
        subtitle="Track every role you're pursuing."
      />

      {error && <Alert>{error}</Alert>}

      {loading ? (
        <div className="animate-pulse space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-slate-100 dark:bg-slate-800" />
          ))}
        </div>
      ) : apps.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-sm text-slate-500">
            No applications yet. Browse jobs and start your first application.
          </CardContent>
        </Card>
      ) : (
        apps.map((app) => (
          <Card key={app.id}>
            <CardContent className="p-5">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-slate-900 dark:text-white truncate">
                    {roleTitle(app)}
                  </h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{company(app)}</p>
                </div>
                <div className="flex items-center gap-3">
                  <select
                    value={app.status}
                    onChange={(e) => updateStatus(app.id, e.target.value)}
                    className={`rounded-full border border-transparent px-3 py-1 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 ${STATUS_STYLES[app.status] ?? ""}`}
                    aria-label="Application status"
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s} className="bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100">
                        {s}
                      </option>
                    ))}
                  </select>
                  {app.destination_url && (
                    <a
                      href={app.destination_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center rounded-lg border border-slate-300 bg-transparent px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-500 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {externalUrlLabel(app.destination_url)}
                    </a>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}