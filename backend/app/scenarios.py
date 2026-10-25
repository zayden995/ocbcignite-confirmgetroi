from __future__ import annotations

import json

from .config import DATA_DIR
from .errors import ScenarioNotFound


def load_scenarios() -> list[dict]:
    with open(DATA_DIR / "scenarios.json", encoding="utf-8") as f:
        return json.load(f)["scenarios"]


def get_scenario(scenario_id: str) -> dict:
    for s in load_scenarios():
        if s["id"] == scenario_id:
            return s
    raise ScenarioNotFound(f"unknown scenario '{scenario_id}'")


def load_slot_defs() -> dict:
    with open(DATA_DIR / "slots.json", encoding="utf-8") as f:
        return json.load(f)
