import type { Assessment, AssessmentRequest, Attempt, Mode } from "../assessment/types";
import type { AdminConfig, AdminCorpus, Meta, ProofTreeResult, ScenarioDetail, SummaryResult } from "../types";

async function request<T>(url: string, init?: RequestInit, record?: (entries: Attempt[]) => void): Promise<T> {
  const res = await fetch(url, init);
  const receipts = res.headers.get("X-Tree-Attempts");
  if (receipts && record) record(JSON.parse(receipts));
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const problem = (await res.json()).detail;
      if (typeof problem === "string") detail = problem;
      if (Array.isArray(problem)) detail = problem.map(item => [item.loc?.join("."), item.msg].filter(Boolean).join(" · ")).join(", ");
    } catch {
      // body was not JSON; keep the status text
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const fetchMeta = () => request<Meta>("/api/meta");

export const fetchScenario = (id: string) => request<ScenarioDetail>(`/api/scenarios/${id}`);

export const fetchAdminCorpus = (role: string, region: string) =>
  request<AdminCorpus>(`/api/admin/corpus?role=${encodeURIComponent(role)}&region=${encodeURIComponent(region)}`);

export const fetchAdminConfig = () => request<AdminConfig>("/api/admin/config");

export const fetchSummary = () => request<SummaryResult>("/api/summary");

export const verify = (body: {
  scenario_id: string;
  role: string;
  region: string;
  params: Record<string, unknown>;
}) =>
  request<ProofTreeResult>("/api/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export const askCustom = (body: {
  turn_id: string;
  question: string;
  role: string;
  region: string;
  history?: Array<{ question: string; ai_answer: string }>;
}, record: (entries: Attempt[]) => void) =>
  request<ScenarioDetail>("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }, record);

export const verifyCustom = (body: {
  question: string;
  ai_answer: string;
  ai_thoughts?: string | null;
  role: string;
  region: string;
  params: Record<string, unknown>;
  /** Earlier turns of this conversation. The server keeps no chat history, so follow-ups need it. */
  history?: Array<{ question: string; ai_answer: string }>;
}) =>
  request<ProofTreeResult>("/api/verify-custom", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const assess = (body: AssessmentRequest, mode: Mode, record: (entries: Attempt[]) => void) =>
  request<Assessment>(`/api/v2/assess?mode=${mode}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }, record);
