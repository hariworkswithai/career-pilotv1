export interface ChangeItem {
  section: string;
  original: string;
  enhanced: string;
  reason: string;
}

export interface EnhancementDraft {
  version_label: string;
  target_opportunity_id?: string | null;
  changes: ChangeItem[];
  quota_used?: number | null;
  quota_limit?: number | null;
  quota_remaining?: number | null;
}

export interface AnalysisFinding {
  category: string;
  status: "good" | "needs_improvement";
  message: string;
  suggestion: string;
}

export interface ResumeAnalysis {
  findings: AnalysisFinding[];
  summary: string;
  overall: string;
}

export interface ResumeEducation {
  institution: string;
  degree?: string | null;
  field?: string | null;
  start_year?: number | null;
  end_year?: number | null;
}

export interface ResumeExperience {
  company: string;
  title: string;
  location?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  is_current: boolean;
  description?: string | null;
}

export interface ResumeProject {
  name: string;
  description?: string | null;
  technologies: string[];
}

export interface ResumeParseResult {
  name: string;
  email?: string | null;
  phone?: string | null;
  summary?: string | null;
  skills: string[];
  education: ResumeEducation[];
  experience: ResumeExperience[];
  projects: ResumeProject[];
}

export interface ResumeRecord {
  id: string;
  user_id: string;
  original_filename: string;
  stored_filename: string;
  file_type: string;
  file_size: number;
  parse_status: string;
  parse_error?: string | null;
  parsed_data?: Record<string, unknown>;
  created_at?: string;
}

export interface ResumeVersionRecord {
  id: string;
  user_id: string;
  parent_resume_id: string;
  target_opportunity_id?: string | null;
  version_label: string;
  version_number: number;
  stored_filename: string;
  file_type: string;
  status: string;
  parsed_data?: Record<string, unknown>;
  enhancement_metadata?: Record<string, unknown>;
  created_at?: string;
}

export interface OnboardingResult {
  onboarding_completed: boolean;
}

export interface QuotaStatus {
  feature: string;
  used: number;
  limit: number;
  remaining: number;
}