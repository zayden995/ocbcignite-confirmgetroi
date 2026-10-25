// Pure geometry for the illustrated Proof Tree. No React in here.
import type { ClaimNodeData, ProofTreeResult, RootData, Status } from "../../types";

export interface Pt {
  x: number;
  y: number;
}

export const BARK = "#7A5638";

// Branch and leaf colours follow claim status. Leaves use 4 shades so a canopy reads as foliage, not a flat blob.
export const STATUS_PALETTE: Record<Status, { main: string; leaves: string[] }> = {
  Verified: { main: "#2E7D32", leaves: ["#1F6B2B", "#2E7D32", "#43A047", "#6DBF73"] },
  Refuted: { main: "#C8102E", leaves: ["#9E0B22", "#C8102E", "#DC2F47", "#EE6076"] },
  Unresolved: { main: "#D99A00", leaves: ["#B77F00", "#D99A00", "#F2BC2B", "#F8D56B"] },
};

export function mulberry32(seed: number): () => number {
  let a = seed | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function bez(p0: Pt, p1: Pt, p2: Pt, p3: Pt, t: number): Pt {
  const u = 1 - t;
  return {
    x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
    y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
  };
}

function bezTan(p0: Pt, p1: Pt, p2: Pt, p3: Pt, t: number): Pt {
  const u = 1 - t;
  return {
    x: 3 * u * u * (p1.x - p0.x) + 6 * u * t * (p2.x - p1.x) + 3 * t * t * (p3.x - p2.x),
    y: 3 * u * u * (p1.y - p0.y) + 6 * u * t * (p2.y - p1.y) + 3 * t * t * (p3.y - p2.y),
  };
}

const f = (n: number) => n.toFixed(1);

export const cubicPath = (p0: Pt, p1: Pt, p2: Pt, p3: Pt) =>
  `M${f(p0.x)},${f(p0.y)} C${f(p1.x)},${f(p1.y)} ${f(p2.x)},${f(p2.y)} ${f(p3.x)},${f(p3.y)}`;

/** A filled polygon that follows the bezier and narrows from w0 to w1 (a branch, not a line). */
export function taperedPath(p0: Pt, p1: Pt, p2: Pt, p3: Pt, w0: number, w1: number, steps = 22): string {
  const left: Pt[] = [];
  const right: Pt[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const p = bez(p0, p1, p2, p3, t);
    const d = bezTan(p0, p1, p2, p3, t);
    const len = Math.hypot(d.x, d.y) || 1;
    const half = (w0 + (w1 - w0) * t) / 2;
    left.push({ x: p.x - (d.y / len) * half, y: p.y + (d.x / len) * half });
    right.push({ x: p.x + (d.y / len) * half, y: p.y - (d.x / len) * half });
  }
  const pts = [...left, ...right.reverse()];
  return "M" + pts.map((p) => `${f(p.x)},${f(p.y)}`).join(" L") + " Z";
}

export interface Leaf {
  x: number;
  y: number;
  rot: number;
  s: number;
  shade: number;
}

export interface BranchGeo {
  claim: ClaimNodeData;
  center: Pt; // card centre (the branch ends here)
  d: string; // tapered branch polygon
  grad: { x1: number; y1: number; x2: number; y2: number };
  twigs: { d: string; leaves: Leaf[] }[];
  leaves: Leaf[];
  foliage: { rx: number; ry: number };
}

export interface RootGeo {
  root: RootData;
  x: number;
  y: number;
  r: number;
  d: string; // brown tapered root
  line: string; // centre line for the coloured thread
  dots: Pt[];
  threads: { color: string; dash?: string; dx: number }[];
  anchor: Pt; // where evidence links leave the node
}

export interface TreeLayout {
  W: number;
  H: number;
  trunkTop: number;
  ground: number;
  cardW: number;
  cardH: number;
  trunkPath: string;
  branches: BranchGeo[];
  roots: RootGeo[];
  lineage: { d: string; label: string; mid: Pt }[];
}

const leafCluster = (rng: () => number, cx: number, cy: number, rx: number, ry: number, count: number, ring: number): Leaf[] =>
  Array.from({ length: count }, () => {
    const a = rng() * Math.PI * 2;
    const r = ring + (1.05 - ring) * Math.sqrt(rng());
    return {
      x: cx + Math.cos(a) * rx * r,
      y: cy + Math.sin(a) * ry * r,
      rot: rng() * 360,
      s: 0.9 + rng() * 0.8,
      shade: Math.floor(rng() * 4),
    };
  });

const THREAD = { supports: "#2E7D32", challenges: "#C8102E", rejected: "#C8102E", muted: "#7B8794" };

export function layoutTree(result: ProofTreeResult): TreeLayout {
  const W = 1000;
  const n = result.claims.length;
  const cardW = n <= 3 ? 224 : n === 4 ? 196 : 164;
  const cardH = 118;

  // --- canopy: one branch per claim, fanned out above the trunk
  const tOf = (i: number) => (n === 1 ? 0 : (i - (n - 1) / 2) / ((n - 1) / 2));
  const spread = n === 2 ? 235 : n === 3 ? 320 : 340;
  const centers: Pt[] = result.claims.map((_, i) => {
    const t = tOf(i);
    const stagger = n >= 4 && i % 2 === 1 ? 128 : 0;
    return { x: W / 2 + t * spread, y: 190 + 64 * t * t + stagger };
  });
  const canopyBottom = Math.max(...centers.map((c) => c.y)) + cardH / 2 + 34;
  const trunkTop = canopyBottom + 26;
  const ground = trunkTop + 175;

  const trunkPath =
    `M${W / 2 - 30},${trunkTop} C${W / 2 - 28},${trunkTop + 70} ${W / 2 - 40},${ground - 60} ${W / 2 - 78},${ground + 16} ` +
    `L${W / 2 + 78},${ground + 16} C${W / 2 + 40},${ground - 60} ${W / 2 + 28},${trunkTop + 70} ${W / 2 + 30},${trunkTop} Z`;

  const fork: Pt = { x: W / 2, y: trunkTop + 14 };
  const branches: BranchGeo[] = result.claims.map((claim, i) => {
    const t = tOf(i);
    const c = centers[i];
    const p1 = { x: fork.x + t * 24, y: trunkTop - 80 };
    const p2 = { x: c.x - t * 70, y: c.y + 130 };
    const rng = mulberry32(9301 + i * 7919 + claim.id.length * 31);

    const twigs = [0.48, 0.7].map((u, k) => {
      const base = bez(fork, p1, p2, c, u);
      const tan = bezTan(fork, p1, p2, c, u);
      const side = (k + i) % 2 === 0 ? 1 : -1;
      const ang = Math.atan2(tan.y, tan.x) + side * 0.75;
      const len = 62 + rng() * 22;
      const end = { x: base.x + Math.cos(ang) * len, y: base.y + Math.sin(ang) * len };
      const q1 = { x: base.x + Math.cos(ang) * len * 0.35, y: base.y + Math.sin(ang) * len * 0.35 - 6 };
      const q2 = { x: base.x + Math.cos(ang) * len * 0.7, y: base.y + Math.sin(ang) * len * 0.7 - 10 };
      return { d: taperedPath(base, q1, q2, end, 9, 2.5, 10), leaves: leafCluster(rng, end.x, end.y, 26, 20, 6, 0.1) };
    });

    const rx = cardW / 2 + 46;
    const ry = cardH / 2 + 38;
    return {
      claim,
      center: c,
      d: taperedPath(fork, p1, p2, c, 21, 7),
      grad: { x1: fork.x, y1: fork.y, x2: c.x, y2: c.y },
      twigs,
      leaves: leafCluster(rng, c.x, c.y, rx, ry, 64, 0.5),
      foliage: { rx, ry },
    };
  });

  // --- roots: one per passage, filtered passages last so lineage lines stay short
  const claimIndex = new Map(result.claims.map((c, i) => [c.id, i]));
  const firstClaim = (rootId: string) => {
    const idx = result.edges.filter((e) => e.source === rootId && claimIndex.has(e.target)).map((e) => claimIndex.get(e.target)!);
    return idx.length ? Math.min(...idx) : 999;
  };
  const ordered = [...result.roots].sort(
    (a, b) => Number(a.state !== "active") - Number(b.state !== "active") || firstClaim(a.id) - firstClaim(b.id),
  );
  const m = ordered.length;
  const step = m > 1 ? Math.min(232, 800 / (m - 1)) : 0;
  const rootY = ground + 168;
  const r = 34;

  const roots: RootGeo[] = ordered.map((root, i) => {
    const x = W / 2 + (i - (m - 1) / 2) * step;
    const p0 = { x: W / 2 + (x - W / 2) * 0.1, y: ground + 6 };
    const p1 = { x: W / 2 + (x - W / 2) * 0.3, y: ground + 70 };
    const p2 = { x: x - (x - W / 2) * 0.08, y: rootY - 90 };
    const p3 = { x, y: rootY - r };

    const filtered = root.state !== "active";
    const threads: RootGeo["threads"] = [];
    if (root.roles.includes("supports") && !filtered) threads.push({ color: THREAD.supports, dx: 0 });
    if (root.roles.includes("challenges") && !filtered) threads.push({ color: THREAD.challenges, dx: 0 });
    if (filtered) {
      threads.push({ color: root.state === "filtered_not_approved" ? THREAD.rejected : THREAD.muted, dash: "6 6", dx: 0 });
    }
    if (!threads.length) threads.push({ color: THREAD.muted, dash: "6 6", dx: 0 });
    threads.forEach((th, k) => (th.dx = (k - (threads.length - 1) / 2) * 7));

    return {
      root, x, y: rootY, r,
      d: taperedPath(p0, p1, p2, p3, 22, 5),
      line: cubicPath(p0, p1, p2, p3),
      dots: [0.32, 0.56, 0.8].map((u) => bez(p0, p1, p2, p3, u)),
      threads,
      anchor: { x, y: rootY - r },
    };
  });

  // --- lineage: amends / supersedes between roots that are both on the tree
  const lineage: TreeLayout["lineage"] = [];
  for (const e of result.edges) {
    if (e.kind !== "parent" && e.kind !== "supersedes") continue;
    const a = roots.find((g) => g.root.id === e.source);
    const b = roots.find((g) => g.root.id === e.target);
    if (!a || !b) continue;
    const dir = a.x < b.x ? 1 : -1;
    const from = { x: a.x + dir * (r + 2), y: rootY };
    const to = { x: b.x - dir * (r + 2), y: rootY };
    const mid = { x: (from.x + to.x) / 2, y: rootY - 46 };
    lineage.push({ d: `M${f(from.x)},${f(from.y - 6)} Q${f(mid.x)},${f(mid.y - 24)} ${f(to.x)},${f(to.y - 6)}`, label: e.kind === "parent" ? "amends" : "supersedes", mid });
  }

  return { W, H: rootY + 112, trunkTop, ground, cardW, cardH, trunkPath, branches, roots, lineage };
}

/** Curve from a root node up to a claim card, used for the hover "sap lines". */
export function linkPath(from: Pt, to: Pt): string {
  return cubicPath(from, { x: from.x, y: from.y - 150 }, { x: to.x, y: to.y + 150 }, to);
}
