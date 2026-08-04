"""Cache-stable rendering of the HOT layer.

The rendered block is deterministic: fixed section order, and within each
section memories sorted by descending stability, then id. High-stability
memories change rarely, so the front of the block — the prompt prefix — stays
nearly identical between sessions, which is what prompt caches reward.
"""

from __future__ import annotations

import datetime

from .models import DAY, Memory, MemoryType

#: Prompt caches typically bill cached prefix tokens at ~10% of fresh price.
CACHED_TOKEN_PRICE = 0.10


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _day_stamp(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d")


def _arrival_sort(memories: list[Memory]) -> list[Memory]:
    """Arrival order: append-only rendering, so new entries land at the back.

    Stability decides *which* memories are selected (see standing_block);
    arrival order decides *where* they render. Ordering by current stability
    would reshuffle the block every time reinforcement changes a value —
    exactly the churn a cache-stable prefix cannot afford.
    """
    return sorted(memories, key=lambda m: (m.created_at, m.id))


def render_memory(m: Memory, tension_with: list[str] | None = None) -> str:
    if m.type == MemoryType.PROCEDURAL:
        name = m.payload.get("name", m.id)
        version = m.payload.get("version", 1)
        steps = m.payload.get("steps", [])
        lines = [f"- **{name}** (v{version}): {m.text}"]
        lines += [f"  {i}. {step}" for i, step in enumerate(steps, 1)]
        return "\n".join(lines)
    if m.type == MemoryType.EPISODIC:
        return f"- [{_day_stamp(m.payload.get('when', m.created_at))}] {m.text}"
    if m.type == MemoryType.PROSPECTIVE:
        return f"- when *{m.payload.get('trigger', '?')}*: {m.payload.get('action', m.text)}"
    if m.type == MemoryType.LAW:
        lines = [f"- {m.text} [{m.payload.get('confidence', 0.9):.0%}]"]
        exceptions = m.payload.get("exceptions", [])
        if exceptions:
            lines.append(f"    exception: {exceptions[-1]['note']}")
        for other_text in tension_with or []:
            lines.append(f'    in tension with: "{other_text}"')
        return "\n".join(lines)
    return f"- {m.text}"


def render_pack(memories: list[Memory], tensions: dict[str, list[str]] | None = None) -> str:
    """Render a recalled set of memories as the HOT-layer markdown block.

    Laws render first: they are the most stable memories of all, so they
    belong at the very front of the cacheable prefix.
    """
    laws = [m for m in memories if m.type == MemoryType.LAW]
    stable = [m for m in memories if m.type in (MemoryType.SEMANTIC, MemoryType.PROCEDURAL)]
    recent = [m for m in memories if m.type == MemoryType.EPISODIC]
    intents = [m for m in memories if m.type == MemoryType.PROSPECTIVE]
    tensions = tensions or {}

    parts = ["# MEMORY (WOUF)"]
    if laws:
        parts.append("\n## Guiding laws")
        parts += [render_memory(m, tensions.get(m.id)) for m in _arrival_sort(laws)]
    if stable:
        parts.append("\n## Stable knowledge")
        parts += [render_memory(m) for m in _arrival_sort(stable)]
    if recent:
        parts.append("\n## Recent context")
        parts += [render_memory(m) for m in _arrival_sort(recent)]
    if intents:
        parts.append("\n## Active intentions")
        parts += [render_memory(m) for m in _arrival_sort(intents)]
    return "\n".join(parts)


def stable_prefix_ratio(previous: str, current: str) -> float:
    """Fraction of the current render that is a verbatim prefix of the previous.

    A proxy for prompt-cache hit rate between consecutive sessions.
    """
    if not previous or not current:
        return 0.0
    n = 0
    for a, b in zip(previous, current):
        if a != b:
            break
        n += 1
    return n / len(current)


def estimated_cost_ratio(prefix_ratio: float) -> float:
    """Relative context cost vs. an uncached prompt, given a stable-prefix ratio."""
    return 1.0 - (1.0 - CACHED_TOKEN_PRICE) * prefix_ratio
