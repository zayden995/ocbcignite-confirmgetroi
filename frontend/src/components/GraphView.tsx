import { useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ClaimNodeData, EdgeData, ProofTreeResult, RootData, Status } from "../types";
import { FailureChips, STATUS_CLASS, StatePill, StatusBadge, shortHash } from "./common";

type RootNodeT = Node<{ root: RootData }, "root">;
type ClaimNodeT = Node<{ claim: ClaimNodeData; selected: boolean }, "claim">;
type TrunkNodeT = Node<{ text: string; status: Status }, "trunk">;

const hidden = { opacity: 0, pointerEvents: "none" as const };

function RootNodeView({ data }: NodeProps<RootNodeT>) {
  const r = data.root;
  return (
    <div className={`tnode root-node state-${r.state}`}>
      <Handle type="source" position={Position.Top} id="up" style={hidden} />
      <Handle type="source" position={Position.Right} id="sr" style={hidden} />
      <Handle type="source" position={Position.Left} id="sl" style={hidden} />
      <Handle type="target" position={Position.Left} id="tl" style={hidden} />
      <Handle type="target" position={Position.Right} id="tr" style={hidden} />
      <div className="rn-head">
        <strong>{r.id}</strong>
        <StatePill state={r.state} label={r.state_label} />
      </div>
      <div className="rn-title">
        {r.title} · v{r.version}
      </div>
      <div className="rn-meta">
        SHA-256 {shortHash(r.hash)} {r.hash_ok ? "✔ verified" : "✖ mismatch"}
      </div>
      {r.parent_doc_id && <div className="rn-meta">amends {r.parent_doc_id}</div>}
      {r.supersedes && <div className="rn-meta">supersedes {r.supersedes}</div>}
    </div>
  );
}

function ClaimNodeView({ data }: NodeProps<ClaimNodeT>) {
  const c = data.claim;
  return (
    <div className={`tnode claim-node ${STATUS_CLASS[c.status]}${data.selected ? " selected" : ""}`}>
      <Handle type="target" position={Position.Bottom} style={hidden} />
      <Handle type="source" position={Position.Top} style={hidden} />
      <div className="cn-head">
        <strong>{c.id.split(".").pop()}</strong>
        <StatusBadge status={c.status} />
      </div>
      <div className="cn-text">{c.text}</div>
      <div className="cn-meta">
        SE {c.se.toFixed(2)} · SC {c.sc.toFixed(2)}
      </div>
      <FailureChips types={c.failure_types} />
    </div>
  );
}

function TrunkNodeView({ data }: NodeProps<TrunkNodeT>) {
  return (
    <div className={`tnode trunk-node ${STATUS_CLASS[data.status]}`}>
      <Handle type="target" position={Position.Bottom} style={hidden} />
      <div className="tn-label">AI conclusion</div>
      <div className="tn-text">{data.text}</div>
      <StatusBadge status={data.status} big />
    </div>
  );
}

const nodeTypes = { root: RootNodeView, claim: ClaimNodeView, trunk: TrunkNodeView };

const ROOT_W = 250;
const CLAIM_W = 270;
const TRUNK_W = 320;
const GAP = 30;
const ROOT_GAP = 76; // wide enough for the "amends" / "supersedes" edge label
const Y = { trunk: 0, claim: 190, root: 410 };

const EFFECT_LABEL: Record<string, string> = {
  counts: "challenges",
  conflict: "conflicts (flag)",
  ignored_lower_authority: "ignored: lower authority",
  not_triggered: "exception not triggered",
  needs_input: "input needed",
};

function layout(result: ProofTreeResult, selectedId: string | null): { nodes: Node[]; edges: Edge[] } {
  const claimIndex = new Map(result.claims.map((c, i) => [c.id, i]));
  // order roots under the first claim they feed so edges stay short
  const firstClaim = (rootId: string) => {
    const idx = result.edges
      .filter((e) => e.source === rootId && claimIndex.has(e.target))
      .map((e) => claimIndex.get(e.target)!);
    return idx.length ? Math.min(...idx) : 999;
  };
  // filtered passages go last so lineage edges between usable passages stay short
  const roots = [...result.roots].sort(
    (a, b) =>
      Number(a.state !== "active") - Number(b.state !== "active") || firstClaim(a.id) - firstClaim(b.id),
  );

  const rowW = (n: number, w: number, gap = GAP) => n * w + Math.max(0, n - 1) * gap;
  const width = Math.max(rowW(roots.length, ROOT_W, ROOT_GAP), rowW(result.claims.length, CLAIM_W), TRUNK_W);
  const start = (n: number, w: number, gap = GAP) => (width - rowW(n, w, gap)) / 2;

  const nodes: Node[] = [
    {
      id: "conclusion", type: "trunk", position: { x: (width - TRUNK_W) / 2, y: Y.trunk },
      data: { text: result.trunk.text, status: result.trunk.status }, style: { width: TRUNK_W },
      draggable: false,
    } as TrunkNodeT,
    ...result.claims.map(
      (c, i) =>
        ({
          id: c.id, type: "claim",
          position: { x: start(result.claims.length, CLAIM_W) + i * (CLAIM_W + GAP), y: Y.claim },
          data: { claim: c, selected: c.id === selectedId }, style: { width: CLAIM_W }, draggable: false,
        }) as ClaimNodeT,
    ),
    ...roots.map(
      (r, i) =>
        ({
          id: r.id, type: "root",
          position: { x: start(roots.length, ROOT_W, ROOT_GAP) + i * (ROOT_W + ROOT_GAP), y: Y.root },
          data: { root: r }, style: { width: ROOT_W }, draggable: false,
        }) as RootNodeT,
    ),
  ];
  const xOf = new Map(nodes.map((n) => [n.id, n.position.x]));

  const evidenceEffect = (e: EdgeData) =>
    result.claims.find((c) => c.id === e.target)?.evidence.find((v) => v.passage_id === e.source)?.effect ?? null;

  const edges: Edge[] = result.edges.map((e, i) => {
    const base: Edge = { id: `e${i}`, source: e.source, target: e.target, markerEnd: { type: MarkerType.ArrowClosed } };
    switch (e.kind) {
      case "supports":
        return { ...base, sourceHandle: "up", label: "supports", style: { stroke: "#15803d", strokeWidth: 2 } };
      case "challenges": {
        const fx = evidenceEffect(e);
        const dim = fx === "not_triggered" || fx === "ignored_lower_authority";
        return {
          ...base, sourceHandle: "up", label: EFFECT_LABEL[fx ?? "counts"] ?? "challenges",
          style: { stroke: "#b91c1c", strokeWidth: 2, strokeDasharray: dim ? "4 4" : undefined, opacity: dim ? 0.6 : 1 },
        };
      }
      case "cites":
        return { ...base, sourceHandle: "up", label: "cited", style: { stroke: "#6b7280", strokeDasharray: "4 4" } };
      case "claim_of":
        return { ...base, style: { stroke: "#475569", strokeWidth: 2 } };
      default: {
        // root-to-root lineage (amends / supersedes): attach on the side facing the other root
        const right = (xOf.get(e.source) ?? 0) < (xOf.get(e.target) ?? 0);
        return {
          ...base, sourceHandle: right ? "sr" : "sl", targetHandle: right ? "tl" : "tr",
          label: e.kind === "parent" ? "amends" : "supersedes",
          style: { stroke: "#1d4ed8", strokeDasharray: "2 4", strokeWidth: 2 },
        };
      }
    }
  });
  return { nodes, edges };
}

/** Structured claim-to-passage graph (React Flow) for the admin view. The employee view uses the illustrated tree. */
export function GraphView({
  result, selectedId, onSelectClaim,
}: {
  result: ProofTreeResult;
  selectedId: string | null;
  onSelectClaim: (id: string) => void;
}) {
  const { nodes, edges } = useMemo(() => layout(result, selectedId), [result, selectedId]);
  return (
    <section className="tree-section">
      <div className="tree-head">
        <h2>Claim and passage graph</h2>
        <div className="legend small">
          <span className="swatch ok" /> Verified <span className="swatch bad" /> Refuted{" "}
          <span className="swatch warn" /> Unresolved · click a branch for details
        </div>
      </div>
      <div className="tree-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.12 }}
          nodesDraggable={false}
          nodesConnectable={false}
          onNodeClick={(_, n) => n.type === "claim" && onSelectClaim(n.id)}
          minZoom={0.3}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </section>
  );
}
