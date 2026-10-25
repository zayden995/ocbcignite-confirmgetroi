"""Write the SHA-256 manifest hash into data/passages.json.

Run from backend/:  .venv\\Scripts\\python.exe scripts\\seal_passages.py
Re-run after editing any passage text (tests deliberately fail on a stale hash).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import DATA_DIR  # noqa: E402
from app.corpus import compute_hash  # noqa: E402

path = DATA_DIR / "passages.json"
doc = json.loads(path.read_text(encoding="utf-8"))
for p in doc["passages"]:
    p["hash"] = compute_hash(p["text"])
path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"sealed {len(doc['passages'])} passages")
