"""Employee intent and provenance. Assistant text is never an input to routing or facts."""
import re
from typing import Literal
from decimal import Decimal

from ..config import DATA_DIR
from .contracts import Fact, Origin, Request, Span, Task, Wire

FIXTURE = Request.model_validate_json((DATA_DIR / "decision_fixture.json").read_text(encoding="utf-8"))
FIXTURE_VALUES = {f.origin.ref: (f.key, f.value) for f in FIXTURE.facts}
MONEY = r"(?:S\$|SGD\s*)\s*((?:[1-9]\d{0,2}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)(?![\d,.]\d|\w)"
UNSUPPORTED = re.compile(r"\b(withdraw\w*|fee|bonus|board[- ]rate|daily|per day|guarantee\w*|settlement|eligib\w*|authori[sz]\w*|alternative|split|approve|tax\w*)\b", re.I)
TRANSFER = re.compile(
    r"\b(?:check|assess|whether)\b[^.?!]*\b(?:transfer|limit|cap)\b|"
    r"\b(?:can|will|does|would|could)\b[^.?!]*\b(?:fund|send|transfer|fit|exceed)\b[^.?!]*\b(?:one|single|limit|cap|fit)\b|"
    r"\btransfer\b[^.?!]*\b(?:fit|exceed|work)\b", re.I)
RATE = re.compile(r"\b(?:rate|interest)\b", re.I)


def route(req: Request) -> tuple[Task | None, str | None, str]:
    question = req.question
    if re.match(r"^(?:and |what if |same (?:case|customer)|what about )", question, re.I) and req.history:
        question = req.history[-1].question + " " + question
    choice = req.confirmation.choice if req.confirmation else None
    outside = UNSUPPORTED.search(question)
    if outside or choice == "other":
        subject = outside.group() if outside else "the selected use"
        return None, "unsupported_task", f"Refer the request about {subject} to the policy owner."
    # Each requested action must be represented, including the last part of a mixed question.
    clauses = re.split(r"[?;]|\band\s+(?=(?:what|how|can|will|why|whether|check|tell|calculate|is|do)\b)", question, flags=re.I)
    for clause in clauses:
        if re.search(r"\b(?:what|how|can|calculate|why|check)\b", clause, re.I) and not (
            RATE.search(clause) or TRANSFER.search(clause) or re.search(r"what should I tell|what (?:if|about)", clause, re.I)
        ):
            return None, "unsupported_task", f"Refer this part to the policy owner: {clause.strip()}"
    # An unrecognised second action must not disappear behind a recognised first one.
    for part in re.split(r"\b(?:and|also|as well as)\b", question, flags=re.I)[1:]:
        if part.strip(" ,.?") and not (RATE.search(part) or TRANSFER.search(part)
                                      or re.search(r"\b(?:single|one)\b[^?!]*\btransfer\b", part, re.I)):
            return None, "unsupported_task", f"Refer the additional request to the policy owner: {part.strip()}"
    wants_rate = bool(RATE.search(question))
    wants_transfer = bool(TRANSFER.search(question))
    explicit = ("plan_and_rate" if wants_transfer else "rate_only") if wants_rate else None
    if choice in {"incomplete", "conflicting"} or (explicit and choice and choice != explicit):
        explicit = None
    elif choice:
        explicit = choice
    if explicit:
        return explicit, None, ""
    if not re.search(r"deposit|placement|rate|FAST|transfer|SteadyGrowth", question, re.I):
        return None, "unsupported_task", f"Refer this request to the policy owner: {req.question}"
    return None, "clarify_intent", "Quote the standard rate only, or quote the rate and check one FAST transfer?"


class IntentReading(Wire):
    choice: Literal["rate_only", "plan_and_rate", "uncertain", "unsupported"]
    evidence: list[Span]


def intended_use(req: Request, provider=None):
    task, reason, prompt = route(req)
    if task or reason != "clarify_intent" or req.confirmation or not provider:
        return task, reason, prompt
    # Only employee text reaches this call. A model suggestion for ambiguous language needs confirmation.
    reading = provider.structured(
        "Identify the requested use: quote the standard annual rate, quote it and check one FAST transfer, "
        "unsupported, or uncertain. Give exact action quotes and Unicode code-point offsets into the current "
        "question. FAST alone is a funding method. Never infer a requested decision from a customer fact.\n"
        + "Earlier employee questions: " + repr([t.question for t in req.history]) + "\nQuestion: " + req.question,
        IntentReading,
    )
    if not reading.evidence or not all(span.matches(req.question) for span in reading.evidence):
        return None, reason, prompt
    words = " / ".join(span.quote for span in reading.evidence)
    if reading.choice == "unsupported":
        return None, "unsupported_task", f"Refer the uncovered request to the policy owner: {words}"
    if reading.choice in {"rate_only", "plan_and_rate"}:
        label = "the standard rate" if reading.choice == "rate_only" else "the rate and one FAST transfer"
        return None, reason, f'“{words}” may refer to {label}. {prompt}'
    return None, reason, prompt


def cents(value: str) -> int:
    return int(Decimal(value.replace(",", "")) * 100)


def validate_text(fact: Fact, question: str) -> bool:
    span = fact.origin.span
    if not span or not span.matches(question):
        return False
    # Negation, a competing amount, or an alternative in the same clause defeats attribution.
    clause = re.split(r"[;?!]|\.\s", question[:span.start])[-1] + span.quote
    clause += re.split(r"[;?!]|\.\s", question[span.end:])[0]
    if re.search(r"\b(?:not|isn't|instead|either|or|might|maybe|except)\b", clause, re.I):
        return False
    if fact.key.endswith("_cents"):
        if re.search(r"[-−+]\s*(?:S\$|SGD)|(?:S\$|SGD)\s*[-+]|\d\.\d{3}|\d[eE][+-]?\d|\b(?:USD|MYR)\b", clause):
            return False
        amounts = re.findall(MONEY, span.quote)
        if len(amounts) != 1 or re.findall(MONEY, clause) != amounts:
            return False
        deposit = re.search(r"\b(?:deposit|placement)\b", clause, re.I)
        single = re.search(r"\b(?:single|one|proposed)\b[^.?!]*\btransfer\b", clause, re.I)
        linked = re.search(r"\b(?:fund|send|place)\b[^?!]*(?:\bin (?:one|a single)\b|\b(?:entire|whole|full)\b)", clause, re.I)
        if fact.key == "transfer_cents":
            subject = single and (not deposit or linked)
        else:
            subject = deposit and (not single or linked)
        return bool(subject and cents(amounts[0]) == fact.value)
    if fact.key == "tenor_months":
        return bool(re.search(rf"\b{fact.value}[- ]months?\b", span.quote, re.I))
    if fact.key == "booking_region" and not re.search(r"\bbook(?:ed|ing)?\b", clause, re.I):
        return False
    return bool(re.search(rf"\b{re.escape(str(fact.value))}\b", span.quote, re.I))


def employee_amounts(req: Request) -> list[Fact]:
    """An employee may link both amounts in one sentence. Never inherit a placement total by default."""
    found = []
    turn = req
    for match in re.finditer(MONEY, turn.question):
        value = cents(match[1])
        if not 0 < value < 2**53:
            continue
        span = Span(start=match.start(), end=match.end(), quote=match[0])
        for key in ("deposit_cents", "transfer_cents"):
            fact = Fact(key=key, value=value, origin=Origin(kind="employee_text", ref=turn.turn_id, span=span))
            if validate_text(fact, turn.question):
                found.append(fact)
    return found


def trusted_facts(req: Request) -> dict[str, str | int]:
    questions = {t.turn_id: t.question for t in [*req.history, req]}
    values = {}
    conflicts = set()
    for fact in req.facts:
        origin = fact.origin
        if origin.kind == "fixture" and FIXTURE_VALUES.get(origin.ref) != (fact.key, fact.value):
            raise ValueError(f"Unknown synthetic fact: {origin.ref}")
        if origin.kind == "employee_text" and not validate_text(fact, questions.get(origin.ref, "")):
            raise ValueError(f"Employee quote does not establish {fact.key}")
        if fact.key in values and values[fact.key] != fact.value:
            conflicts.add(fact.key)
        values[fact.key] = fact.value
    return {key: value for key, value in values.items() if key not in conflicts}

def resolve_facts(req: Request):
    inferred = employee_amounts(req)
    # A later, explicitly corrected form value supersedes the original wording.
    explicit = {f.key for f in req.facts if f.origin.kind == "form"}
    inferred = [f for f in inferred if f.key not in explicit or req.input_revision == 1]
    facts = trusted_facts(req.model_copy(update={"facts": [*req.facts, *inferred]}))
    supplied = {f.key for f in req.facts}
    origins = {f.key: f for f in inferred if f.key in facts and f.key not in supplied}
    return facts, origins
