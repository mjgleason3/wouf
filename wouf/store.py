"""WARM/COLD persistence: JSONL records plus a rendered human-readable view."""

from __future__ import annotations

import json
from pathlib import Path

from .graph import Graph
from .models import Edge, Memory
from .render import render_pack


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exists(self) -> bool:
        return (self.path / "memories.jsonl").exists()

    def save(self, memories: dict[str, Memory], graph: Graph, archive: list[dict]) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        self._write_jsonl("memories.jsonl", [m.to_dict() for m in memories.values()])
        self._write_jsonl("edges.jsonl", [e.to_dict() for e in graph.edges])
        self._write_jsonl("archive.jsonl", archive)
        human_view = render_pack(sorted(memories.values(), key=lambda m: m.id))
        (self.path / "MEMORY.md").write_text(human_view + "\n")

    def load(self) -> tuple[dict[str, Memory], Graph, list[dict]]:
        memories = {
            d["id"]: Memory.from_dict(d) for d in self._read_jsonl("memories.jsonl")
        }
        graph = Graph([Edge.from_dict(d) for d in self._read_jsonl("edges.jsonl")])
        archive = self._read_jsonl("archive.jsonl")
        return memories, graph, archive

    def _write_jsonl(self, name: str, rows: list[dict]) -> None:
        lines = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        (self.path / name).write_text(lines)

    def _read_jsonl(self, name: str) -> list[dict]:
        file = self.path / name
        if not file.exists():
            return []
        return [json.loads(line) for line in file.read_text().splitlines() if line.strip()]
