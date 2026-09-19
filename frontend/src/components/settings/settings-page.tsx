"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  EmploymentType,
  ExperienceLevel,
  JobPreferences,
  NotificationPreferences,
  WorkMode,
} from "@/lib/opportunities/types";
import { EMPLOYMENT_TYPE_LABELS } from "@/lib/opportunities/types";
import { api } from "@/lib/api";
import { getAccessToken, signOut } from "@/lib/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";

const EXPERIENCE_OPTIONS: { value: ExperienceLevel; label: string }[] = [
  { value: "fresher", label: "Fresher" },
  { value: "entry", label: "0–1 years" },
  { value: "mid", label: "1–3 years" },
  { value: "senior", label: "3–5 years" },
  { value: "lead", label: "5+ years" },
];

const WORK_MODE_OPTIONS: { value: WorkMode; label: string }[] = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "on_site", label: "On-site" },
];

const JOB_TYPE_OPTIONS: EmploymentType[] = ["full_time", "internship", "contract"];

function Toggle({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  hint?: string;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 py-2">
      <span>
        <span className="block text-sm font-medium text-slate-800 dark:text-slate-200">{label}</span>
        {hint && <span className="block text-xs text-slate-500 dark:text-slate-400">{hint}</span>}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-5 w-5 shrink-0 accent-indigo-700"
      />
    </label>
  );
}

export function SettingsPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const loaded = useRef(false);

  const [targetRoles, setTargetRoles] = useState("");
  const [citiesRaw, setCitiesRaw] = useState("");
  const [anywhereIndia, setAnywhereIndia] = useState(false);
  const [remoteOk, setRemoteOk] = useState(false);
  const [workModes, setWorkModes] = useState<WorkMode[]>([]);
  const [jobTypes, setJobTypes] = useState<EmploymentType[]>([]);
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel | "">("");
  const [notif, setNotif] = useState<NotificationPreferences | null>(null);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    void (async () => {
      try {
        const t = await getAccessToken();
        setToken(t);
        if (!t) return;
        const [prefs, np] = await Promise.all([
          api.getJobPreferences(t),
          api.getNotificationPreferences(t),
        ]);
        setTargetRoles(prefs.target_roles.join(", "));
        setCitiesRaw(prefs.preferred_cities.filter((c) => c !== "anywhere").join(", "));
        setAnywhereIndia(prefs.preferred_cities.includes("anywhere"));
        setRemoteOk(prefs.remote_ok);
        setWorkModes(prefs.work_modes.filter((m) => m !== "any"));
        setJobTypes(prefs.employment_types);
        setExperienceLevel(prefs.experience_level ?? "");
        setNotif(np);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load settings");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function toggle<T>(list: T[], value: T, set: (next: T[]) => void) {
    set(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  async function saveCareer(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSaving(true);
    setError("");
    setSaved("");
    const payload: Partial<JobPreferences> = {
      target_roles: targetRoles.split(",").map((r) => r.trim()).filter(Boolean),
      preferred_cities: anywhereIndia
        ? ["anywhere"]
        : citiesRaw.split(",").map((c) => c.trim()).filter(Boolean),
      remote_ok: remoteOk,
      work_modes: workModes,
      employment_types: jobTypes,
      experience_level: experienceLevel || null,
    };
    try {
      await api.updateJobPreferences(payload, token);
      setSaved("Career preferences saved. Matches update immediately.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save preferences");
    } finally {
      setSaving(false);
    }
  }

  async function saveNotifications(next: NotificationPreferences) {
    if (!token) return;
    setNotif(next);
    try {
      await api.updateNotificationPreferences(next, token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save notification settings");
    }
  }

  async function exportData() {
    if (!token) return;
    try {
      const data = await api.exportAccount(token);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "careerpilot-export.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not export data");
    }
  }

  async function deleteAccount() {
    if (!token) return;
    try {
      await api.deleteAccount(token);
      await signOut();
      router.push("/");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete account");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Career preferences, notifications, privacy and account." />

      {error && <Alert>{error}</Alert>}
      {saved && <Alert tone="success">{saved}</Alert>}

      {loading ? (
        <div className="animate-pulse h-64 w-full bg-slate-200/70 dark:bg-slate-800 rounded-2xl" />
      ) : (
        <>
          <Card>
            <CardContent className="p-6">
              <h2 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-white">
                Career preferences
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                The same choices from onboarding — drives hard filters and match scores.
              </p>
              <form onSubmit={saveCareer} className="mt-4 space-y-4">
                <Input
                  label="Target roles (comma separated)"
                  value={targetRoles}
                  onChange={(e) => setTargetRoles(e.target.value)}
                  placeholder="Backend Engineer, Data Analyst"
                />
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Looking for
                  </span>
                  {JOB_TYPE_OPTIONS.map((t) => (
                    <Chip key={t} active={jobTypes.includes(t)} onClick={() => toggle(jobTypes, t, setJobTypes)}>
                      {EMPLOYMENT_TYPE_LABELS[t]}
                    </Chip>
                  ))}
                </div>
                <div>
                  <label htmlFor="settings-experience" className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                    Experience level
                  </label>
                  <select
                    id="settings-experience"
                    value={experienceLevel}
                    onChange={(e) => setExperienceLevel(e.target.value as ExperienceLevel | "")}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                  >
                    <option value="">No preference</option>
                    {EXPERIENCE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Work mode
                  </span>
                  {WORK_MODE_OPTIONS.map((o) => (
                    <Chip
                      key={o.value}
                      active={workModes.includes(o.value)}
                      onClick={() => toggle(workModes, o.value, setWorkModes)}
                    >
                      {o.label}
                    </Chip>
                  ))}
                </div>
                <Input
                  label="Preferred cities (comma separated)"
                  value={citiesRaw}
                  onChange={(e) => setCitiesRaw(e.target.value)}
                  placeholder="Bengaluru, Mumbai"
                  disabled={anywhereIndia}
                />
                <div className="divide-y divide-slate-100 dark:divide-slate-800">
                  <Toggle checked={anywhereIndia} onChange={setAnywhereIndia} label="Anywhere in India" hint="Don't restrict to one city." />
                  <Toggle checked={remoteOk} onChange={setRemoteOk} label="Open to remote" hint="Eligible remote roles pass location filters." />
                </div>
                <Button type="submit" loading={saving}>
                  Save preferences
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <h2 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-white">
                Notifications
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Email is only sent for categories you keep on. The in-app feed always records events.
              </p>
              {notif && (
                <div className="mt-2 divide-y divide-slate-100 dark:divide-slate-800">
                  <Toggle checked={notif.matching_jobs} onChange={(v) => saveNotifications({ ...notif, matching_jobs: v })} label="Job matches" />
                  <Toggle checked={notif.internships} onChange={(v) => saveNotifications({ ...notif, internships: v })} label="Internship alerts" />
                  <Toggle checked={notif.application_updates} onChange={(v) => saveNotifications({ ...notif, application_updates: v })} label="Application updates" />
                  <Toggle checked={notif.resume_suggestions} onChange={(v) => saveNotifications({ ...notif, resume_suggestions: v })} label="Resume suggestions" />
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <h2 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-white">
                Privacy & account
              </h2>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button variant="outline" onClick={exportData}>
                  Export my data
                </Button>
                {!confirmDelete ? (
                  <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
                    Delete account
                  </Button>
                ) : (
                  <span className="flex flex-wrap items-center gap-3">
                    <span className="text-sm text-slate-600 dark:text-slate-400">
                      Remove all profile, resume, application and saved data?
                    </span>
                    <Button variant="destructive" onClick={deleteAccount}>
                      Yes, delete everything
                    </Button>
                    <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
                      Cancel
                    </Button>
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
