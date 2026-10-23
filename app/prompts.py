"""Loads the system prompts. The text is private: it lives in a git-ignored prompts/ folder, deployed to
sk24 at 0640. Tests point CVWRITE_PROMPTS_DIR at stub prompts. The loader is public; the prompts are not."""
import os
from functools import lru_cache
from pathlib import Path

NAMES = ("ad_read", "write_cv", "reformat")


@lru_cache(maxsize=None)
def get(name, directory=None):
    if name not in NAMES:
        raise KeyError(name)
    d = Path(directory or os.environ.get("CVWRITE_PROMPTS_DIR") or Path(__file__).resolve().parent.parent / "prompts")
    path = d / f"{name}.md"
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"prompt {path.name} is empty")
    return text
