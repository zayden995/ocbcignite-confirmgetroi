import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { askCustom, fetchMeta, fetchScenario, verify, verifyCustom } from "../api/client";
import type { Meta, MissingInput, ProofTreeResult, ScenarioDetail } from "../types";

export interface ChatTurn {
  turnId: string;
  scenarioId: string;
  scenario: ScenarioDetail & { ai_thoughts?: string | null };
  result: (ProofTreeResult & { ai_thoughts?: string | null; verification_thoughts?: string[] }) | null;
  params: Record<string, unknown>;
  suppliedInputs: MissingInput[];
  loadingAnswer?: boolean;
  loadingVerify?: boolean;
}

interface TreeState {
  meta: Meta | null;
  scenarioId: string;
  scenario: (ScenarioDetail & { ai_thoughts?: string | null }) | null;
  role: string;
  region: string;
  params: Record<string, unknown>;
  suppliedInputs: MissingInput[];
  result: (ProofTreeResult & { ai_thoughts?: string | null; verification_thoughts?: string[] }) | null;
  selectedClaimId: string | null;
  loading: boolean;
  error: string | null;
  turns: ChatTurn[];
  activeTurnId: string | null;
  selectScenario: (id: string) => void;
  askCustomQuestion: (question: string) => Promise<void>;
  setRole: (r: string) => void;
  setRegion: (r: string) => void;
  setParam: (k: string, v: unknown) => void;
  submitInputs: (values: Record<string, unknown>, defs: MissingInput[]) => Promise<void>;
  run: (overrideParams?: Record<string, unknown>) => Promise<void>;
  runForTurn: (turnId: string, overrideParams?: Record<string, unknown>) => Promise<void>;
  setActiveTurnId: (turnId: string) => void;
  clearChat: () => void;
  selectClaim: (id: string | null) => void;
}

const Ctx = createContext<TreeState | null>(null);

export function TreeProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [role, setRoleState] = useState<string>("RM");
  const [region, setRegionState] = useState<string>("SG");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Refs to prevent stale closures during async calls
  const turnsRef = useRef<ChatTurn[]>(turns);
  turnsRef.current = turns;
  const roleRef = useRef<string>(role);
  roleRef.current = role;
  const regionRef = useRef<string>(region);
  regionRef.current = region;

  useEffect(() => {
    fetchMeta()
      .then((m) => {
        setMeta(m);
        if (m.scenarios.length > 0) {
          const first = m.scenarios[0];
          setRoleState(first.employee.role);
          setRegionState(first.employee.region);
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const activeTurn = useMemo<ChatTurn | null>(() => {
    if (turns.length === 0) return null;
    return turns.find((t) => t.turnId === activeTurnId) ?? turns[turns.length - 1];
  }, [turns, activeTurnId]);

  const selectScenario = useCallback((id: string) => {
    if (id === "custom") return;
    setError(null);
    setSelectedClaimId(null);

    const newTurnId = `turn-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setLoading(true);

    fetchScenario(id)
      .then((s) => {
        setRoleState(s.employee.role);
        setRegionState(s.employee.region);
        roleRef.current = s.employee.role;
        regionRef.current = s.employee.region;

        const defaultThoughts = [
          `1. Parsed employee query (${s.employee.role} in ${s.employee.region}): "${s.question}"`,
          `2. Retrieved primary policy passage(s): ${s.citations.join(", ") || "Corpus lookup"}.`,
          `3. Formulated direct response citing [${s.citations.join(", ")}].`,
        ].join("\n");

        const newTurn: ChatTurn = {
          turnId: newTurnId,
          scenarioId: id,
          scenario: { ...s, ai_thoughts: defaultThoughts },
          result: null,
          params: {},
          suppliedInputs: [],
          loadingAnswer: false,
          loadingVerify: false,
        };
        setTurns((prev) => [...prev, newTurn]);
        setActiveTurnId(newTurnId);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  const askCustomQuestion = useCallback(async (question: string) => {
    setError(null);
    setSelectedClaimId(null);

    const currentRole = roleRef.current;
    const currentRegion = regionRef.current;
    const newTurnId = `turn-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

    const placeholderScenario: ScenarioDetail & { ai_thoughts?: string | null } = {
      id: "custom",
      title: "Custom question",
      question,
      ai_answer: "Generating answer…",
      ai_thoughts: "Thinking and searching policy corpus…",
      employee: { role: currentRole, region: currentRegion },
      citations: [],
    };

    const placeholderTurn: ChatTurn = {
      turnId: newTurnId,
      scenarioId: "custom",
      scenario: placeholderScenario,
      result: null,
      params: {},
      suppliedInputs: [],
      loadingAnswer: true,
      loadingVerify: false,
    };

    const historyPayload = turnsRef.current
      .filter((t) => !t.loadingAnswer && t.scenario.ai_answer)
      .map((t) => ({
        question: t.scenario.question,
        ai_answer: t.scenario.ai_answer,
      }));

    setTurns((prev) => [...prev, placeholderTurn]);
    setActiveTurnId(newTurnId);
    setLoading(true);

    try {
      const s = await askCustom({
        question,
        role: currentRole,
        region: currentRegion,
        ...(historyPayload.length > 0 ? { history: historyPayload } : {}),
      } as Parameters<typeof askCustom>[0]);

      const fallbackThoughts = [
        `1. Analysed employee question for role=${currentRole}, region=${currentRegion}.`,
        `2. Checked prior conversation context (${historyPayload.length} previous turn(s)).`,
        `3. Synthesised answer from active synthetic banking policy clauses.`,
      ].join("\n");

      const enrichedScenario = {
        ...s,
        ai_thoughts:
          (s as ScenarioDetail & { ai_thoughts?: string | null }).ai_thoughts ||
          fallbackThoughts,
      };

      setTurns((prev) =>
        prev.map((t) =>
          t.turnId === newTurnId
            ? { ...t, scenario: enrichedScenario, loadingAnswer: false }
            : t
        )
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setTurns((prev) => prev.filter((t) => t.turnId !== newTurnId));
    } finally {
      setLoading(false);
    }
  }, []);

  const runForTurn = useCallback(
    async (
      turnId: string,
      overrideParams?: Record<string, unknown>,
      overrideSupplied?: MissingInput[]
    ) => {
      const target = turnsRef.current.find((t) => t.turnId === turnId);
      if (!target || target.loadingAnswer) return;

      const currentRole = roleRef.current;
      const currentRegion = regionRef.current;

      setActiveTurnId(turnId);
      setSelectedClaimId(null);
      setError(null);
      setLoading(true);

      const effectiveParams = overrideParams ?? target.params;

      setTurns((prev) =>
        prev.map((t) =>
          t.turnId === turnId
            ? {
                ...t,
                params: effectiveParams,
                suppliedInputs: overrideSupplied ?? t.suppliedInputs,
                loadingVerify: true,
              }
            : t
        )
      );

      try {
        let res: ProofTreeResult & {
          ai_thoughts?: string | null;
          verification_thoughts?: string[];
        };

        if (target.scenarioId === "custom") {
          res = await verifyCustom({
            question: target.scenario.question,
            ai_answer: target.scenario.ai_answer,
            role: currentRole,
            region: currentRegion,
            params: effectiveParams,
          });
        } else {
          res = await verify({
            scenario_id: target.scenarioId,
            role: currentRole,
            region: currentRegion,
            params: effectiveParams,
          });
        }

        const computedVerificationThoughts =
          res.verification_thoughts && res.verification_thoughts.length > 0
            ? res.verification_thoughts
            : [
                `[EXTRACT] Trunk conclusion: "${res.trunk.text}" (${res.claims.length} atomic claim(s)).`,
                ...res.claims.flatMap((c) => {
                  const sup = c.evidence
                    .filter((e) => e.role === "supports")
                    .map((e) => e.passage_id);
                  const chal = c.evidence
                    .filter((e) => e.role === "challenges")
                    .map(
                      (e) =>
                        `${e.passage_id}${e.counter_query ? ` via "${e.counter_query}"` : ""}`
                    );
                  return [
                    `[INVESTIGATE ${c.id}] Supporting passages: ${sup.length ? sup.join(", ") : "None"} | Missing inputs: ${c.missing_slots.length ? c.missing_slots.join(", ") : "None"}`,
                    `[CHALLENGE ${c.id}] Counter-queries run: ${c.trace.challenge.length} | Contradictions found: ${chal.length ? chal.join(", ") : "None"}`,
                    `[VERIFY ${c.id}] SE=${c.se.toFixed(2)}, SC=${c.sc.toFixed(2)} -> ${c.status}: ${c.reason}`,
                  ];
                }),
              ];

        const enrichedResult = {
          ...res,
          ai_thoughts: res.ai_thoughts ?? target.scenario.ai_thoughts ?? null,
          verification_thoughts: computedVerificationThoughts,
        };

        setTurns((prev) =>
          prev.map((t) =>
            t.turnId === turnId
              ? { ...t, result: enrichedResult, loadingVerify: false }
              : t
          )
        );
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
        setTurns((prev) =>
          prev.map((t) => (t.turnId === turnId ? { ...t, loadingVerify: false } : t))
        );
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const run = useCallback(
    async (overrideParams?: Record<string, unknown>) => {
      const currentActive =
        turnsRef.current.find((t) => t.turnId === activeTurnId) ??
        turnsRef.current[turnsRef.current.length - 1];
      if (!currentActive) return;
      await runForTurn(currentActive.turnId, overrideParams);
    },
    [activeTurnId, runForTurn]
  );

  const submitInputs = useCallback(
    async (values: Record<string, unknown>, defs: MissingInput[]) => {
      const currentActive =
        turnsRef.current.find((t) => t.turnId === activeTurnId) ??
        turnsRef.current[turnsRef.current.length - 1];
      if (!currentActive) return;
      const merged = { ...currentActive.params, ...values };
      const mergedDefs = [
        ...currentActive.suppliedInputs.filter(
          (d) => !defs.some((n) => n.field === d.field)
        ),
        ...defs,
      ];
      await runForTurn(currentActive.turnId, merged, mergedDefs);
    },
    [activeTurnId, runForTurn]
  );

  const setParam = useCallback(
    (k: string, v: unknown) => {
      if (!activeTurn) return;
      setTurns((prev) =>
        prev.map((t) =>
          t.turnId === activeTurn.turnId
            ? { ...t, params: { ...t.params, [k]: v } }
            : t
        )
      );
    },
    [activeTurn]
  );

  const setRole = useCallback((r: string) => {
    setRoleState(r);
    roleRef.current = r;
  }, []);

  const setRegion = useCallback((r: string) => {
    setRegionState(r);
    regionRef.current = r;
  }, []);

  const clearChat = useCallback(() => {
    setTurns([]);
    setActiveTurnId(null);
    setSelectedClaimId(null);
    setError(null);
  }, []);

  const value: TreeState = {
    meta,
    scenarioId: activeTurn?.scenarioId ?? (meta?.scenarios[0]?.id || "s1"),
    scenario: activeTurn?.scenario ?? null,
    role,
    region,
    params: activeTurn?.params ?? {},
    suppliedInputs: activeTurn?.suppliedInputs ?? [],
    result: activeTurn?.result ?? null,
    selectedClaimId,
    loading,
    error,
    turns,
    activeTurnId: activeTurn?.turnId ?? null,
    selectScenario,
    askCustomQuestion,
    setRole,
    setRegion,
    setParam,
    submitInputs,
    run,
    runForTurn,
    setActiveTurnId,
    clearChat,
    selectClaim: setSelectedClaimId,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTree(): TreeState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTree must be used inside TreeProvider");
  return ctx;
}