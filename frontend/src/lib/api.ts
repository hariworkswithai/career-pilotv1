import type {
  AdminUserOverview,
  Application,
  AuditLog,
  JobPreferences,
  JobSource,
  MatchExplanation,
  MatchResult,
  NotificationItem,
  NotificationPreferences,
  OnboardingRequest,
  OpportunityFilters,
  OpportunityList,
  OpportunityRecord,
  Profile,
  RecommendationList,
  SourceTestResult,
  SuggestionItem,
} from "@/lib/opportunities/types";
import type {
  EnhancementDraft,
  ResumeAnalysis,
  ResumeParseResult,
  ResumeRecord,
  ResumeVersionRecord,
} from "@/lib/resume/types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const isConfigured = Boolean(process.env.NEXT_PUBLIC_API_URL);

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? "").filter(Boolean).join("; ");
    }
    return JSON.stringify(body);
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { token?: string | null } = {}
): Promise<T> {
  const { token, headers, ...rest } = init;
  const mergedHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string> | undefined),
  };
  if (rest.body && !(rest.body instanceof FormData)) {
    mergedHeaders["Content-Type"] = "application/json";
  }
  if (token) {
    mergedHeaders.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...rest, headers: mergedHeaders });
  } catch {
    throw new ApiError(0, "Could not reach the CareerPilot API. Is the backend running?");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

function serializeFilters(filters: OpportunityFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.roles?.length) params.set("q_roles", filters.roles.join(","));
  if (filters.cities?.length) params.set("q_cities", filters.cities.join(","));
  if (filters.work_modes?.length) params.set("work_modes", filters.work_modes.join(","));
  if (filters.experience_levels?.length)
    params.set("experience_levels", filters.experience_levels.join(","));
  if (filters.employment_types?.length)
    params.set("employment_types", filters.employment_types.join(","));
  if (filters.min_salary !== undefined) params.set("min_salary", String(filters.min_salary));
  if (filters.posted_days !== undefined) params.set("posted_days", String(filters.posted_days));
  if (filters.sort) params.set("sort", filters.sort);
  const qs = params.toString();
  return qs ? `&${qs}` : "";
}

export const api = {
  listJobs(filters: OpportunityFilters = {}, page = 1, pageSize = 20, token?: string | null) {
    return apiFetch<OpportunityList>(
      `/jobs?page=${page}&page_size=${pageSize}${serializeFilters(filters)}`,
      { token }
    );
  },

  listInternships(
    filters: OpportunityFilters = {},
    page = 1,
    pageSize = 20,
    token?: string | null
  ) {
    return apiFetch<OpportunityList>(
      `/internships?page=${page}&page_size=${pageSize}${serializeFilters(filters)}`,
      { token }
    );
  },

  getOpportunity(id: string, token?: string | null) {
    return apiFetch<OpportunityRecord>(`/opportunities/${id}`, { token });
  },

  matchOpportunity(id: string, token: string) {
    return apiFetch<MatchResult>(`/opportunities/${id}/match`, { token });
  },

  batchMatch(opportunityIds: string[], token: string) {
    return apiFetch<{ opportunity_id: string; match: MatchResult }[]>(`/match-batch`, {
      method: "POST",
      body: JSON.stringify({ opportunity_ids: opportunityIds }),
      token,
    });
  },

  listRecommendations(
    opts: { page?: number; pageSize?: number; internshipsOnly?: boolean } = {},
    token: string
  ) {
    const params = new URLSearchParams();
    params.set("page", String(opts.page ?? 1));
    params.set("page_size", String(opts.pageSize ?? 20));
    if (opts.internshipsOnly) params.set("internships_only", "true");
    return apiFetch<RecommendationList>(`/recommendations?${params.toString()}`, {
      token,
    });
  },

  explainMatch(opportunityId: string, token: string) {
    return apiFetch<MatchExplanation>(`/opportunities/${opportunityId}/match-explanation`, {
      method: "POST",
      token,
    });
  },

  suggestCities(query: string, limit = 8) {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    return apiFetch<SuggestionItem[]>(`/suggest/cities?${params.toString()}`);
  },

  listSaved(token: string) {
    return apiFetch<OpportunityRecord[]>("/saved", { token });
  },

  saveOpportunity(id: string, token: string) {
    return apiFetch<{ saved: boolean }>(`/saved/${id}`, { method: "PUT", token });
  },

  unsaveOpportunity(id: string, token: string) {
    return apiFetch<void>(`/saved/${id}`, { method: "DELETE", token });
  },

  getProfile(token: string) {
    return apiFetch<Profile>("/profile", { token });
  },

  updateProfile(profile: Partial<Profile>, token: string) {
    return apiFetch<Profile>("/profile", {
      method: "PUT",
      body: JSON.stringify(profile),
      token,
    });
  },

  getJobPreferences(token: string) {
    return apiFetch<JobPreferences>("/profile/job-preferences", { token });
  },

  updateJobPreferences(prefs: Partial<JobPreferences>, token: string) {
    return apiFetch<JobPreferences>("/profile/job-preferences", {
      method: "PUT",
      body: JSON.stringify(prefs),
      token,
    });
  },

  getNotificationPreferences(token: string) {
    return apiFetch<NotificationPreferences>("/profile/notification-preferences", {
      token,
    });
  },

  updateNotificationPreferences(prefs: Partial<NotificationPreferences>, token: string) {
    return apiFetch<NotificationPreferences>("/profile/notification-preferences", {
      method: "PUT",
      body: JSON.stringify(prefs),
      token,
    });
  },

  completeOnboarding(payload: OnboardingRequest, token: string) {
    return apiFetch<{ onboarding_completed: boolean }>("/profile/onboarding", {
      method: "POST",
      body: JSON.stringify(payload),
      token,
    });
  },

  listApplications(token: string) {
    return apiFetch<Application[]>("/applications", { token });
  },

  startApplication(opportunityId: string, token: string) {
    return apiFetch<Application>("/applications", {
      method: "POST",
      body: JSON.stringify({ opportunity_id: opportunityId }),
      token,
    });
  },

  updateApplication(
    applicationId: string,
    patch: Partial<{ status: string; notes: string }>,
    token: string
  ) {
    return apiFetch<Application>(`/applications/${applicationId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
      token,
    });
  },

  uploadResume(file: File, token: string) {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<{ id: string; parse_status: string }>("/resumes", {
      method: "POST",
      body: form,
      token,
    });
  },

  parseResume(resumeId: string, token: string) {
    return apiFetch<ResumeParseResult>(`/resumes/${resumeId}/parse`, {
      method: "POST",
      token,
    });
  },

  analyzeResume(resumeId: string, token: string) {
    return apiFetch<ResumeAnalysis>(`/resumes/${resumeId}/analyze`, {
      method: "POST",
      token,
    });
  },

  enhanceResume(
    resumeId: string,
    opts: { targetRole?: string; targetOpportunityId?: string },
    token: string
  ) {
    const params = new URLSearchParams();
    if (opts.targetRole) params.set("target_role", opts.targetRole);
    if (opts.targetOpportunityId)
      params.set("target_opportunity_id", opts.targetOpportunityId);
    const qs = params.toString();
    return apiFetch<EnhancementDraft>(
      `/resumes/${resumeId}/enhance${qs ? `?${qs}` : ""}`,
      { method: "POST", token }
    );
  },

  saveResumeVersion(
    resumeId: string,
    payload: {
      version_label?: string;
      target_opportunity_id?: string | null;
      changes: {
        section: string;
        original: string;
        enhanced: string;
        reason: string;
      }[];
    },
    token: string
  ) {
    return apiFetch<ResumeVersionRecord>(`/resumes/${resumeId}/versions`, {
      method: "POST",
      body: JSON.stringify(payload),
      token,
    });
  },

  getResumeVersions(resumeId: string, token: string) {
    return apiFetch<ResumeVersionRecord[]>(`/resumes/${resumeId}/versions`, {
      token,
    });
  },

  deleteResumeVersion(resumeId: string, versionId: string, token: string) {
    return apiFetch<{ deleted: boolean }>(
      `/resumes/${resumeId}/versions/${versionId}`,
      { method: "DELETE", token }
    );
  },

  getResumes(token: string) {
    return apiFetch<ResumeRecord[]>("/resumes", { token });
  },

  listNotifications(token: string) {
    return apiFetch<NotificationItem[]>("/notifications", { token });
  },

  markNotificationRead(id: string, token: string) {
    return apiFetch<{ read: boolean }>(`/notifications/${id}/read`, {
      method: "POST",
      token,
    });
  },

  markAllNotificationsRead(token: string) {
    return apiFetch<{ read: boolean }>("/notifications/read-all", {
      method: "POST",
      token,
    });
  },

  exportAccount(token: string) {
    return apiFetch<Record<string, unknown>>("/account/export", { token });
  },

  deleteAccount(token: string) {
    return apiFetch<{ deleted: boolean }>("/account", { method: "DELETE", token });
  },

  adminStatus(token: string) {
    return apiFetch<Record<string, number | string>>("/admin/status", { token });
  },

  adminUsers(token: string) {
    return apiFetch<AdminUserOverview[]>("/admin/users", { token });
  },

  adminSetRole(userId: string, isAdmin: boolean, token: string) {
    return apiFetch<AdminUserOverview>(`/admin/users/${userId}/role`, {
      method: "POST",
      body: JSON.stringify({ is_admin: isAdmin }),
      token,
    });
  },

  adminApplications(token: string, limit = 50) {
    return apiFetch<Application[]>(`/admin/applications?limit=${limit}`, { token });
  },

  adminAuditLogs(token: string, limit = 100) {
    return apiFetch<AuditLog[]>(`/admin/audit-logs?limit=${limit}`, { token });
  },

  adminAiUsage(token: string) {
    return apiFetch<Record<string, unknown>[]>("/admin/ai-usage", { token });
  },

  adminSources(token: string) {
    return apiFetch<JobSource[]>("/admin/sources", { token });
  },

  adminCreateSource(
    payload: { source_type: string; board_identifier: string; company_name?: string },
    token: string
  ) {
    return apiFetch<JobSource>("/admin/sources", {
      method: "POST",
      body: JSON.stringify(payload),
      token,
    });
  },

  adminUpdateSource(
    id: string,
    payload: { company_name?: string; is_active?: boolean },
    token: string
  ) {
    return apiFetch<JobSource>(`/admin/sources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
      token,
    });
  },

  adminTestSource(id: string, token: string) {
    return apiFetch<SourceTestResult>(`/admin/sources/${id}/test`, {
      method: "POST",
      token,
    });
  },

  adminTriggerSource(id: string, token: string) {
    return apiFetch<{ fetched: number; inserted: number; updated: number; errors: string[] }>(
      `/admin/sources/${id}/trigger`,
      { method: "POST", token }
    );
  },
};

export { isConfigured as isApiConfigured };