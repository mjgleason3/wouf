"""The physics of WOUF memory: decay, reinforcement, activation, spreading.

Every function takes time as an explicit parameter. Nothing here reads the
wall clock, so all behavior is reproducible under a virtual clock.
"""

from __future__ import annotations

import math

from .models import DAY, Memory

ALPHA = 0.6  # reinforcement learning rate (spacing-effect gain)
TAU_ACTIVATION = 0.5  # activation time constant, days
SPREAD_RATE = 0.5  # fraction of activation pushed across an edge
ARCHIVE_THRESHOLD = 0.05  # retrievability below this -> COLD


def retrievability(m: Memory, now: float) -> float:
    """Ebbinghaus forgetting curve: R = exp(-elapsed / stability)."""
    elapsed_days = max(0.0, now - m.last_access) / DAY
    return math.exp(-elapsed_days / m.stability)


def activation(m: Memory, now: float) -> float:
    """Short-term energy, decaying with a fast time constant."""
    elapsed_days = max(0.0, now - m.activation_at) / DAY
    return m.activation * math.exp(-elapsed_days / TAU_ACTIVATION)


def reinforce(m: Memory, now: float, alpha: float = ALPHA) -> None:
    """Reward a memory for being used.

    The (1 - R) factor is the spacing effect: rescuing a nearly-forgotten
    memory grows stability far more than touching a fresh one.
    """
    r = retrievability(m, now)
    m.stability *= 1.0 + alpha * (1.0 - r)
    m.activation = 1.0
    m.activation_at = now
    m.last_access = now
    m.access_count += 1


def spread(source: Memory, target: Memory, weight: float, now: float) -> None:
    """Pump activation from a recalled memory into a graph neighbor.

    Spreading energizes the neighbor's short-term clock only; its long-term
    forgetting curve (last_access / stability) is untouched.
    """
    energy = SPREAD_RATE * weight * activation(source, now)
    target.activation = min(1.0, activation(target, now) + energy)
    target.activation_at = now


def score(m: Memory, relevance: float, now: float) -> float:
    """Combined recall score: lexical relevance gated by memory energy."""
    energy = 0.6 * retrievability(m, now) + 0.3 * activation(m, now) + 0.1 * math.log1p(m.access_count)
    return relevance * energy
