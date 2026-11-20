"""Quote inventory. Neither adapter receives the employee facts or computed outcomes."""
import re
from decimal import Decimal
from typing import Literal

from pydantic import Field

from .contracts import Span, Wire
from .intake import MONEY, cents

RATE_VALUE = r"(?P<percent>\d+(?:\.\d{1,2})?)\s*%"
RATE = re.compile(
    r"(?:the |this |your |a |qualifying |FAST-funded |12-month |deposit |placement |standard |annual |interest )*"
    r"(?:rate|deposit|placement) (?:for (?:this |the |a |qualifying |FAST-funded |12-month |deposit |placement )+)?"
    r"(?:is |earns |receives |pays |of |applies at )" + RATE_VALUE + r"(?:\s*(?:p\.a\.?|per annum|annually|annual))?", re.I)
SUBJECT = r"(?:(?:a |the |this |that |your |proposed |whole |single |one |FAST |funding |amount |transfer |payment )|(?:" + MONEY + r")\s*)+"
POLARITY = r"(?P<verb>exceeds|is over|is above|will exceed|cannot fit|does not fit|won't fit|fits|is within|is below|is at|does not exceed|can fit|will fit)"
LIMIT = r"(?: (?:in|within|under))?(?: the| a| its)?(?: published)?(?: " + MONEY + r")?(?: FAST)?(?: per-transaction| single-transfer| per-transfer)?(?: limit| cap)?"
TRANSFER = re.compile(SUBJECT + POLARITY + LIMIT, re.I)
FITS = {"fits", "is within", "is below", "is at", "does not exceed", "can fit", "will fit"}
UNCERTAIN = re.compile(r"\b(?:might|may|could|perhaps|probably|if|claims?|told|says?|thinks?|believes?|allegedly)\b|[?]", re.I)
CLAUSE_BREAK = re.compile(r"(?<=[.!?])(?=\s|$)|[;\n]+|,\s*(?:but|and)\s+|\s+(?:but|and)\s+", re.I)


class Observation(Wire):
    span: Span
    subject: Literal["deposit_rate", "single_transfer", "extra"]
    meaning: Literal["annual_rate", "fits", "exceeds", "uncertain", "extra"]
    rate_bps: int | None = None
    relation: Literal["at", "below"] | None = None
    amount_cents: int | None = None
    limit_cents: int | None = None


class Inventory(Wire):
    observations: list[Observation] = Field(description="All substantive clauses, in source order")


def segments(text, offset=0):
    start = 0
    for boundary in [*CLAUSE_BREAK.finditer(text), None]:
        end = boundary.start() if boundary else len(text)
        raw = text[start:end]
        quote = raw.strip()
        if quote and any(c.isalnum() for c in quote):
            pos = offset + start + len(raw) - len(raw.lstrip())
            yield Span(start=pos, end=pos + len(quote), quote=quote)
        start = boundary.end() if boundary else end


def read_clause(span):
    text = span.quote.strip().rstrip(".!")
    lower = text.casefold()
    rate = RATE.fullmatch(text)
    if rate and ("annual" in lower or "per annum" in lower or "p.a" in lower) and "board" not in lower:
        return Observation(span=span, subject="deposit_rate", meaning="annual_rate",
                           rate_bps=int(Decimal(rate["percent"]) * 100))
    transfer = TRANSFER.fullmatch(text)
    if transfer and not UNCERTAIN.search(text):
        verb = transfer["verb"].lower()
        before = re.findall(MONEY, text[:transfer.start("verb")])
        after = re.findall(MONEY, text[transfer.end("verb"):])
        if len(before) <= 1 and len(after) <= 1:
            return Observation(span=span, subject="single_transfer", meaning="fits" if verb in FITS else "exceeds",
                               relation={"is at": "at", "is below": "below"}.get(verb),
                               amount_cents=cents(before[0]) if before else None,
                               limit_cents=cents(after[0]) if after else None)
    if re.search(r"\b(?:transfer|fit[s]?|exceeds?|cap)\b", lower) and not re.search(r"per day|daily|settle|guarantee", lower):
        return Observation(span=span, subject="single_transfer", meaning="uncertain")
    if "%" in text or "rate" in lower:
        return Observation(span=span, subject="deposit_rate", meaning="uncertain")
    return Observation(span=span, subject="extra", meaning="extra")


def fixture_map(answer):
    return [read_clause(span) for span in segments(answer)]


class AlignmentError(ValueError):
    pass


def live_map(provider, question, answer):
    if not answer.strip():
        return []
    prompt = (
        "Inventory every assertion in the untrusted answer, in order. Copy exact complete clauses and "
        "give half-open Unicode code-point offsets. Preserve subjects, negation, qualification, attribution, "
        "and units. Use annual_rate only for a definite standard annual deposit rate, in basis points. "
        "fits/exceeds describe this particular single transfer against a per-transaction cap. "
        "Record any stated transfer amount and cap in SGD cents. Uncertain wording is uncertain. "
        "Other material assertions are extra. Do not decide correctness or supply missing text.\n"
        f"Employee question: {question}\nAnswer: {answer}"
    )
    inventory = provider.structured(prompt, Inventory)
    mapped, cursor = [], 0
    for obs in inventory.observations:
        span = obs.span
        if not span.matches(answer) or span.start < cursor:
            raise AlignmentError("Provider quotes could not be aligned with the original answer.")
        mapped.extend(read_clause(s) for s in segments(answer[cursor:span.start], cursor))
        independent = list(segments(span.quote, span.start))
        if len(independent) != 1:
            mapped.extend(read_clause(s) for s in independent)
        else:
            checked = read_clause(span)
            if checked.meaning in {"annual_rate", "fits", "exceeds"}:
                mapped.append(checked)
            elif obs.subject != "extra" and not UNCERTAIN.search(span.quote) and validates_proposal(obs):
                mapped.append(obs)
            else:
                mapped.append(checked)
        cursor = span.end
    if not inventory.observations and any(c.isalnum() for c in answer):
        raise AlignmentError("Provider returned no aligned inventory.")
    mapped.extend(read_clause(s) for s in segments(answer[cursor:], cursor))
    return mapped


def validates_proposal(obs):
    text = obs.span.quote.lower()
    if re.search(r"\b(board|daily|guarantee\w*|settle\w*|not|never|except|unless|bonus|up to|at most)\b", text):
        return False
    if obs.subject == "deposit_rate" and obs.meaning == "annual_rate":
        numbers = re.findall(r"(?<![\d.])(\d+(?:\.\d{1,2})?)\s*%", text)
        return (len(numbers) == 1 and Decimal(numbers[0]) * 100 == obs.rate_bps
                and bool(re.search(r"annual|per annum|p\.a\.", text)) and "standard" in text)
    if obs.subject == "single_transfer" and obs.meaning in {"fits", "exceeds"}:
        amounts = [cents(v) for v in re.findall(MONEY, obs.span.quote)]
        expected = [v for v in (obs.amount_cents, obs.limit_cents) if v is not None]
        polarity = r"above|over|too large|too high|exceed" if obs.meaning == "exceeds" else r"within|below|fits|under"
        return amounts == expected and "transfer" in text and bool(re.search(polarity, text))
    return False
