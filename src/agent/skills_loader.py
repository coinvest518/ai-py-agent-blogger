"""Skill-file loader — compact tool cheatsheets for agent prompts.

Each skill file lives at `skills/{NAME}.skill.md` and describes the 4-6
canonical tools for a given integration (Notion, Google Docs, GA, CDP, etc.).
Agents call `load_skill("NOTION")` and inject the returned text into their
LLM system prompt instead of dumping the full 40+ tool catalogue.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


class SkillNotFoundError(FileNotFoundError):
    pass


@lru_cache(maxsize=32)
def load_skill(name: str) -> str:
    """Return the markdown body of `skills/{NAME}.skill.md`.

    Lookup is case-insensitive and tolerates both `"NOTION"` and `"notion"`.
    Result is cached per-process so repeated calls are free.
    """
    candidates = [
        SKILLS_DIR / f"{name}.skill.md",
        SKILLS_DIR / f"{name.upper()}.skill.md",
        SKILLS_DIR / f"{name.lower()}.skill.md",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise SkillNotFoundError(
        f"No skill file for {name!r} — looked in {[str(p) for p in candidates]}"
    )


def list_skills() -> list[str]:
    """Names of all skill files available (without .skill.md suffix)."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(p.stem.replace(".skill", "") for p in SKILLS_DIR.glob("*.skill.md"))
