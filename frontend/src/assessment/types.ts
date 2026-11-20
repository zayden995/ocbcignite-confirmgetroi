export type Task = "rate_only" | "plan_and_rate";
export type Decision = "deposit_rate" | "single_transfer";
export type Mode = "fixture" | "live";
export interface Span { start: number; end: number; quote: string }
export const factLabels = {
  product: "Product", currency: "Currency", booking_region: "Booking region", segment: "Customer segment",
  channel: "Funding channel", tenor_months: "Tenor (months)", deposit_cents: "Deposit amount (SGD)",
  transfer_cents: "Amount in this single transfer (SGD)",
};
export type FactKey = keyof typeof factLabels;
export interface Fact {
  key: FactKey; value: string | number; origin: { kind: "fixture" | "form" | "employee_text"; ref: string; span?: Span };
}
export interface AssessmentRequest {
  schema_version: "2"; turn_id: string; input_revision: number; bundle_id: string; as_of: string;
  employee: { role: string; region: string }; question: string; answer: string;
  history: { turn_id: string; question: string; answer: string }[];
  facts: Fact[];
  confirmation: { choice: Task | "other"; input_revision: number } | null;
}
export interface Branch {
  decision_id: Decision; status: "covered" | "wrong" | "omitted" | "need_fact" | "policy_review" | "uncertain_text";
  expected: {rate_bps: number} | {limit_cents: number; within_cap: boolean} | null;
  spans: Span[]; source_ids: string[]; fact_keys: FactKey[]; explanation: string;
}
export interface Assessment {
  assessment_id: string; turn_id: string; input_revision: number; bundle_id: string; snapshot_id: string; mode: Mode;
  task_id: Task | null; verdict: "ready" | "hold"; coverage: {covered: number; required: number}; branches: Branch[];
  roots: {passage_id: string; version: string; state: string; reason: string; text: string}[];
  extras: {span: Span; status: string; explanation: string; source_ids: string[]}[];
  next: {kind: string; fields: FactKey[]; prompt: string}; repair: {text: string; source_ids: string[]} | null;
}
export interface Revision { request: AssessmentRequest; result: Assessment }
export interface Attempt {
  id: string; turn_id: string; revision: number; purpose: "generation" | "verification"; model: string;
  success: boolean; usage: Record<string, number | null> | null; elapsed_ms: number; estimate: string | null;
  currency: string; pricing_date: string;
}
export const tasks = {rate_only: "Quote the standard rate", plan_and_rate: "Quote the rate and check one FAST transfer"};
export const decisions = {deposit_rate: "Standard annual rate", single_transfer: "Single FAST transfer"};
export const rateQuestion = "What standard annual rate should I quote for this qualifying FAST-funded placement?";
export const coverage = (r: Assessment) => r.coverage.required ? `${r.coverage.covered}/${r.coverage.required}` : "Coverage unavailable";
