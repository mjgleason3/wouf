"""The three systems under test, behind one interface.

Each system hears the same statements exactly once and must assemble the best
context it can for each session, within the same token budget.
"""

from __future__ import annotations

from wouf import Wouf
from wouf.relevance import tokenize
from wouf.render import estimate_tokens

STANDING_BUDGET = 380  # WOUF splits its budget: standing block + query recall


def render_statement(item: dict) -> str:
    """How a statement reads when kept as plain text (the baselines' view)."""
    if item["kind"] in ("procedure", "correction"):
        steps = "; ".join(f"{i}) {s}" for i, s in enumerate(item["steps"], 1))
        return f"- {item['text']}: {steps}"
    return f"- {item['text']}"


class WoufSystem:
    name = "wouf"

    def __init__(self, budget: int):
        self.w = Wouf()
        self.budget = budget
        self.proc_ids: dict[str, str] = {}

    def start_session(self, now: float) -> None:
        self.w.tick(now)

    def state(self, key: str, item: dict, now: float) -> None:
        kind = item["kind"]
        if kind == "fact":
            self.w.remember(
                item["text"], now=now, subject=item.get("subject"), predicate=item.get("predicate")
            )
        elif kind == "event":
            self.w.remember_event(item["text"], now=now, salience=item.get("salience", 0.5))
        elif kind == "procedure":
            self.proc_ids[key] = self.w.remember_procedure(
                item["name"], item["steps"], now=now, description=item["text"]
            )
        elif kind == "intention":
            self.w.intend(item["trigger"], item["action"], now=now)
        elif kind == "law":
            self.w.law(item["text"], now=now, confidence=item.get("confidence", 0.9))
        elif kind == "correction":
            target = item["corrects"]
            new_id = self.w.correct(self.proc_ids[target], now=now, steps=item["steps"])
            self.proc_ids[target] = new_id
            self.proc_ids[key] = new_id

    def noise(self, text: str, now: float) -> None:
        self.w.remember_event(text, now=now, salience=0.2)

    def context(self, query: str, now: float) -> str:
        standing = self.w.standing_block(now=now, budget=STANDING_BUDGET)
        pack = self.w.recall(query, now=now, budget=self.budget - STANDING_BUDGET)
        return f"{standing}\n\n{pack.markdown}"

    def probe_context(self, query: str, now: float) -> str:
        """Query-conditioned retrieval only — what recall() surfaces to answer this."""
        return self.w.recall(query, now=now, budget=self.budget).markdown


class FullContextSystem:
    """Baseline A: keep everything in the prompt, newest-fits sliding window."""

    name = "full-context"

    def __init__(self, budget: int):
        self.lines: list[str] = []
        self.budget = budget

    def start_session(self, now: float) -> None:
        pass

    def state(self, key: str, item: dict, now: float) -> None:
        self.lines.append(render_statement(item))

    def noise(self, text: str, now: float) -> None:
        self.lines.append(f"- {text}")

    def context(self, query: str, now: float) -> str:
        kept: list[str] = []
        spent = 0
        for line in reversed(self.lines):  # newest survive when budget runs out
            cost = estimate_tokens(line)
            if spent + cost > self.budget:
                break
            kept.append(line)
            spent += cost
        return "\n".join(reversed(kept))

    def probe_context(self, query: str, now: float) -> str:
        return self.context(query, now)


class FlatFilesSystem:
    """Baseline B: a notes directory with per-topic files, loaded by name match."""

    name = "flat-files"

    def __init__(self, budget: int):
        self.files: dict[str, list[str]] = {}
        self.order: list[str] = []  # most recently written last
        self.budget = budget

    def start_session(self, now: float) -> None:
        pass

    def _append(self, topic: str, line: str) -> None:
        self.files.setdefault(topic, []).append(line)
        if topic in self.order:
            self.order.remove(topic)
        self.order.append(topic)

    def state(self, key: str, item: dict, now: float) -> None:
        self._append(item["topic"], render_statement(item))

    def noise(self, text: str, now: float) -> None:
        self._append("log", f"- {text}")

    def context(self, query: str, now: float) -> str:
        query_tokens = tokenize(query)
        matched = sorted(
            name
            for name in self.files
            if any(
                q.startswith(f) or f.startswith(q)
                for f in tokenize(name.replace("-", " "))
                for q in query_tokens
                if len(q) >= 4 and len(f) >= 4
            )
        )
        if not matched and self.order:
            matched = [self.order[-1]]  # no file matches: open the latest notes

        parts: list[str] = []
        spent = 0
        for name in matched:
            header = f"## {name}.md"
            spent += estimate_tokens(header)
            if spent > self.budget:
                break
            parts.append(header)
            for line in self.files[name]:
                cost = estimate_tokens(line)
                if spent + cost > self.budget:
                    break
                parts.append(line)
                spent += cost
        return "\n".join(parts)

    def probe_context(self, query: str, now: float) -> str:
        return self.context(query, now)
