// Mirrors backend/app/models.py (Proof Tree payload). Keep in sync by hand.

export type Status = "Verified" | "Refuted" | "Unresolved";

export type PassageState =
  | "active"
  | "filtered_expired"
  | "filtered_inapplicable"
  | "filtered_not_approved"
  | "filtered_hash_mismatch";

export type FailureType =
  | "overlooked_exception"
  | "conflicting_documents"
  | "outdated_or_inapplicable"
  | "unsupported_assumption";

export interface Condition {
  field: string;
  op: string;
  value: unknown;
}

export interface ConditionResult {
  field: string;
  op: string;
  expected: unknown;
  actual: unknown;
  result: "pass" | "fail" | "missing";
  passage_id: string | null;
}

export interface Evidence {
  passage_id: string;
  role: "supports" | "challenges";
  label: "entails" | "contradicts" | "neutral";
  score: number;
  counter_query: string | null;
  effect: string | null;
  trigger_conditions: ConditionResult[];
}

export interface Correction {
  text: string;
  passage_id: string;
  source: "scripted" | "derived";
}

export interface ClaimNodeData {
  id: string;
  text: string;
  status: Status;
  reason: string;
  se: number;
  sc: number;
  failure_types: FailureType[];
  cited_passage_ids: string[];
  evidence: Evidence[];
  conditions: ConditionResult[];
  missing_slots: string[];
  proposed_correction: Correction | null;
  actions: string[];
}

export interface RootData {
  id: string;
  doc_id: string;
  title: string;
  version: string;
  effective_date: string;
  expiry_date: string;
  doc_status: string;
  authority: number;
  source: { hub: string; path: string };
  supersedes: string | null;
  parent_doc_id: string | null;
  hash: string;
  hash_ok: boolean;
  state: PassageState;
  state_label: string;
  state_detail: string;
  snippet: string;
  conditions: Condition[];
  roles: string[];
}

export interface EdgeData {
  source: string;
  target: string;
  kind: "supports" | "challenges" | "cites" | "claim_of" | "parent" | "supersedes";
}

export interface MissingInput {
  field: string;
  label: string;
  type: string;
  options: string[];
}

export interface Employee {
  role: string;
  region: string;
  params: Record<string, unknown>;
}

export interface BaselineCheck {
  claim_id: string;
  passage_id: string;
  exists: boolean;
  entails: boolean;
  score: number;
}

export interface ProofTreeResult {
  scenario_id: string;
  title: string;
  demo_date: string;
  llm_mode: string;
  llm_badge: string | null;
  data_label: string;
  employee: Employee;
  question: string;
  answer: string;
  overall: { status: Status; reason: string };
  baseline: { status: Status; checks: BaselineCheck[] };
  roots: RootData[];
  trunk: { id: string; text: string; status: Status };
  claims: ClaimNodeData[];
  edges: EdgeData[];
  missing_inputs: MissingInput[];
}

export interface Meta {
  demo_date: string;
  data_label: string;
  llm_mode: string;
  llm_badge: string | null;
  roles: { code: string; label: string }[];
  regions: { code: string; label: string }[];
  scenarios: { id: string; title: string; employee: { role: string; region: string } }[];
}

export interface ScenarioDetail {
  id: string;
  title: string;
  question: string;
  ai_answer: string;
  employee: { role: string; region: string };
  citations: string[];
}
