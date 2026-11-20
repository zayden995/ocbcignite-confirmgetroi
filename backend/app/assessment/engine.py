import re
from uuid import uuid4

from ..context import RunContext
from ..models import Claim, Employee, NLIResult
from ..pipeline import check_claim
from .contracts import Action, Coverage, Extra, Rate, Repair, Request, Result, Transfer
from .intake import intended_use
from .mapping import fixture_map, live_map
from .policy import Policy


def compare(calc, observations, facts):
    branch = calc.branch
    branch.spans = [o.span for o in observations]
    if branch.expected is None:
        return
    results = []
    for obs in observations:
        if obs.meaning == "uncertain":
            results.append("uncertain_text")
        elif isinstance(branch.expected, Rate):
            results.append("covered" if obs.rate_bps == branch.expected.rate_bps else "wrong")
        else:
            expected: Transfer = branch.expected
            matches = ((obs.meaning == "fits") == expected.within_cap
                       and obs.limit_cents in (None, expected.limit_cents)
                       and obs.amount_cents in (None, facts.get("transfer_cents")))
            if obs.relation == "at":
                matches = matches and facts["transfer_cents"] == expected.limit_cents
            if obs.relation == "below":
                matches = matches and facts["transfer_cents"] < expected.limit_cents
            results.append("covered" if matches else "wrong")
    branch.status = next((s for s in ("wrong", "uncertain_text", "covered") if s in results), "omitted")
    reason = {"omitted": "The answer does not address this decision.", "wrong": "The quoted conclusion disagrees.",
              "uncertain_text": "The wording does not establish a definite conclusion.", "covered": "The quoted answer agrees."}
    branch.explanation += " " + reason[branch.status]


class SnapshotEvidence:
    """Supply this claim's pinned passage labels to the existing conflict checks."""
    def __init__(self, labels, is_mock):
        self.labels = labels
        self.is_mock = is_mock

    def nli(self, claim, passage):
        return self.labels.get(passage.passage_id, NLIResult(label="neutral", score=0))


def extra_finding(obs, policy, req, facts, provider, roots):
    if obs.subject != "extra":
        calc = policy.calculate(obs.subject, facts, req.employee, req.as_of)
        compare(calc, [obs], facts)
        roots.update((r.passage_id, r) for r in calc.roots)
        branch = calc.branch
        return Extra(span=obs.span, status={"covered": "supported", "wrong": "wrong"}.get(branch.status, "unresolved"),
                     source_ids=branch.source_ids, explanation=branch.explanation)
    params = dict(facts)
    if "deposit_cents" in facts:
        params["deposit_amount"] = facts["deposit_cents"] / 100
    emp = Employee(**req.employee.model_dump(), params=params)
    claim = Claim(id=f"span-{obs.span.start}", text=obs.span.quote)
    if provider:
        # Compare this anchored assertion with this snapshot, including contrary eligible clauses.
        passages = [rec.passage for pid, rec in policy.corpus.records.items()
                    if policy.root(pid, emp, req.as_of).state == "context"
                    and facts.get("booking_region") in rec.passage.region]
        labels = provider.label_evidence(claim, passages)
        claim.cited_passage_ids = [pid for pid, label in labels.items() if label.label != "neutral"]
    else:
        eligibility = policy.calculate("deposit_rate", facts, req.employee, req.as_of)
        # The fixture can ground a literal placement rule. Other extra prose stays unresolved.
        labels = {}
        for root in eligibility.roots:
            if eligibility.branch.expected and root.state == "context" and "minimum placement" in root.text.lower():
                sentences = [s.rstrip(".").casefold() for s in root.text.split(". ")]
                if claim.text.rstrip(".").casefold() in sentences:
                    labels[root.passage_id] = NLIResult(label="entails", score=1)
        claim.cited_passage_ids = list(labels)
    ctx = RunContext(policy.corpus, SnapshotEvidence(labels, provider is None), emp, req.as_of)
    checked = check_claim(claim, ctx)
    status = {"Verified": "supported", "Refuted": "wrong", "Unresolved": "unresolved"}[checked.status]
    evidence = list(dict.fromkeys(e.passage_id for e in checked.evidence))
    for pid in evidence:
        root = policy.root(pid, emp, req.as_of)
        roots.setdefault(pid, root)
        if root.state != "context" or facts.get("booking_region") not in policy.corpus.records[pid].passage.region:
            status = "unresolved"
    return Extra(span=obs.span, status=status, source_ids=evidence,
                 explanation=checked.reason if status != "unresolved" else "No conclusive applicable evidence for this assertion.")


def next_step(calculations, extras, answer):
    if any(c.branch.status == "policy_review" for c in calculations):
        return Action(kind="review_policy", prompt="Refer the affected policy and source revisions to the policy owner."), None
    missing = list(dict.fromkeys(field for c in calculations for field in c.missing))
    if missing:
        return Action(kind="supply_fact", fields=missing, prompt="Confirm the missing or conflicting employee facts."), None
    if any(e.status != "supported" for e in extras) or any(c.branch.status == "uncertain_text" for c in calculations):
        return Action(kind="review_text", prompt="Review the highlighted wording and recheck the whole answer."), None
    changes = [c for c in calculations if c.branch.status != "covered"]
    if not changes:
        return Action(kind="use", prompt="Use this answer for the selected task."), None
    edits = []
    append = []
    sources = []
    for c in changes:
        sources.extend(r.passage_id for r in c.roots if r.state == "governing")
        if not c.branch.spans:
            append.append(c.sentence)
        elif len(c.branch.spans) == 1:
            s = c.branch.spans[0]
            edits.append((s.start, s.end, c.sentence))
        else:
            return Action(kind="review_text", prompt="Reconcile the competing statements before rechecking."), None
    for start, end, replacement in sorted(edits, reverse=True):
        answer = answer[:start] + replacement + answer[end:]
    return Action(kind="review_repair", prompt="Review the proposed answer before replying."), Repair(
        text=" ".join(filter(None, [answer.strip(), *append])), source_ids=list(dict.fromkeys(sources)))


def assess(req: Request, policy: Policy, facts, provider=None, *, origins=None) -> Result:
    task, reason, prompt = intended_use(req, provider)
    mode = "live" if provider else "fixture"
    common = dict(assessment_id=uuid4().hex, turn_id=req.turn_id, input_revision=req.input_revision,
                  bundle_id=req.bundle_id, snapshot_id=policy.snapshot_id, mode=mode, task_id=task)
    if not task:
        action = "clarify_intent" if reason == "clarify_intent" else "review_policy"
        return Result(**common, verdict="hold", reasons=[reason], coverage=Coverage(covered=0, required=0),
                      branches=[], extras=[], roots=[], next=Action(kind=action, prompt=prompt), repair=None)
    decisions = policy.tasks[task]
    conditional_rate = bool(re.search(r"\bqualifying\b|\bif (?:the |this )?(?:placement|deposit) qualifies\b", req.question, re.I))
    calculations = [policy.calculate(d, facts, req.employee, req.as_of, conditional_rate=conditional_rate) for d in decisions]
    inventory = live_map(provider, req.question, req.answer) if provider else fixture_map(req.answer)
    roots = {r.passage_id: r for c in calculations for r in c.roots}
    for c in calculations:
        compare(c, [o for o in inventory if o.subject == c.branch.decision_id], facts)
        for key, f in (origins or {}).items():
            if key in c.branch.fact_keys:
                c.branch.explanation += f' Employee turn {f.origin.ref} supplies {key}: “{f.origin.span.quote}”.'
    extras = [extra_finding(o, policy, req, facts, provider, roots) for o in inventory if o.subject not in decisions]
    branches = [c.branch for c in calculations]
    covered = sum(b.status == "covered" for b in branches)
    reasons = ["branch_blocked"] if covered < len(branches) else []
    if any(e.status != "supported" for e in extras):
        reasons.append("extra_claim")
    action, repair = next_step(calculations, extras, req.answer)
    return Result(**common, verdict="hold" if reasons else "ready", reasons=reasons,
                  coverage=Coverage(covered=covered, required=len(branches)), branches=branches,
                  extras=extras, roots=list(roots.values()), next=action, repair=repair)
