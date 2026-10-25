import os
from datetime import date
from pathlib import Path

# Fixed "today" so freshness results are repeatable on demo day.
DEMO_DATE = date(2026, 10, 28)

# Lives inside backend/ so a Vercel service rooted at backend/ ships it with the function.
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

DATA_LABEL = "Synthetic - not real OCBC policy"

# "mock" (default) returns scripted fixtures. Any other value selects the
# real-provider adapter stub in app/llm/provider.py.
LLM_PROVIDER = os.environ.get("TREE_LLM_PROVIDER", "mock").strip().lower()
