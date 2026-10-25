"""Serialise claims and passages into the Proof Tree payload (roots, edges, badges)."""
from __future__ import annotations

from .context import RunContext
from .models import ClaimNode, Edge, MissingInput, PassageState, RootNode

STATE_LABELS: dict[str, str] = {
    "active": "Active",
    "filtered_expired": "Filtered: expired",
    "filtered_inapplicable": "Filtered: not applicable",
    "filtered_not_approved": "Filtered: not approved",
    "filtered_hash_mismatch": "Filtered: hash mismatch",
}


def _state_detail(state: PassageState, ctx: RunContext, passage_id: str) -> str:
    rec = ctx.corpus.records[passage_id]
    p = rec.passage
    if state == "active":
        return f"Effective {p.effective_date} to {p.expiry_date}; valid on {ctx.today}."
    if state == "filtered_expired":
        extra = f" Document status: {p.status}." if p.status != "active" else ""
        return f"Not valid on {ctx.today} (effective {p.effective_date}, expires {p.expiry_date}).{extra}"
    if state == "filtered_inapplicable":
        e = ctx.employee
        return f"Scope is regions {', '.join(p.region)} / roles {', '.join(p.role_scope)}; employee is {e.role} in {e.region}."
    if state == "filtered_not_approved":
        return f"Source {p.source.hub}{p.source.path} is not on the approved-sources list."
    return "SHA-256 of the text does not match the ingestion manifest."


def build_roots(claims: list[ClaimNode], ctx: RunContext) -> list[RootNode]:
    roles: dict[str, list[str]] = {}

    def mark(pid: str, role: str) -> None:
        if pid in ctx.corpus.records and role not in roles.setdefault(pid, []):
            roles[pid].append(role)

    for c in claims:
        for pid in c.cited_passage_ids:
            mark(pid, "cited")
        for e in c.evidence:
            mark(e.passage_id, e.role)

    roots = []
    for pid, r in roles.items():
        rec = ctx.corpus.records[pid]
        p = rec.passage
        state = ctx.state_of(pid)
        assert state is not None
        roots.append(
            RootNode(
                id=pid, doc_id=p.doc_id, title=p.title, version=p.version,
                effective_date=p.effective_date, expiry_date=p.expiry_date, doc_status=p.status,
                authority=p.authority, source=p.source, supersedes=p.supersedes, parent_doc_id=p.parent_doc_id,
                hash=rec.computed_hash, hash_ok=rec.hash_ok,
                state=state, state_label=STATE_LABELS[state], state_detail=_state_detail(state, ctx, pid),
                snippet=p.text, conditions=p.conditions, roles=r,
            )
        )
    return roots


def build_edges(claims: list[ClaimNode], roots: list[RootNode]) -> list[Edge]:
    edges: list[Edge] = []
    for c in claims:
        linked = set()
        for e in c.evidence:
            edges.append(Edge(source=e.passage_id, target=c.id, kind=e.role))
            linked.add(e.passage_id)
        for pid in c.cited_passage_ids:
            if pid not in linked and any(r.id == pid for r in roots):
                edges.append(Edge(source=pid, target=c.id, kind="cites"))
        edges.append(Edge(source=c.id, target="conclusion", kind="claim_of"))

    first_of_doc: dict[str, str] = {}
    for r in roots:
        first_of_doc.setdefault(r.doc_id, r.id)
    for r in roots:
        if r.parent_doc_id in first_of_doc:
            edges.append(Edge(source=r.id, target=first_of_doc[r.parent_doc_id], kind="parent"))
        if r.supersedes in first_of_doc:
            edges.append(Edge(source=r.id, target=first_of_doc[r.supersedes], kind="supersedes"))
    return edges


def build_missing_inputs(claims: list[ClaimNode], slot_defs: dict) -> list[MissingInput]:
    fields = list(dict.fromkeys(f for c in claims for f in c.missing_slots))
    out = []
    for f in fields:
        d = slot_defs["slots"].get(f, {"label": f, "type": "text"})
        out.append(MissingInput(field=f, label=d["label"], type=d["type"], options=d.get("options", [])))
    return out
