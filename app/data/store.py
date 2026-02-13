from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InMemoryStore:
    runs: dict[str, dict] = field(default_factory=dict)


STORE = InMemoryStore()
