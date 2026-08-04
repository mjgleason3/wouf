"""The recall pipeline: score -> spread -> fire -> assemble -> reinforce."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import dynamics
from .graph import Graph
from .models import Memory, MemoryType, Tier
from .relevance import Scorer, tokenize
from .render import estimate_tokens, render_memory, render_pack

SEED_COUNT = 5  # top-scoring memories that spread activation
EDGE_RELEVANCE_TRANSFER = 0.6  # fraction of a seed's relevance that flows across an edge
EPISODIC_FOCUS = 5  # sparse focus: max episodic memories in one pack
LAW_FOCUS = 3  # max laws in one pack
NOVELTY_COVERAGE = 0.4  # below this query coverage, law fallback engages
TRIGGER_SIMILARITY = 0.34  # prospective trigger match threshold
HEADER_OVERHEAD_TOKENS = 10


@dataclass
class ContextPack:
    markdown: str
    memories: list[Memory]
    tokens: int
    fired: list[Memory] = field(default_factory=list)
    revived: list[Memory] = field(default_factory=list)
    novel: bool = False  # did the law fallback engage?
    tensions: dict[str, list[str]] = field(default_factory=dict)


def _searchable_text(m: Memory) -> str:
    """What lexical relevance sees: statement plus class-specific payload text."""
    extra = ""
    if m.type == MemoryType.PROCEDURAL:
        extra = " ".join([m.payload.get("name", ""), *m.payload.get("steps", [])])
    elif m.type == MemoryType.PROSPECTIVE:
        extra = " ".join([m.payload.get("trigger", ""), m.payload.get("action", "")])
    return f"{m.text} {extra}".strip()


def recall(
    memories: dict[str, Memory],
    graph: Graph,
    query: str,
    budget: int,
    now: float,
) -> ContextPack:
    active = {
        m.id: m
        for m in memories.values()
        if m.tier != Tier.COLD and not m.payload.get("superseded")
    }
    scorer = Scorer({mid: _searchable_text(m) for mid, m in active.items()})

    relevance = {mid: scorer.score(query, mid) for mid in active}

    # Spreading activation: top seeds energize neighbors and lend them relevance,
    # pulling in related memories that share no keywords with the query.
    seeds = sorted(
        (mid for mid in active if relevance[mid] > 0),
        key=lambda mid: dynamics.score(active[mid], relevance[mid], now),
        reverse=True,
    )[:SEED_COUNT]
    for seed_id in seeds:
        for neighbor_id, _kind, weight in graph.neighbors(seed_id):
            if neighbor_id not in active:
                continue
            dynamics.spread(active[seed_id], active[neighbor_id], weight, now)
            transferred = relevance[seed_id] * weight * EDGE_RELEVANCE_TRANSFER
            relevance[neighbor_id] = max(relevance[neighbor_id], transferred)

    scored = sorted(
        (m for m in active.values() if relevance[m.id] > 0),
        key=lambda m: dynamics.score(m, relevance[m.id], now),
        reverse=True,
    )

    query_tokens = set(tokenize(query))

    # Law gating (inverse): coverage is how much of the query the single best
    # specific memory accounts for. Familiar ground keeps laws out; unmapped
    # territory pulls in the top-confidence laws as priors.
    coverage = 0.0
    if query_tokens:
        for mid, m in active.items():
            if m.type == MemoryType.LAW:
                continue
            overlap = query_tokens & set(scorer.doc_tokens.get(mid, []))
            coverage = max(coverage, len(overlap) / len(query_tokens))
    novel = coverage < NOVELTY_COVERAGE
    forced_laws: list[Memory] = []
    if novel:
        forced_laws = sorted(
            (m for m in active.values() if m.type == MemoryType.LAW),
            key=lambda m: (-m.payload.get("confidence", 0.9), m.created_at, m.id),
        )[:LAW_FOCUS]

    # Prospective memories fire on trigger match, jumping the relevance queue.
    fired = []
    for m in active.values():
        if m.type != MemoryType.PROSPECTIVE or m.payload.get("fired_at"):
            continue
        trigger_tokens = set(tokenize(m.payload.get("trigger", "")))
        if trigger_tokens and (
            trigger_tokens <= query_tokens
            or (len(trigger_tokens & query_tokens) / len(trigger_tokens | query_tokens)) >= TRIGGER_SIMILARITY
        ):
            m.payload["fired_at"] = now
            fired.append(m)

    # Assemble within budget: fired intentions, then best-scored (a law that
    # lexically matches the query competes here and beats generic fallback),
    # then fallback laws to fill remaining law slots on novel ground.
    included: list[Memory] = []
    spent = HEADER_OVERHEAD_TOKENS
    episodic_count = 0
    law_count = 0
    seen: set[str] = set()
    for m in fired + scored + forced_laws:
        if m.id in seen:
            continue
        seen.add(m.id)
        if m.type == MemoryType.EPISODIC and episodic_count >= EPISODIC_FOCUS:
            continue
        if m.type == MemoryType.LAW and law_count >= LAW_FOCUS:
            continue
        cost = estimate_tokens(render_memory(m))
        if spent + cost > budget:
            continue
        included.append(m)
        spent += cost
        if m.type == MemoryType.EPISODIC:
            episodic_count += 1
        elif m.type == MemoryType.LAW:
            law_count += 1

    # Inclusion is use: the energetic loop closes here.
    for m in included:
        dynamics.reinforce(m, now)

    # Laws in declared tension render with the conflict surfaced, not resolved.
    tensions: dict[str, list[str]] = {}
    for a, b in graph.tension_pairs({m.id for m in included}):
        tensions.setdefault(a, []).append(memories[b].text)
        tensions.setdefault(b, []).append(memories[a].text)

    markdown = render_pack(included, tensions)
    return ContextPack(
        markdown=markdown,
        memories=included,
        tokens=estimate_tokens(markdown),
        fired=fired,
        novel=novel,
        tensions=tensions,
    )
