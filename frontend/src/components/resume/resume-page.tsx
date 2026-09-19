"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Alert } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { CheckCircleIcon, DownloadIcon, TrashIcon, UploadIcon } from "@/components/ui/icons";
import type {
  ChangeItem,
  EnhancementDraft,
  ResumeAnalysis,
  ResumeRecord,
  ResumeVersionRecord,
} from "@/lib/resume/types";

export function ResumePage() {
  const [token, setToken] = useState<string | null>(null);
  const [resumes, setResumes] = useState<ResumeRecord[]>([]);
  const [selected, setSelected] = useState<ResumeRecord | null>(null);
  const [versions, setVersions] = useState<ResumeVersionRecord[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const [analysis, setAnalysis] = useState<ResumeAnalysis | null>(null);
  const [draft, setDraft] = useState<EnhancementDraft | null>(null);
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [targetRole, setTargetRole] = useState("");
  const [busy, setBusy] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    void getAccessToken().then((t) => {
      setToken(t);
      if (t) void apiFetchResumes(t);
    });
  }, []);

  async function apiFetchResumes(t: string) {
    try {
      const list = await api.getResumes(t);
      setResumes(list);
    } catch {
      setResumes([]);
    }
  }

  async function refreshVersions(t: string, resumeId: string) {
    try {
      setVersions(await api.getResumeVersions(resumeId, t));
    } catch {
      setVersions([]);
    }
  }

  const selectResume = useCallback(
    (resume: ResumeRecord, t: string) => {
      setSelected(resume);
      setAnalysis(null);
      setDraft(null);
      setAccepted({});
      void refreshVersions(t, resume.id);
    },
    []
  );

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !file) return;
    setUploading(true);
    setError("");
    setSuccess("");
    try {
      const result = await api.uploadResume(file, token);
      setSuccess(`Uploaded ${file.name}.`);
      setFile(null);
      await apiFetchResumes(token);
      const updated = await api.getResumes(token);
      const uploaded = updated.find((r) => r.id === result.id);
      if (uploaded) selectResume(uploaded, token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload resume");
    } finally {
      setUploading(false);
    }
  }

  async function runParse() {
    if (!token || !selected) return;
    setBusy(true);
    setError("");
    try {
      const parsed = await api.parseResume(selected.id, token);
      setSuccess(
        `Parsed: ${parsed.name ? `${parsed.name} · ` : ""}${parsed.skills.length} skills, ` +
          `${parsed.experience.length} jobs, ${parsed.education.length} entries parsed.`
      );
      await apiFetchResumes(token);
      const updated = await api.getResumes(token);
      const fresh = updated.find((r) => r.id === selected.id);
      if (fresh) setSelected(fresh);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not parse this resume.");
    } finally {
      setBusy(false);
    }
  }

  async function runAnalyze() {
    if (!token || !selected) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.analyzeResume(selected.id, token);
      setAnalysis(result);
      setSuccess("Analysis complete.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis is temporarily unavailable.");
    } finally {
      setBusy(false);
    }
  }

  async function runEnhance() {
    if (!token || !selected) return;
    const role = targetRole.trim();
    const isTailor = role.length > 0;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await api.enhanceResume(selected.id, { targetRole: role }, token);
      setDraft({ ...result, changes: result.changes ?? [] });
      setAccepted(
        (result.changes ?? []).reduce<Record<string, boolean>>((acc, c) => {
          acc[c.section] = true;
          return acc;
        }, {})
      );
      setSuccess(
        isTailor
          ? `Tailoring draft ready for review (${result.quota_remaining ?? 0} left this month).`
          : `Enhancement draft ready for review (${result.quota_remaining ?? 0} left this month).`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enhancement is temporarily unavailable. Your resume is safe.");
    } finally {
      setBusy(false);
    }
  }

  async function saveVersion() {
    if (!token || !selected || !draft) return;
    const changes = draft.changes.filter((c) => accepted[c.section]);
    if (changes.length === 0) {
      setError("Select at least one change to save.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.saveResumeVersion(
        selected.id,
        { version_label: draft.version_label, changes },
        token
      );
      setSuccess(`Saved new version “${draft.version_label}”. The original resume is unchanged.`);
      setDraft(null);
      setAccepted({});
      void refreshVersions(token, selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this version.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteVersion(version: ResumeVersionRecord) {
    if (!token || !selected) return;
    setError("");
    try {
      await api.deleteResumeVersion(selected.id, version.id, token);
      setSuccess("Version archived. Versions used by applications are preserved.");
      void refreshVersions(token, selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this version.");
    }
  }

  const rawUrl = selected ? `${API_BASE}/resumes/${selected.id}/raw` : "";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Resume"
        subtitle="Upload a PDF or DOCX. Your original is immutable — enhancements become new versions."
      />

      {error && <Alert>{error}</Alert>}
      {success && <Alert tone="success">{success}</Alert>}

      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleUpload} className="space-y-4">
            <label
              htmlFor="resume-file"
              className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-600 p-8 text-center cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/50 dark:hover:bg-indigo-900/10 transition-colors"
            >
              <UploadIcon className="h-8 w-8 text-slate-400 mb-2" aria-hidden="true" />
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                {file ? file.name : "Choose a PDF or DOCX file"}
              </span>
              <span className="text-xs text-slate-400 mt-1">Max 10 MB</span>
              <input
                id="resume-file"
                type="file"
                accept=".pdf,.docx"
                className="sr-only"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <div className="flex justify-end">
              <Button type="submit" disabled={!file} loading={uploading}>
                Upload resume
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {resumes.length > 0 && (
        <div className="grid lg:grid-cols-[280px_1fr] gap-6">
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white uppercase tracking-wide">
              Your resumes
            </h2>
            {resumes.map((resume) => (
              <button
                key={resume.id}
                type="button"
                onClick={() => token && selectResume(resume, token)}
                className={`w-full text-left rounded-lg border p-3 transition-colors ${
                  selected?.id === resume.id
                    ? "border-indigo-600 bg-indigo-50 dark:bg-indigo-900/20"
                    : "border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600"
                }`}
              >
                <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                  {resume.original_filename}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {resume.parse_status === "parsed" ? "Parsed" : resume.parse_status}
                  {resume.parsed_data && Object.keys(resume.parsed_data).length > 0
                    ? " · structured data ready"
                    : ""}
                </p>
              </button>
            ))}
          </div>

          {selected && (
            <div className="space-y-5">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                    {selected.original_filename}
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Original file — never modified
                  </p>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button variant="outline" size="sm" onClick={runParse} loading={busy}>
                    Parse
                  </Button>
                  <Button variant="outline" size="sm" onClick={runAnalyze} loading={busy}>
                    Analyze
                  </Button>
                  {rawUrl && (
                    <a
                      href={rawUrl}
                      download
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                    >
                      <DownloadIcon className="h-4 w-4" aria-hidden="true" /> Download
                    </a>
                  )}
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                  Enhance or tailor for a role
                </h4>
                <div className="flex gap-2 flex-wrap">
                  <div className="min-w-52 flex-1">
                    <Input
                      value={targetRole}
                      onChange={(e) => setTargetRole(e.target.value)}
                      placeholder="e.g. Senior Backend Engineer (blank = general enhance)"
                    />
                  </div>
                  <Button onClick={runEnhance} loading={busy} disabled={busy}>
                    {targetRole.trim() ? "Tailor for role" : "Enhance wording"}
                  </Button>
                </div>
              </div>

              {analysis && (
                <Card>
                  <CardContent className="p-5 space-y-3">
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                      Analysis — {analysis.overall.replace("_", " ")}
                    </h4>
                    {analysis.findings.map((finding) => (
                      <div key={finding.category} className="text-sm">
                        <p className="font-medium text-slate-800 dark:text-slate-200">
                          {finding.category}:{" "}
                          <span
                            className={
                              finding.status === "good" ? "text-emerald-600" : "text-amber-600"
                            }
                          >
                            {finding.status.replace("_", " ")}
                          </span>
                        </p>
                        <p className="text-slate-600 dark:text-slate-400">{finding.message}</p>
                        {finding.suggestion && (
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            Suggestion: {finding.suggestion}
                          </p>
                        )}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {draft && draft.changes.length > 0 && (
                <Card>
                  <CardContent className="p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                        Review changes — {draft.version_label}
                      </h4>
                      <Button size="sm" onClick={saveVersion} loading={busy}>
                        Save new version
                      </Button>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      AI only rephrases existing facts. Review each section; nothing is saved
                      until you confirm.
                    </p>
                    {draft.changes.map((change: ChangeItem) => (
                      <div key={change.section} className="border border-slate-200 dark:border-slate-700 rounded-lg p-3">
                        <label className="flex items-center justify-between gap-2 mb-2">
                          <span className="text-sm font-medium text-slate-800 dark:text-slate-200 capitalize">
                            {change.section}
                          </span>
                          <input
                            type="checkbox"
                            checked={accepted[change.section] ?? false}
                            onChange={(e) =>
                              setAccepted((prev) => ({ ...prev, [change.section]: e.target.checked }))
                            }
                            className="rounded border-slate-300 text-indigo-600"
                          />
                        </label>
                        <div className="grid sm:grid-cols-2 gap-3 text-sm">
                          <div>
                            <p className="text-xs text-slate-400 uppercase">Original</p>
                            <p className="whitespace-pre-wrap text-slate-600 dark:text-slate-400">
                              {change.original || "(empty section)"}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-slate-400 uppercase">Enhanced</p>
                            <p className="whitespace-pre-wrap text-slate-800 dark:text-slate-200">
                              {change.enhanced}
                            </p>
                          </div>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                          {change.reason}
                        </p>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {versions.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                    Versions
                  </h4>
                  {versions.map((version) => (
                    <div
                      key={version.id}
                      className="flex items-center justify-between gap-2 border border-slate-200 dark:border-slate-700 rounded-lg p-3"
                    >
                      <div className="flex items-center gap-2">
                        <CheckCircleIcon className="h-4 w-4 text-emerald-500" aria-hidden="true" />
                        <div>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">
                            {version.version_label}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            v{version.version_number} ·{" "}
                            {version.target_opportunity_id ? "tailored" : "enhanced"}
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => deleteVersion(version)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                        aria-label={`Delete version ${version.version_label}`}
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}