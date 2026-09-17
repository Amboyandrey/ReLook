"""Loads the document category taxonomy from config/taxonomy.yaml.

The taxonomy is config, not code, so relabeling or adding categories never
requires touching the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "config" / "taxonomy.yaml"


@dataclass(frozen=True)
class Category:
    name: str
    description: str
    default_owner: str


@dataclass(frozen=True)
class Taxonomy:
    categories: tuple[Category, ...]
    auto_approve_threshold: float

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.categories)

    def owner_for(self, category_name: str) -> str | None:
        for c in self.categories:
            if c.name == category_name:
                return c.default_owner
        return None

    def as_prompt_block(self) -> str:
        """Render the taxonomy as a description list for the system prompt."""
        lines = []
        for c in self.categories:
            lines.append(f"- {c.name}: {c.description.strip()}")
        return "\n".join(lines)


def load_taxonomy(path: str | Path | None = None) -> Taxonomy:
    path = Path(path) if path else DEFAULT_TAXONOMY_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    categories = tuple(
        Category(
            name=name,
            description=data["description"],
            default_owner=data.get("default_owner", "Unassigned"),
        )
        for name, data in raw["categories"].items()
    )

    return Taxonomy(
        categories=categories,
        auto_approve_threshold=float(raw.get("auto_approve_threshold", 0.95)),
    )
