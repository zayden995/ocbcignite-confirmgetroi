import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent, type SVGProps } from "react";
import type { ClaimNodeData, ProofTreeResult, RootData } from "../../types";
import { FailureChips, StatePill, StatusBadge, STATUS_CLASS, fmtValue, shortHash } from "../common";
import { BARK, STATUS_PALETTE, layoutTree, linkPath, type BranchGeo, type Leaf, type RootGeo } from "./treeGeometry";

type Hover = { kind: "claim" | "root" | "trunk"; id: string; x: number; y: number } | null;

const ICON = {
  doc: "M7 3h7l5 5v13H7z M14 3v5h5 M10 13h6 M10 17h6",
  shield: "M12 3l7 3v5c0 5-3 8.5-7 10-4-1.5-7-5-7-10V6z M9 12l2.2 2.2L15.5 10",
  cross: "M8 8l8 8 M16 8l-8 8",
  clock: "M12 7v5l3 2",
};

const LEAF = "M-12,0 C-7,-9 5,-9 12,0 C5,9 -7,9 -12,0 Z";

function Icon({ d, x, y, size, color, width = 2 }: { d: string; x: number; y: number; size: number; color: string; width?: number }) {
  const s = size / 24;
  return (
    <path d={d} transform={`translate(${x - size / 2},${y - size / 2}) scale(${s})`} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" />
  );
}

function Leaves({ leaves, colors }: { leaves: Leaf[]; colors: string[] }) {
  return (
    <>
      {leaves.map((l, i) => (
        <path key={i} d={LEAF} fill={colors[l.shade]} transform={`translate(${l.x.toFixed(1)},${l.y.toFixed(1)}) rotate(${l.rot.toFixed(0)}) scale(${l.s.toFixed(2)})`} opacity={0.95} />
      ))}
    </>
  );
}

export function TreeIllustration({
  result, selectedId, onSelectClaim,
}: {
  result: ProofTreeResult;
  selectedId: string | null;
  onSelectClaim: (id: string) => void;
}) {
  const layout = useMemo(() => layoutTree(result), [result]);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover>(null);
  const mock = result.llm_badge !== null;

  const at = (e: PointerEvent | { clientX: number; clientY: number }) => {
    const r = wrapRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const hoverProps = (kind: "claim" | "root" | "trunk", id: string) => ({
    onPointerEnter: (e: PointerEvent) => setHover({ kind, id, ...at(e) }),
    onPointerMove: (e: PointerEvent) => setHover({ kind, id, ...at(e) }),
    onPointerLeave: () => setHover(null),
    onFocus: (e: { currentTarget: Element }) => {
      const b = e.currentTarget.getBoundingClientRect();
      setHover({ kind, id, ...at({ clientX: b.left + b.width / 2, clientY: b.top + b.height }) });
    },
    onBlur: () => setHover(null),
  });
  const activate = (id: string) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelectClaim(id);
    }
  };

  // which claims/roots are connected to what is hovered or selected (for dimming and sap lines)
  const focusClaim = hover?.kind === "claim" ? hover.id : selectedId;
  const focusRoot = hover?.kind === "root" ? hover.id : null;
  const links = result.edges.filter(
    (e) =>
      (e.kind === "supports" || e.kind === "challenges" || e.kind === "cites") &&
      (e.target === focusClaim || (focusRoot !== null && e.source === focusRoot)),
  );
  const linkedClaims = new Set(links.map((l) => l.target));
  const linkedRoots = new Set(links.map((l) => l.source));
  const anyFocus = focusClaim !== null || focusRoot !== null;
  const claimDim = (id: string) => anyFocus && !linkedClaims.has(id) && id !== focusClaim;
  const rootDim = (id: string) => anyFocus && !linkedRoots.has(id) && id !== focusRoot;

  const rootById = new Map(layout.roots.map((g) => [g.root.id, g]));
  const branchById = new Map(layout.branches.map((b) => [b.claim.id, b]));

  return (
    <div className="tree-wrap" ref={wrapRef}>
      <svg viewBox={`0 0 ${layout.W} ${layout.H}`} role="img" aria-label={`Proof Tree. Overall ${result.overall.status}.`}>
        <defs>
          <linearGradient id="bark" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#5C4029" />
            <stop offset="0.45" stopColor="#8A6844" />
            <stop offset="1" stopColor="#5F432B" />
          </linearGradient>
          <radialGradient id="ground" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#DCE6DC" stopOpacity="0.9" />
            <stop offset="1" stopColor="#DCE6DC" stopOpacity="0" />
          </radialGradient>
          {layout.branches.map((b) => (
            <linearGradient key={b.claim.id} id={`bg-${b.claim.id}`} gradientUnits="userSpaceOnUse" {...b.grad}>
              <stop offset="0" stopColor={BARK} />
              <stop offset="0.34" stopColor={STATUS_PALETTE[b.claim.status].main} />
              <stop offset="1" stopColor={STATUS_PALETTE[b.claim.status].main} />
            </linearGradient>
          ))}
        </defs>

        <ellipse cx={layout.W / 2} cy={layout.ground + 14} rx={470} ry={34} fill="url(#ground)" />

        {/* roots: the source passages */}
        {layout.roots.map((g) => (
          <g key={g.root.id} className={rootDim(g.root.id) ? "dim" : ""}>
            <path d={g.d} fill="url(#bark)" />
            {g.threads.map((th, k) => (
              <g key={k} transform={`translate(${th.dx},0)`}>
                <path d={g.line} fill="none" stroke={th.color} strokeWidth={3} strokeDasharray={th.dash} strokeLinecap="round" />
                {g.dots.map((p, j) => (
                  <circle key={j} cx={p.x} cy={p.y} r={4.5} fill={th.color} stroke="#fff" strokeWidth={1.5} />
                ))}
              </g>
            ))}
          </g>
        ))}

        {layout.lineage.map((l, i) => (
          <g key={i}>
            <path d={l.d} fill="none" stroke="#475569" strokeWidth={2} strokeDasharray="2 5" strokeLinecap="round" />
            <text x={l.mid.x} y={l.mid.y - 30} textAnchor="middle" className="svg-note">{l.label}</text>
          </g>
        ))}

        {/* trunk: the AI conclusion */}
        <path d={layout.trunkPath} fill="url(#bark)" />
        <path d={`M${layout.W / 2 - 12},${layout.trunkTop + 12} C${layout.W / 2 - 14},${layout.trunkTop + 80} ${layout.W / 2 - 20},${layout.ground - 50} ${layout.W / 2 - 34},${layout.ground + 6}`} stroke="#4A3320" strokeWidth={2} fill="none" opacity={0.55} />
        <path d={`M${layout.W / 2 + 14},${layout.trunkTop + 20} C${layout.W / 2 + 12},${layout.trunkTop + 90} ${layout.W / 2 + 22},${layout.ground - 40} ${layout.W / 2 + 40},${layout.ground + 6}`} stroke="#4A3320" strokeWidth={2} fill="none" opacity={0.45} />

        {/* branches: one per claim, coloured by status */}
        {layout.branches.map((b) => (
          <BranchLayer key={b.claim.id} b={b} dim={claimDim(b.claim.id)} focused={b.claim.id === focusClaim} />
        ))}

        {/* sap lines: which passages feed or challenge the claim in focus */}
        {links.map((l, i) => {
          const g = rootById.get(l.source);
          const b = branchById.get(l.target);
          if (!g || !b) return null;
          const color = l.kind === "supports" ? "#2E7D32" : l.kind === "challenges" ? "#C8102E" : "#6B7280";
          const to = { x: b.center.x, y: b.center.y + layout.cardH / 2 };
          return (
            <g key={i} pointerEvents="none">
              <path d={linkPath(g.anchor, to)} fill="none" stroke="#fff" strokeWidth={7} opacity={0.85} />
              <path d={linkPath(g.anchor, to)} fill="none" stroke={color} strokeWidth={3.5} strokeDasharray={l.kind === "supports" ? undefined : "9 7"} strokeLinecap="round" />
              <circle cx={to.x} cy={to.y} r={6} fill={color} stroke="#fff" strokeWidth={2} />
            </g>
          );
        })}

        {/* root nodes */}
        {layout.roots.map((g) => (
          <RootNodeView key={g.root.id} g={g} dim={rootDim(g.root.id)} focused={g.root.id === focusRoot} {...hoverProps("root", g.root.id)} />
        ))}

        {/* claim cards */}
        {layout.branches.map((b) => (
          <foreignObject key={b.claim.id} x={b.center.x - layout.cardW / 2} y={b.center.y - layout.cardH / 2} width={layout.cardW} height={layout.cardH}>
            <div
              className={`tcard ${STATUS_CLASS[b.claim.status]}${b.claim.id === selectedId ? " selected" : ""}${claimDim(b.claim.id) ? " dim" : ""}${result.claims.length >= 4 ? " compact" : ""}`}
              role="button"
              tabIndex={0}
              aria-label={`Claim ${b.claim.id.split(".").pop()}: ${b.claim.status}. ${b.claim.text}`}
              onClick={() => onSelectClaim(b.claim.id)}
              onKeyDown={activate(b.claim.id)}
              {...hoverProps("claim", b.claim.id)}
            >
              <div className="tcard-head">
                <strong>{b.claim.id.split(".").pop()}</strong>
                <StatusBadge status={b.claim.status} />
              </div>
              <div className="tcard-text">{b.claim.text}</div>
              <div className="tcard-meta">SE {b.claim.se.toFixed(2)} · SC {b.claim.sc.toFixed(2)}</div>
            </div>
          </foreignObject>
        ))}

        {/* trunk plate */}
        <line x1={layout.W / 2 + 34} y1={layout.trunkTop + 82} x2={layout.W / 2 + 74} y2={layout.trunkTop + 82} stroke={BARK} strokeWidth={4} strokeLinecap="round" />
        <foreignObject x={layout.W / 2 + 74} y={layout.trunkTop + 30} width={262} height={106}>
          <div
            className={`tplate ${STATUS_CLASS[result.overall.status]}`}
            tabIndex={0}
            aria-label={`AI conclusion: ${result.trunk.text}. Overall ${result.overall.status}.`}
            {...hoverProps("trunk", "conclusion")}
          >
            <span className="tplate-label">AI conclusion</span>
            <span className="tplate-text">{result.trunk.text}</span>
            <StatusBadge status={result.overall.status} big />
          </div>
        </foreignObject>
      </svg>

      <div className="tree-legend">
        <span><i className="sw ok" />Verified branch</span>
        <span><i className="sw warn" />Unresolved branch</span>
        <span><i className="sw bad" />Refuted branch</span>
        <span><i className="th ok" />supports</span>
        <span><i className="th bad" />challenges</span>
        <span><i className="th muted" />filtered out</span>
      </div>

      {hover && (
        <div className="tip" style={{ left: Math.min(hover.x + 16, (wrapRef.current?.clientWidth ?? 600) - 330), top: hover.y + 18 }} role="tooltip">
          <TipBody hover={hover} result={result} mock={mock} />
        </div>
      )}
    </div>
  );
}

function BranchLayer({ b, dim, focused }: { b: BranchGeo; dim: boolean; focused: boolean }) {
  const pal = STATUS_PALETTE[b.claim.status];
  return (
    <g className={dim ? "dim" : ""} pointerEvents="none">
      <path d={b.d} fill={`url(#bg-${b.claim.id})`} stroke={focused ? "#1c2430" : "none"} strokeWidth={focused ? 1.5 : 0} />
      {b.twigs.map((t, i) => (
        <g key={i}>
          <path d={t.d} fill={pal.main} />
          <Leaves leaves={t.leaves} colors={pal.leaves} />
        </g>
      ))}
      <ellipse cx={b.center.x} cy={b.center.y} rx={b.foliage.rx} ry={b.foliage.ry} fill={pal.main} opacity={0.16} />
      <Leaves leaves={b.leaves} colors={pal.leaves} />
    </g>
  );
}

function RootNodeView({ g, dim, focused, ...rest }: { g: RootGeo; dim: boolean; focused: boolean } & Omit<SVGProps<SVGGElement>, "ref">) {
  const { root } = g;
  const active = root.state === "active";
  const rejected = root.state === "filtered_not_approved" || root.state === "filtered_hash_mismatch";
  const color = active ? "#2E7D32" : rejected ? "#C8102E" : "#6B7280";
  const badgeColor = active && root.hash_ok ? "#2E7D32" : rejected ? "#C8102E" : "#6B7280";
  return (
    <g className={`rootnode${dim ? " dim" : ""}${focused ? " focused" : ""}`} tabIndex={0} aria-label={`Source ${root.id}: ${root.state_label}`} {...rest}>
      <circle cx={g.x} cy={g.y} r={g.r + 10} fill="transparent" />
      <circle cx={g.x} cy={g.y} r={g.r} fill={active ? "#fff" : rejected ? "#FFF1F2" : "#F1F5F9"} stroke={color} strokeWidth={4} strokeDasharray={active ? undefined : "7 5"} />
      <Icon d={ICON.doc} x={g.x} y={g.y} size={34} color={color} />
      <circle cx={g.x + 26} cy={g.y - 26} r={13} fill={badgeColor} stroke="#fff" strokeWidth={2.5} />
      {active && root.hash_ok ? (
        <Icon d={ICON.shield} x={g.x + 26} y={g.y - 26} size={17} color="#fff" width={2.4} />
      ) : rejected ? (
        <Icon d={ICON.cross} x={g.x + 26} y={g.y - 26} size={14} color="#fff" width={3} />
      ) : (
        <Icon d={ICON.clock} x={g.x + 26} y={g.y - 26} size={15} color="#fff" width={2.6} />
      )}
      <text x={g.x} y={g.y + g.r + 24} textAnchor="middle" className="svg-id">{root.id}</text>
      <text x={g.x} y={g.y + g.r + 44} textAnchor="middle" className={`svg-state ${active ? "ok" : rejected ? "bad" : "muted"}`}>{root.state_label}</text>
    </g>
  );
}

function TipBody({ hover, result, mock }: { hover: NonNullable<Hover>; result: ProofTreeResult; mock: boolean }) {
  if (hover.kind === "claim") {
    const c = result.claims.find((x) => x.id === hover.id);
    return c ? <ClaimTip c={c} result={result} mock={mock} /> : null;
  }
  if (hover.kind === "root") {
    const r = result.roots.find((x) => x.id === hover.id);
    return r ? <RootTip r={r} /> : null;
  }
  const baseline = result.baseline.status;
  return (
    <>
      <div className="tip-head"><StatusBadge status={result.overall.status} /> <strong>Overall answer</strong></div>
      <p>{result.overall.reason}</p>
      <p className="tip-sub">A citation-only check would have said <strong>{baseline}</strong>.</p>
    </>
  );
}

function ClaimTip({ c, result, mock }: { c: ClaimNodeData; result: ProofTreeResult; mock: boolean }) {
  const supports = c.evidence.filter((e) => e.role === "supports");
  const challenges = c.evidence.filter((e) => e.role === "challenges");
  return (
    <>
      <div className="tip-head"><StatusBadge status={c.status} /> <strong>Claim {c.id.split(".").pop()}</strong></div>
      <p>{c.text}</p>
      <div className="tip-grid">
        <span>Support (SE)</span><strong>{c.se.toFixed(2)}</strong>
        <span>Challenge (SC)</span><strong>{c.sc.toFixed(2)}</strong>
      </div>
      <p className="tip-sub">{c.reason}</p>
      <FailureChips types={c.failure_types} />
      {supports.map((e) => (
        <p key={e.passage_id} className="tip-line ok">Supported by {e.passage_id}</p>
      ))}
      {challenges.map((e) => (
        <p key={e.passage_id} className={`tip-line ${e.effect === "counts" ? "bad" : "muted"}`}>
          Challenged by {e.passage_id}
          {e.effect === "counts" && e.trigger_conditions.length > 0 &&
            `: applies because ${e.trigger_conditions.map((t) => `${t.field} = ${fmtValue(t.actual)}`).join(", ")}`}
          {e.effect && e.effect !== "counts" && ` (${e.effect.replaceAll("_", " ")})`}
        </p>
      ))}
      {c.missing_slots.length > 0 && <p className="tip-line warn">Missing input: {c.missing_slots.join(", ")}</p>}
      {c.cited_passage_ids.filter((id) => result.roots.find((r) => r.id === id && r.state !== "active")).map((id) => (
        <p key={id} className="tip-line muted">Cited {id} was filtered out</p>
      ))}
      {mock && <p className="tip-sub">Scores come from scripted mock outputs.</p>}
      <p className="tip-hint">Click the branch for the full breakdown.</p>
    </>
  );
}

function RootTip({ r }: { r: RootData }) {
  return (
    <>
      <div className="tip-head"><strong>{r.id}</strong> <StatePill state={r.state} label={r.state_label} /></div>
      <p>{r.title} · v{r.version}</p>
      <p className="tip-sub">{r.state_detail}</p>
      <div className="tip-grid">
        <span>Effective</span><strong>{r.effective_date}</strong>
        <span>Expires</span><strong>{r.expiry_date}</strong>
        <span>SHA-256</span><strong className="mono">{shortHash(r.hash)} {r.hash_ok ? "✔" : "✖"}</strong>
        <span>Source</span><strong className="mono">{r.source.hub}</strong>
      </div>
      {r.parent_doc_id && <p className="tip-line muted">Amends {r.parent_doc_id}</p>}
      {r.supersedes && <p className="tip-line muted">Supersedes {r.supersedes}</p>}
    </>
  );
}
