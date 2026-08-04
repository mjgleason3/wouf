"""Edge store and neighbor queries for the memory graph."""

from __future__ import annotations

from .models import Edge, EdgeKind


class Graph:
    def __init__(self, edges: list[Edge] | None = None):
        self.edges: list[Edge] = edges or []

    def link(self, src: str, dst: str, kind: EdgeKind, weight: float = 1.0) -> Edge:
        """Add an edge, deduplicating on (src, dst, kind); keeps the max weight."""
        for e in self.edges:
            if e.src == src and e.dst == dst and e.kind == kind:
                e.weight = max(e.weight, weight)
                return e
        edge = Edge(src=src, dst=dst, kind=kind, weight=weight)
        self.edges.append(edge)
        return edge

    def neighbors(self, mem_id: str) -> list[tuple[str, EdgeKind, float]]:
        """All memories one hop away, traversing edges in both directions."""
        out: list[tuple[str, EdgeKind, float]] = []
        for e in self.edges:
            if e.src == mem_id:
                out.append((e.dst, e.kind, e.weight))
            elif e.dst == mem_id:
                out.append((e.src, e.kind, e.weight))
        return out

    def edges_of(self, mem_id: str, kind: EdgeKind | None = None) -> list[Edge]:
        return [
            e
            for e in self.edges
            if (e.src == mem_id or e.dst == mem_id) and (kind is None or e.kind == kind)
        ]
