import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchMeta, fetchScenario, verify } from "../api/client";
import type { Meta, ProofTreeResult, ScenarioDetail } from "../types";

interface TreeState {
  meta: Meta | null;
  scenarioId: string | null;
  scenario: ScenarioDetail | null;
  // employee context (simulated, no SSO)
  role: string;
  region: string;
  params: Record<string, unknown>;
  result: ProofTreeResult | null;
  loading: boolean;
  error: string | null;
  selectScenario: (id: string) => void;
  setRole: (r: string) => void;
  setRegion: (r: string) => void;
  setParam: (field: string, value: unknown) => void;
  run: () => Promise<void>;
}

const TreeContext = createContext<TreeState | null>(null);

export function TreeProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null);
  const [role, setRole] = useState("RM");
  const [region, setRegion] = useState("SG");
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<ProofTreeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectScenario = useCallback((id: string) => {
    setScenarioId(id);
    setResult(null);
    setParams({});
    setError(null);
    // the employee's role and region are kept when they switch questions: the same answer can be
    // right for one employee and wrong for another, so the profile belongs to the person, not the question
    fetchScenario(id)
      .then(setScenario)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    fetchMeta()
      .then((m) => {
        setMeta(m);
        if (m.scenarios.length) {
          selectScenario(m.scenarios[0].id);
          setRole(m.scenarios[0].employee.role);
          setRegion(m.scenarios[0].employee.region);
        }
      })
      .catch((e: Error) => setError(e.message));
  }, [selectScenario]);

  const run = useCallback(async () => {
    if (!scenarioId) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await verify({ scenario_id: scenarioId, role, region, params }));
    } catch (e) {
      setResult(null);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [scenarioId, role, region, params]);

  const value = useMemo<TreeState>(
    () => ({
      meta, scenarioId, scenario, role, region, params, result, loading, error,
      selectScenario,
      setRole: (r) => { setRole(r); setResult(null); },
      setRegion: (r) => { setRegion(r); setResult(null); },
      setParam: (field, v) => setParams((p) => ({ ...p, [field]: v })),
      run,
    }),
    [meta, scenarioId, scenario, role, region, params, result, loading, error, selectScenario, run],
  );

  return <TreeContext.Provider value={value}>{children}</TreeContext.Provider>;
}

export function useTree(): TreeState {
  const ctx = useContext(TreeContext);
  if (!ctx) throw new Error("useTree must be used inside <TreeProvider>");
  return ctx;
}
