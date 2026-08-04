"""The Wouf facade: the only module that composes the others.

    w = Wouf(".wouf")
    w.remember("Ada is Nyx's daughter", now=t)
    pack = w.recall("who is Ada?", budget=800, now=t)
    pack.markdown  # -> paste into the prompt
"""

from __future__ import annotations

from pathlib import Path

from . import dynamics, recall as recall_mod
from .graph import Graph
from .models import INITIAL_STABILITY, EdgeKind, Memory, MemoryType, Tier
from .recall import ContextPack
from .relevance import similarity, tokenize
from .store import Store

AUTO_LINK_SIMILARITY = 0.25
AUTO_LINK_MAX = 3
SUMMARY_LENGTH = 72
REVIVAL_OVERLAP = 2  # content tokens shared with a query that revive a COLD memory
CONTRADICTION_DEMOTION = 0.2


class Wouf:
    def __init__(self, path: str | Path | None = None):
        self.store = Store(path) if path else None
        self.memories: dict[str, Memory] = {}
        self.graph = Graph()
        self.archive: list[dict] = []
        if self.store and self.store.exists():
            self.memories, self.graph, self.archive = self.store.load()

    # ------------------------------------------------------------------ write

    def remember(
        self,
        text: str,
        now: float,
        type: MemoryType = MemoryType.SEMANTIC,
        subject: str | None = None,
        predicate: str | None = None,
        **payload,
    ) -> str:
        """Store a concise statement once. Returns the memory id."""
        if subject:
            payload["subject"] = subject
        if predicate:
            payload["predicate"] = predicate
        m = Memory.new(text, type, now, payload)
        if subject and predicate:
            self._detect_contradiction(m, now)
        self.memories[m.id] = m
        self._auto_link(m)
        return m.id

    def remember_event(self, text: str, now: float, salience: float = 0.5, when: float | None = None) -> str:
        return self.remember(
            text, now, type=MemoryType.EPISODIC, salience=salience, when=when if when is not None else now
        )

    def remember_procedure(
        self, name: str, steps: list[str], now: float, description: str | None = None
    ) -> str:
        return self.remember(
            description or f"How to {name}",
            now,
            type=MemoryType.PROCEDURAL,
            name=name,
            steps=steps,
            version=1,
            outcomes=[],
        )

    def intend(
        self, trigger: str, action: str, now: float, expires: float | None = None, once: bool = True
    ) -> str:
        return self.remember(
            f"when {trigger}: {action}",
            now,
            type=MemoryType.PROSPECTIVE,
            trigger=trigger,
            action=action,
            expires=expires,
            once=once,
        )

    def link(self, a: str, b: str, kind: str | EdgeKind = EdgeKind.RELATES_TO, weight: float = 1.0) -> None:
        self.graph.link(a, b, EdgeKind(kind), weight)

    # ------------------------------------------------------------------ read

    def recall(self, query: str, now: float, budget: int = 800) -> ContextPack:
        revived = self._probe_archive(query, now)
        pack = recall_mod.recall(self.memories, self.graph, query, budget, now)
        pack.revived = revived
        for m in pack.fired:
            if m.payload.get("once", True):
                self._archive_memory(m, now, reason="fired")
        return pack

    def get(self, mem_id: str) -> Memory | None:
        return self.memories.get(mem_id)

    # ------------------------------------------------------------ procedural

    def correct(
        self,
        proc_id: str,
        now: float,
        steps: list[str] | None = None,
        text: str | None = None,
    ) -> str:
        """Supersede a procedure with a corrected version. Returns the new id."""
        old = self.memories[proc_id]
        payload = dict(old.payload)
        payload["version"] = old.payload.get("version", 1) + 1
        payload["steps"] = steps if steps is not None else old.payload.get("steps", [])
        payload["outcomes"] = []
        new = Memory.new(text or old.text, old.type, now, payload)
        # the new version inherits the old one's earned stability
        new.stability = max(new.stability, old.stability)
        self.memories[new.id] = new
        self.graph.link(new.id, old.id, EdgeKind.REFINES)
        for neighbor_id, kind, weight in self.graph.neighbors(old.id):
            if neighbor_id != new.id:
                self.graph.link(new.id, neighbor_id, kind, weight)
        old.payload["superseded"] = True
        return new.id

    def feedback(self, proc_id: str, success: bool, now: float, note: str = "") -> None:
        m = self.memories[proc_id]
        m.payload.setdefault("outcomes", []).append({"when": now, "success": success, "note": note})
        dynamics.reinforce(m, now)  # an outcome is attention, pass or fail

    # ------------------------------------------------------------- lifecycle

    def tick(self, now: float) -> list[str]:
        """Decay pass: archive what has faded, expire stale intentions."""
        archived = []
        for m in list(self.memories.values()):
            expired = (
                m.type == MemoryType.PROSPECTIVE
                and m.payload.get("expires") is not None
                and now > m.payload["expires"]
            )
            faded = dynamics.retrievability(m, now) < dynamics.ARCHIVE_THRESHOLD
            if m.payload.get("superseded") or expired or faded:
                self._archive_memory(m, now, reason="expired" if expired else "decayed")
                archived.append(m.id)
        return archived

    def save(self) -> None:
        if self.store:
            self.store.save(self.memories, self.graph, self.archive)

    # -------------------------------------------------------------- internal

    def _auto_link(self, new: Memory) -> None:
        candidates = []
        for other in self.memories.values():
            if other.id == new.id:
                continue
            sim = similarity(new.text, other.text)
            if sim >= AUTO_LINK_SIMILARITY:
                candidates.append((sim, other.id))
        for sim, other_id in sorted(candidates, reverse=True)[:AUTO_LINK_MAX]:
            self.graph.link(new.id, other_id, EdgeKind.RELATES_TO, weight=min(1.0, 2 * sim))

    def _detect_contradiction(self, new: Memory, now: float) -> None:
        for old in self.memories.values():
            if (
                old.type == MemoryType.SEMANTIC
                and old.payload.get("subject") == new.payload["subject"]
                and old.payload.get("predicate") == new.payload["predicate"]
                and old.text != new.text
                and not old.payload.get("superseded")
            ):
                self.graph.link(new.id, old.id, EdgeKind.CONTRADICTS)
                old.stability *= CONTRADICTION_DEMOTION
                old.payload["superseded"] = True

    def _archive_memory(self, m: Memory, now: float, reason: str) -> None:
        self.archive.append(
            {
                "id": m.id,
                "summary": m.text[:SUMMARY_LENGTH],
                "archived_at": now,
                "reason": reason,
                "record": m.to_dict(),
            }
        )
        self.memories.pop(m.id, None)

    def _probe_archive(self, query: str, now: float) -> list[Memory]:
        """Revive COLD memories strongly cued by the query. 'Oh right — *that*.'"""
        query_tokens = set(tokenize(query))
        revived = []
        for entry in list(self.archive):
            if entry["reason"] == "fired" or entry["record"]["payload"].get("superseded"):
                continue  # spent intentions and replaced versions stay archived
            overlap = query_tokens & set(tokenize(entry["record"]["text"]))
            if len(overlap) >= REVIVAL_OVERLAP:
                m = Memory.from_dict(entry["record"])
                m.tier = Tier.WARM
                m.payload.pop("superseded", None)
                m.stability = max(m.stability, INITIAL_STABILITY[m.type] * 0.5)
                dynamics.reinforce(m, now)
                self.memories[m.id] = m
                self.archive.remove(entry)
                revived.append(m)
        return revived
