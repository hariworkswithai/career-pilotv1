"use client";

import { useEffect, useRef, useState } from "react";
import type {
  AdminUserOverview,
  AuditLog,
  JobSource,
} from "@/lib/opportunities/types";
import { api, ApiError } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";

type Tab = "overview" | "sources" | "users" | "audit";

const SOURCE_TYPES = ["greenhouse", "ashby", "lever"] as const;

const HEALTH_STYLES: Record<string, string> = {
  healthy: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  failed: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  disabled: "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400",
  never: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
};

export function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [forbidden, setForbidden] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<Record<string, number | string> | null>(null);
  const [sources, setSources] = useState<JobSource[]>([]);
  const [users, setUsers] = useState<AdminUserOverview[]>([]);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [newType, setNewType] = useState<string>("greenhouse");
  const [newBoard, setNewBoard] = useState("");
  const [newCompany, setNewCompany] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    void (async () => {
      try {
        const t = await getAccessToken();
        setToken(t);
        if (!t) return;
        const [s, src, u, a] = await Promise.all([
          api.adminStatus(t),
          api.adminSources(t),
          api.adminUsers(t),
          api.adminAuditLogs(t, 50),
        ]);
        setStatus(s);
        setSources(src);
        setUsers(u);
        setAudit(a);
      } catch (e) {
        if (e instanceof ApiError && e.status === 403) setForbidden(true);
        else setError(e instanceof Error ? e.message : "Could not load admin data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function refreshSources() {
    if (!token) return;
    setSources(await api.adminSources(token));
    setStatus(await api.adminStatus(token));
  }

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Admin action failed");
    } finally {
      setBusy("");
    }
  }

  if (loading) {
    return <div className="animate-pulse h-64 w-full bg-slate-200/70 dark:bg-slate-800 rounded-2xl" />;
  }

  if (forbidden) {
    return (
      <div className="space-y-6">
        <PageHeader title="Admin" subtitle="Restricted area." />
        <Alert>Admin access required. This area is enforced server-side.</Alert>
      </div>
    );
  }

  const metrics: [string, string][] = status
    ? [
        ["Active jobs", String(status.active_jobs ?? 0)],
        ["Sources active", `${status.sources_active ?? 0} / ${status.sources_total ?? 0}`],
        ["Sources failed", String(status.sources_failed ?? 0)],
        ["AI events", String(status.ai_usage_events ?? 0)],
      ]
    : [];

  return (
    <div className="space-y-6">
      <PageHeader title="Admin" subtitle="Sources, users, audit trail and platform health." />

      {error && <Alert>{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Admin sections">
        {(["overview", "sources", "users", "audit"] as Tab[]).map((t) => (
          <Chip key={t} active={tab === t} onClick={() => setTab(t)}>
            {t === "overview" ? "Overview" : t === "sources" ? "Job sources" : t === "users" ? "Users" : "Audit log"}
          </Chip>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map(([label, value]) => (
            <Card key={label}>
              <CardContent className="p-5">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
                <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">{value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {tab === "sources" && token && (
        <div className="space-y-4">
          <Card>
            <CardContent className="p-5">
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">Add source</h2>
              <form
                className="mt-3 grid gap-3 sm:grid-cols-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  void run("add", async () => {
                    if (!token) return;
                    await api.adminCreateSource(
                      { source_type: newType, board_identifier: newBoard.trim(), company_name: newCompany.trim() },
                      token
                    );
                    setNewBoard("");
                    setNewCompany("");
                    await refreshSources();
                    setNotice("Source saved.");
                  });
                }}
              >
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Type</span>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
                  >
                    {SOURCE_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="sm:col-span-1">
                  <Input label="Board identifier" value={newBoard} onChange={(e) => setNewBoard(e.target.value)} placeholder="myco" required />
                </div>
                <div className="sm:col-span-1">
                  <Input label="Company" value={newCompany} onChange={(e) => setNewCompany(e.target.value)} placeholder="MyCo" />
                </div>
                <div className="flex items-end">
                  <Button type="submit" loading={busy === "add"}>
                    Save
                  </Button>
                </div>
              </form>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                Only Greenhouse, Ashby and Lever boards. Identifiers are validated — arbitrary URLs are never fetched.
              </p>
            </CardContent>
          </Card>

          {sources.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-sm text-slate-500">
                No sources registered yet. Add the first board above.
              </CardContent>
            </Card>
          ) : (
            sources.map((s) => (
              <Card key={s.id}>
                <CardContent className="p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-900 dark:text-white">
                        {s.company_name || s.board_identifier}{" "}
                        <span className="font-normal text-slate-500">· {s.source_type} / {s.board_identifier}</span>
                      </p>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        Last sync: {s.last_synced_at ? new Date(s.last_synced_at).toLocaleString() : "never"}
                        {s.last_error ? ` · ${s.last_error.slice(0, 120)}` : ""}
                      </p>
                    </div>
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${HEALTH_STYLES[s.is_active ? s.last_sync_status : "disabled"] ?? HEALTH_STYLES.never}`}>
                      {s.is_active ? s.last_sync_status : "disabled"}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      loading={busy === `test-${s.id}`}
                      onClick={() =>
                        run(`test-${s.id}`, async () => {
                          if (!token) return;
                          const r = await api.adminTestSource(s.id, token);
                          setNotice(r.message);
                        })
                      }
                    >
                      Test connection
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      loading={busy === `trigger-${s.id}`}
                      onClick={() =>
                        run(`trigger-${s.id}`, async () => {
                          if (!token) return;
                          const r = await api.adminTriggerSource(s.id, token);
                          await refreshSources();
                          setNotice(`Sync done: ${r.fetched} fetched, ${r.inserted} inserted, ${r.updated} updated.`);
                        })
                      }
                    >
                      Sync now
                    </Button>
                    <Button
                      variant={s.is_active ? "secondary" : "primary"}
                      size="sm"
                      loading={busy === `toggle-${s.id}`}
                      onClick={() =>
                        run(`toggle-${s.id}`, async () => {
                          if (!token) return;
                          await api.adminUpdateSource(s.id, { is_active: !s.is_active }, token);
                          await refreshSources();
                        })
                      }
                    >
                      {s.is_active ? "Disable" : "Enable"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {tab === "users" && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-700 text-xs uppercase tracking-wider text-slate-500">
                    <th className="px-5 py-3">User</th>
                    <th className="px-5 py-3">Role</th>
                    <th className="px-5 py-3">Applications</th>
                    <th className="px-5 py-3">Resumes</th>
                    <th className="px-5 py-3">Saved</th>
                    <th className="px-5 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.user_id} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                      <td className="px-5 py-3">
                        <p className="font-medium text-slate-900 dark:text-white">{u.full_name || "—"}</p>
                        <p className="font-mono text-xs text-slate-400">{u.user_id.slice(0, 8)}…</p>
                      </td>
                      <td className="px-5 py-3">{u.is_admin ? "admin" : "user"}</td>
                      <td className="px-5 py-3">{u.applications}</td>
                      <td className="px-5 py-3">{u.resumes}</td>
                      <td className="px-5 py-3">{u.saved_jobs}</td>
                      <td className="px-5 py-3 text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          loading={busy === `role-${u.user_id}`}
                          onClick={() =>
                            run(`role-${u.user_id}`, async () => {
                              if (!token) return;
                              const updated = await api.adminSetRole(u.user_id, !u.is_admin, token);
                              setUsers((prev) => prev.map((p) => (p.user_id === u.user_id ? updated : p)));
                              setNotice(`Role updated for ${u.full_name || u.user_id.slice(0, 8)}.`);
                            })
                          }
                        >
                          {u.is_admin ? "Revoke admin" : "Make admin"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "audit" && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-700 text-xs uppercase tracking-wider text-slate-500">
                    <th className="px-5 py-3">Time</th>
                    <th className="px-5 py-3">Action</th>
                    <th className="px-5 py-3">Resource</th>
                    <th className="px-5 py-3">Actor</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.map((log) => (
                    <tr key={log.id} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                      <td className="whitespace-nowrap px-5 py-3 text-xs text-slate-500">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-5 py-3 font-mono text-xs">{log.action}</td>
                      <td className="px-5 py-3 text-xs text-slate-500">
                        {log.resource_type ? `${log.resource_type}:${String(log.resource_id).slice(0, 8)}` : "—"}
                      </td>
                      <td className="px-5 py-3 font-mono text-xs text-slate-500">
                        {log.actor_user_id.slice(0, 8)}…
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
