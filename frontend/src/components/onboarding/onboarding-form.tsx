"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type {
  EmploymentType,
  ExperienceLevel,
  WorkMode,
} from "@/lib/opportunities/types";

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

export function OnboardingForm() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [fullName, setFullName] = useState("");
  const [city, setCity] = useState("");
  const [jobTypes, setJobTypes] = useState<EmploymentType[]>(["full_time"]);
  const [targetRoles, setTargetRoles] = useState("");
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel | "">("");
  const [workModes, setWorkModes] = useState<WorkMode[]>([]);
  const [citiesRaw, setCitiesRaw] = useState("");
  const [anywhereIndia, setAnywhereIndia] = useState(false);
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void getAccessToken().then((t) => setToken(t));
  }, []);

  function toggleJobType(value: EmploymentType) {
    setJobTypes((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
  }

  function toggleWorkMode(value: WorkMode) {
    setWorkModes((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const roles = targetRoles.split(",").map((r) => r.trim()).filter(Boolean);
    if (roles.length === 0) {
      setError("Target role is required. Add at least one role you are seeking.");
      return;
    }
    if (!token) {
      setError("You must be signed in.");
      return;
    }
    setLoading(true);
    try {
      await api.completeOnboarding(
        {
          full_name: fullName,
          city,
          target_roles: roles,
          employment_types: jobTypes,
          experience_level: experienceLevel || null,
          work_modes: workModes,
          preferred_cities: citiesRaw.split(",").map((c) => c.trim()).filter(Boolean),
          anywhere_india: anywhereIndia,
          remote_only: remoteOnly,
        },
        token
      );
      router.push("/dashboard");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not complete onboarding.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tell us what you're looking for"
        subtitle="We only ask what your resume can't tell us. You can change everything later in Settings."
      />

      {error && <Alert>{error}</Alert>}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardContent className="p-6 space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <Input
                label="Name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Priya Sharma"
                autoComplete="name"
              />
              <Input
                label="City"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="Bengaluru"
              />
            </div>

            <fieldset>
              <legend className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                I&apos;m looking for
              </legend>
              <div className="flex gap-2 flex-wrap">
                {(["full_time", "internship", "contract", "part_time"] as EmploymentType[]).map(
                  (value) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={jobTypes.includes(value)}
                      onClick={() => toggleJobType(value)}
                      className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                        jobTypes.includes(value)
                          ? "border-indigo-600 bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300"
                          : "border-slate-300 text-slate-600 hover:border-slate-400 dark:border-slate-600 dark:text-slate-300"
                      }`}
                    >
                      {value.replace("_", " ")}
                    </button>
                  )
                )}
              </div>
            </fieldset>

            <Textarea
              label="Target roles (required)"
              value={targetRoles}
              onChange={(e) => setTargetRoles(e.target.value)}
              placeholder="Software Engineer, Backend Engineer"
              helperText="One or more roles, separated by commas"
            />

            <div className="grid sm:grid-cols-2 gap-4">
              <label className="block">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Experience level
                </span>
                <select
                  value={experienceLevel}
                  onChange={(e) => setExperienceLevel(e.target.value as ExperienceLevel)}
                  className="mt-1 block w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white"
                >
                  <option value="">Select…</option>
                  {EXPERIENCE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <fieldset>
              <legend className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Work mode
              </legend>
              <div className="flex gap-2 flex-wrap">
                {WORK_MODE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    aria-pressed={workModes.includes(opt.value)}
                    onClick={() => toggleWorkMode(opt.value)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                      workModes.includes(opt.value) || remoteOnly
                        ? "border-indigo-600 bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300"
                        : "border-slate-300 text-slate-600 hover:border-slate-400 dark:border-slate-600 dark:text-slate-300"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </fieldset>

            <div className="space-y-3 pt-1">
              <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={anywhereIndia}
                  onChange={(e) => setAnywhereIndia(e.target.checked)}
                  className="rounded border-slate-300 text-indigo-600"
                />
                I&apos;m open to working anywhere in India
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={remoteOnly}
                  onChange={(e) => setRemoteOnly(e.target.checked)}
                  className="rounded border-slate-300 text-indigo-600"
                />
                I only want remote roles
              </label>
              {!anywhereIndia && !remoteOnly && (
                <Input
                  label="Preferred cities"
                  value={citiesRaw}
                  onChange={(e) => setCitiesRaw(e.target.value)}
                  placeholder="Bengaluru, Mumbai, Pune"
                  helperText="Comma-separated. Leave blank if you have no preference."
                />
              )}
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" loading={loading} disabled={!token}>
            Finish setup
          </Button>
        </div>
      </form>
    </div>
  );
}