import { useCallback, useRef, useState } from "react";
import { assess } from "../api/client";
import type { AssessmentRequest, Attempt, Mode, Revision } from "./types";

interface Journey {
  draft: AssessmentRequest;
  mode: Mode;
  pending: string | null;
  error: string | null;
  revisions: Revision[];
  selected: string | null;
}

export function useAssessments() {
  const [journeys, setJourneys] = useState<Record<string, Journey>>({});
  const [attempts, setAttempts] = useState<Record<string, Attempt>>({});
  const current = useRef(journeys);
  const session = useRef(0);
  const generation = session.current;
  const write = useCallback((id: string, state: Journey) => {
    current.current = { ...current.current, [id]: state };
    setJourneys(current.current);
  }, []);
  const record = useCallback((entries: Attempt[]) => {
    if (entries.length && generation === session.current) setAttempts(prev => ({...prev, ...Object.fromEntries(entries.map(a => [a.id, a]))}));
  }, [generation]);
  function start(draft: AssessmentRequest, mode: Mode) {
    write(draft.turn_id, { draft, mode, revisions: [], selected: null, error: null, pending: null });
  }
  function edit(id: string, patch: Partial<AssessmentRequest>) {
    const j = current.current[id];
    if (!j) return;
    // All keystrokes before the next check are one draft revision.
    const checked = j.pending || j.error || j.revisions.some(r => r.request.input_revision === j.draft.input_revision);
    const revision = j.draft.input_revision + (checked ? 1 : 0);
    const confirmation = patch.confirmation === undefined && !("question" in patch || "employee" in patch || "bundle_id" in patch)
      ? j.draft.confirmation : patch.confirmation;
    write(id, {...j, draft: {...j.draft, ...patch, input_revision: revision,
      confirmation: confirmation ? {...confirmation, input_revision: revision} : null},
      pending: null, error: null, selected: null});
  }
  function profile(employee: AssessmentRequest["employee"]) {
    for (const [id, j] of Object.entries(current.current)) {
      if (employee.role !== j.draft.employee.role || employee.region !== j.draft.employee.region) edit(id, {employee});
    }
  }
  async function run(id: string) {
    const j = current.current[id];
    if (!j || j.pending) return;
    const token = crypto.randomUUID();
    write(id, {...j, pending: token, error: null, selected: null});
    try {
      const result = await assess(j.draft, j.mode, record);
      if (current.current[id]?.pending !== token) return;
      if (result.turn_id !== id || result.input_revision !== j.draft.input_revision || result.bundle_id !== j.draft.bundle_id)
        throw new Error("Response belongs to another assessment revision.");
      write(id, {...j, pending: null, error: null, revisions: [...j.revisions, {request: j.draft, result}], selected: result.assessment_id});
    } catch (error) {
      if (current.current[id]?.pending === token)
        write(id, {...j, pending: null, selected: null, error: error instanceof Error ? error.message : String(error)});
    }
  }
  function select(id: string, selected: string) {
    const j = current.current[id];
    if (j) write(id, {...j, selected});
  }
  function clear() {
    session.current++;
    current.current = {};
    setJourneys({});
    setAttempts({});
  }
  return { journeys, attempts, record, start, edit, profile, run, select, clear };
}
