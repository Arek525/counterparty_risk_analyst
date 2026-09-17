export type Role = "analyst" | "reviewer";
export type Risk = "Low" | "Medium" | "High" | "Unable to assess";
export type FindingStatus =
  "pass" | "fail" | "unknown" | "conflict" | "not_applicable";

export interface Meta {
  demo_mode: boolean;
  model_mode: string;
  model_name?: string;
  version?: string;
}

export interface User {
  id: string;
  organization_id?: string;
  email: string;
  role: Role;
  name: string;
  is_active?: boolean;
}

export interface DemoAccount {
  email: string;
  password: string;
  role: Role;
  name: string;
  organization?: string;
}

export type SourceLocation =
  | string
  | {
      line_start?: number;
      line_end?: number;
      page?: number;
      [key: string]: unknown;
    };

export interface Relationship {
  purpose: string;
  data_shared: string;
  system_access: string;
  business_criticality: string;
  personal_data: boolean;
  privileged_access: boolean;
}

export interface AssessmentCase {
  is_decided?: boolean;
  id: string;
  name: string;
  counterparty_name: string;
  relationship: Relationship;
  owner_id?: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: string;
  document_id?: string;
  text: string;
  location: SourceLocation;
}

export interface DocumentRecord {
  case_is_decided?: boolean;
  index_status?: "pending" | "indexing" | "ready" | "error";
  index_error?: string | null;
  index_config?: string;
  indexed_at?: string | null;
  id: string;
  case_id?: string | null;
  kind: "policy" | "evidence";
  filename: string;
  version: number;
  media_type?: string;
  evidence_type?: "declaration" | "independent" | null;
  sha256?: string;
  created_at: string;
  chunks?: DocumentChunk[];
  text?: string;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  location: SourceLocation;
  quote: string;
  evidence_type?: string;
}

export interface Requirement {
  id: string;
  title: string;
  description?: string;
  applicability_text?: string;
  field?: string;
  operator?: "eq" | "lte" | "gte" | "contains" | "present" | "manual";
  expected?: unknown;
  severity: "Low" | "Medium" | "High";
  applicability?: Record<string, unknown>;
  source: Citation;
  evaluation_method?: "deterministic" | "llm" | "manual";
}

export interface PolicyVersion {
  extraction_status?: "ready" | "extracting" | "error";
  extraction_error?: string | null;
  requirement_index_status?: "pending" | "ready" | "error";
  requirement_index_error?: string | null;
  id: string;
  name: string;
  version: number;
  status: "draft" | "approved";
  document_ids: string[];
  requirements: Requirement[];
  created_at: string;
  approved_at?: string | null;
}

export interface Finding {
  requirement_description?: string;
  requirement_source?: Citation;
  requirement_id: string;
  title: string;
  status: FindingStatus;
  severity: "Low" | "Medium" | "High";
  explanation: string;
  evidence: Citation[];
  missing_information?: string[] | null;
}

export interface Discrepancy {
  type: string;
  description: string;
  evidence?: Citation[];
}

export interface Report {
  recorded_example?: { captured_at: string; model_name: string; description: string };
  findings: Finding[];
  risk: Risk;
  completeness: number;
  summary: string;
  questions: string[];
  discrepancies: Discrepancy[];
  model_mode: string;
  model_name: string;
  metrics: {
    input_tokens: number;
    output_tokens: number;
    cost_usd: number | null;
    duration_ms?: number;
  };
  rules_version: string;
  prompt_version: string;
  workflow_complete?: boolean;
  workflow_error?: string | null;
}

export interface Decision {
  id: string;
  decision: "accepted" | "rejected" | "needs_information";
  rationale: string;
  actor_id?: string;
  created_at: string;
}

export interface AnalysisRun {
  retry_blocked_reason?: string | null;
  case_is_decided?: boolean;
  progress?: { completed: number; total: number; current_requirement_id: string | null; error?: string | null };
  id: string;
  case_id: string;
  policy_version_id: string;
  status: "queued" | "running" | "awaiting_review" | "completed" | "failed";
  retrieval_variant: "lexical" | "hybrid" | "semantic";
  model_mode: string;
  error?: string | null;
  report?: Report | null;
  events?: AuditEvent[];
  decision?: Decision | null;
  information_request_draft?: { text: string; actor_id: string; actor_email: string | null; updated_at: string } | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface AuditEvent {
  id: string;
  event: string;
  actor_id?: string | null;
  actor_name?: string | null;
  actor_email?: string | null;
  case_id?: string | null;
  run_id?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}
