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


def _stable_sort(memories: list[Memory]) -> list[Memory]:
    return sorted(memories, key=lambda m: (-m.stability, m.id))


def render_memory(m: Memory) -> str:
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
    return f"- {m.text}"


def render_pack(memories: list[Memory]) -> str:
    """Render a recalled set of memories as the HOT-layer markdown block."""
    stable = [m for m in memories if m.type in (MemoryType.SEMANTIC, MemoryType.PROCEDURAL)]
    recent = [m for m in memories if m.type == MemoryType.EPISODIC]
    intents = [m for m in memories if m.type == MemoryType.PROSPECTIVE]

    parts = ["# MEMORY (WOUF)"]
    if stable:
        parts.append("\n## Stable knowledge")
        parts += [render_memory(m) for m in _stable_sort(stable)]
    if recent:
        parts.append("\n## Recent context")
        parts += [render_memory(m) for m in _stable_sort(recent)]
    if intents:
        parts.append("\n## Active intentions")
        parts += [render_memory(m) for m in _stable_sort(intents)]
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
