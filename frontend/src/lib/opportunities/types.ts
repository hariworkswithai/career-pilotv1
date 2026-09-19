export interface NormalizedLocation {
  city?: string | null;
  state?: string | null;
  country?: string | null;
  raw: string;
  is_remote: boolean;
  remote_scope: string; // none | india | worldwide | us | canada | uk | other
}

export type EmploymentType =
  | "full_time"
  | "part_time"
  | "internship"
  | "contract"
  | "temporary";

export type ExperienceLevel = "fresher" | "entry" | "mid" | "senior" | "lead";

export type WorkplaceType = "on_site" | "hybrid" | "remote";

export type Eligibility = "eligible" | "not_eligible" | "ambiguous";

export interface OpportunityRecord {
  id: string;
  provider: string;
  external_id: string;
  source_key: string;
  title: string;
  normalized_title: string;
  company_name: string;
  location: NormalizedLocation;
  description_html: string;
  description_text: string;
  requirements_html: string;
  skills: string[];
  employment_type: EmploymentType;
  experience_level?: ExperienceLevel | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string | null;
  salary_text?: string | null;
  posted_at?: string | null;
  external_url: string;
  apply_url: string;
  apply_method: string; // careerpilot | ats | continue
  india_eligible: Eligibility;
  eligibility_reason: string;
  is_internship: boolean;
  published: boolean;
  dedup_fingerprint: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface OpportunityList {
  items: OpportunityRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface OpportunityFilters {
  q?: string;
  roles?: string[];
  cities?: string[];
  work_modes?: WorkplaceType[];
  experience_levels?: ExperienceLevel[];
  employment_types?: EmploymentType[];
  min_salary?: number;
  posted_days?: number;
  sort?: string;
}

export interface MatchBreakdown {
  skills: number;
  experience: number;
  role: number;
  location_work_mode: number;
  education: number;
}

export interface MatchResult {
  score: number;
  matched_skills: string[];
  gap_skills: string[];
  breakdown: MatchBreakdown;
  explanation: string[];
}

export interface Profile {
  user_id: string;
  full_name: string;
  headline: string;
  email?: string;
  phone?: string;
  city: string;
  state: string;
  skills: string[];
  resume_completeness: number;
  onboarding_completed?: boolean;
}

export type WorkMode = "on_site" | "hybrid" | "remote" | "any";

export interface JobPreferences {
  user_id: string;
  target_roles: string[];
  preferred_cities: string[];
  preferred_states: string[];
  work_modes: WorkMode[];
  experience_level?: ExperienceLevel | null;
  employment_types: EmploymentType[];
  salary_min?: number | null;
  salary_max?: number | null;
  remote_ok: boolean;
}

export interface OnboardingRequest {
  full_name: string;
  city: string;
  target_roles: string[];
  employment_types: EmploymentType[];
  experience_level?: ExperienceLevel | null;
  work_modes: WorkMode[];
  preferred_cities: string[];
  anywhere_india: boolean;
  remote_only: boolean;
}

export interface Application {
  id: string;
  user_id: string;
  opportunity_id: string;
  company_snapshot: Record<string, unknown>;
  role_snapshot: Record<string, unknown>;
  status: string;
  applied_at?: string | null;
  destination: string;
  destination_url: string;
  notes: string;
}

export interface RecommendationItem {
  opportunity: OpportunityRecord;
  match: MatchResult;
  filtered_out: boolean;
  filter_reason: string;
}

export interface RecommendationList {
  items: RecommendationItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface MatchExplanation {
  opportunity_id: string;
  score: number;
  breakdown: MatchBreakdown;
  matched_skills: string[];
  gap_skills: string[];
  explanation: string[];
  ai_summary: string;
  cached: boolean;
}

export interface SuggestionItem {
  type: string;
  value: string;
  label: string;
  category: string;
}

export interface JobSource {
  id: string;
  source_type: string;
  board_identifier: string;
  company_name: string;
  is_active: boolean;
  last_synced_at?: string | null;
  last_sync_status: string;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export interface SourceTestResult {
  ok: boolean;
  message: string;
  jobs_found: number;
  source_type: string;
  board_identifier: string;
}

export interface AuditLog {
  id: string;
  actor_user_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  metadata: Record<string, unknown>;
  ip_address: string;
  user_agent: string;
  created_at: string;
}

export interface AdminUserOverview {
  user_id: string;
  full_name: string;
  is_admin: boolean;
  onboarding_completed: boolean;
  applications: number;
  resumes: number;
  saved_jobs: number;
}

export interface NotificationItem {
  id: string;
  user_id: string;
  type: string;
  title: string;
  body: string;
  read_at?: string | null;
  created_at: string;
}

export interface NotificationPreferences {
  user_id: string;
  matching_jobs: boolean;
  internships: boolean;
  application_updates: boolean;
  resume_suggestions: boolean;
}

export const EMPLOYMENT_TYPE_LABELS: Record<EmploymentType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  internship: "Internship",
  contract: "Contract",
  temporary: "Temporary",
};

export const WORKPLACE_TYPE_LABELS: Record<WorkplaceType, string> = {
  on_site: "On-site",
  hybrid: "Hybrid",
  remote: "Remote",
};

export const EXPERIENCE_LEVEL_LABELS: Record<ExperienceLevel, string> = {
  fresher: "Fresher",
  entry: "Entry level",
  mid: "Mid level",
  senior: "Senior",
  lead: "Lead",
};

export const ELIGIBILITY_LABELS: Record<Eligibility, string> = {
  eligible: "Open to India",
  not_eligible: "Not open to India",
  ambiguous: "Eligibility unclear",
};