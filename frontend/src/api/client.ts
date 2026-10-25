import type { AdminConfig, AdminCorpus, Meta, ProofTreeResult, ScenarioDetail, SummaryResult } from "../types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
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
