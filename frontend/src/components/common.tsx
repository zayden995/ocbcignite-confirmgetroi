import type { FailureType, PassageState, Status } from "../types";

export const STATUS_CLASS: Record<Status, string> = {
  Verified: "ok",
  Refuted: "bad",
  Unresolved: "warn",
};

// Text + symbol as well as colour, so status never relies on colour alone.
const STATUS_ICON: Record<Status, string> = { Verified: "✔", Refuted: "✖", Unresolved: "?" };

export function StatusBadge({ status, big }: { status: Status; big?: boolean }) {
  return (
    <span className={`badge ${STATUS_CLASS[status]}${big ? " big" : ""}`}>
      {STATUS_ICON[status]} {status}
    </span>
  );
}

export function StatePill({ state, label }: { state: PassageState; label: string }) {
  const cls = state === "active" ? "ok" : state === "filtered_not_approved" ? "bad" : "muted";
  return <span className={`pill ${cls}`}>{label}</span>;
}

export const FAILURE_LABELS: Record<FailureType, string> = {
  overlooked_exception: "Overlooked exception",
  conflicting_documents: "Conflicting documents",
  outdated_or_inapplicable: "Outdated or inapplicable",
  unsupported_assumption: "Unsupported assumption",
};

export function FailureChips({ types }: { types: FailureType[] }) {
  if (!types.length) return null;
  return (
    <div className="chips">
      {types.map((t) => (
        <span key={t} className="chip failure">
          {FAILURE_LABELS[t]}
        </span>
      ))}
    </div>
  );
}

export const shortHash = (h: string) => `${h.slice(0, 8)}…${h.slice(-4)}`;

export const fmtValue = (v: unknown) => (Array.isArray(v) ? `[${v.join(", ")}]` : String(v));
