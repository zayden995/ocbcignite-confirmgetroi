import os
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

# Fixed "today" so freshness results are repeatable on demo day.
DEMO_DATE = date(2026, 10, 28)

# Lives inside backend/ so a Vercel service rooted at backend/ ships it with the function.
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

DATA_LABEL = "Synthetic - not real OCBC policy"


def resolve_provider(env: Mapping[str, str]) -> str:
    """Which LLM the app uses.

    Gemini (app/llm/provider.py) whenever GEMINI_API_KEY is set. Without a key the app falls back
    to "mock", the scripted fixtures, so it still runs offline and in tests. TREE_LLM_PROVIDER
    overrides this choice: "mock" forces the fixtures even with a key, and any name other than
    "gemini" fails loudly as not implemented.
    """
    explicit = env.get("TREE_LLM_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    return "gemini" if env.get("GEMINI_API_KEY", "").strip() else "mock"


LLM_PROVIDER = resolve_provider(os.environ)
