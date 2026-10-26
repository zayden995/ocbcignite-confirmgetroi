import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchMeta, fetchScenario, verify } from "../api/client";
import type { Meta, MissingInput, ProofTreeResult, ScenarioDetail } from "../types";

interface TreeState {
  meta: Meta | null;
  scenarioId: string | null;
  scenario: ScenarioDetail | null;
  // employee context (simulated, no SSO)
  role: string;
  region: string;
  params: Record<string, unknown>;
  /** the missing inputs the employee has already reported for this question (so their labels survive the re-run) */
  suppliedInputs: MissingInput[];
  result: ProofTreeResult | null;
  loading: boolean;
  error: string | null;
  selectScenario: (id: string) => void;
  setRole: (r: string) => void;
  setRegion: (r: string) => void;
  setParam: (field: string, value: unknown) => void;
  run: () => Promise<void>;
  /** Re-run TREE with inputs the employee reported. Resolves to an error message, or null on success. */
  rerun: (supplied: Record<string, unknown>, defs: MissingInput[]) => Promise<string | null>;
}

const TreeContext = createContext<TreeState | null>(null);

export function TreeProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null);
  const [role, setRole] = useState("RM");
  const [region, setRegion] = useState("SG");
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [suppliedInputs, setSuppliedInputs] = useState<MissingInput[]>([]);
  const [result, setResult] = useState<ProofTreeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectScenario = useCallback((id: string) => {
    setScenarioId(id);
    setResult(null);
    setParams({});
    setSuppliedInputs([]);
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

  // The values go straight into the request: calling setParams and then run() in one tick would send the old ones.
  // A failed re-run leaves the current verdict on screen and hands the message back to the form.
  const rerun = useCallback(
    async (supplied: Record<string, unknown>, defs: MissingInput[]) => {
      if (!scenarioId) return "No question is selected.";
      const merged = { ...params, ...supplied };
      setLoading(true);
      try {
        const next = await verify({ scenario_id: scenarioId, role, region, params: merged });
        setParams(merged);
        setSuppliedInputs((prev) => [...prev.filter((p) => !defs.some((d) => d.field === p.field)), ...defs]);
        setResult(next);
        return null;
      } catch (e) {
        return (e as Error).message;
      } finally {
        setLoading(false);
      }
    },
    [scenarioId, role, region, params],
  );

  const value = useMemo<TreeState>(
    () => ({
      meta, scenarioId, scenario, role, region, params, suppliedInputs, result, loading, error,
      selectScenario,
      setRole: (r) => { setRole(r); setResult(null); },
      setRegion: (r) => { setRegion(r); setResult(null); },
      setParam: (field, v) => setParams((p) => ({ ...p, [field]: v })),
      run,
      rerun,
    }),
    [meta, scenarioId, scenario, role, region, params, suppliedInputs, result, loading, error, selectScenario, run, rerun],
  );

  return <TreeContext.Provider value={value}>{children}</TreeContext.Provider>;
}

export function useTree(): TreeState {
  const ctx = useContext(TreeContext);
  if (!ctx) throw new Error("useTree must be used inside <TreeProvider>");
  return ctx;
}
