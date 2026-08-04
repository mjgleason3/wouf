"""Data shapes for WOUF memories and graph edges. No behavior lives here."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum

DAY = 86400.0  # seconds


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"
    SEMANTIC = "semantic"
    LAW = "law"
    PROSPECTIVE = "prospective"


class Tier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


#: Initial stability (decay time constant) per class, in days.
INITIAL_STABILITY = {
    MemoryType.EPISODIC: 7.0,
    MemoryType.PROCEDURAL: 21.0,
    MemoryType.SEMANTIC: 30.0,
    MemoryType.LAW: 365.0,  # laws barely decay; their truth is tracked by confidence
    MemoryType.PROSPECTIVE: 60.0,  # intentions persist until fired or expired
}


class EdgeKind(str, Enum):
    RELATES_TO = "relates_to"
    DEPENDS_ON = "depends_on"
    REFINES = "refines"
    CONTRADICTS = "contradicts"
    ABOUT = "about"
    TRIGGERS = "triggers"
    TENSION = "tension"  # laws that conflict in specific situations


@dataclass
class Edge:
    src: str
    dst: str
    kind: EdgeKind
    weight: float = 1.0

    def to_dict(self) -> dict:
        return {"src": self.src, "dst": self.dst, "kind": self.kind.value, "weight": self.weight}

    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        return cls(src=d["src"], dst=d["dst"], kind=EdgeKind(d["kind"]), weight=d["weight"])


@dataclass
class Memory:
    id: str
    type: MemoryType
    text: str
    created_at: float
    last_access: float  # clock for long-term decay (retrievability)
    stability: float  # days
    activation: float = 1.0
    activation_at: float = 0.0  # clock for short-term activation decay
    access_count: int = 0
    tier: Tier = Tier.WARM
    payload: dict = field(default_factory=dict)

    @classmethod
    def new(cls, text: str, type: MemoryType, now: float, payload: dict | None = None) -> "Memory":
        digest = hashlib.sha256(f"{type.value}:{text}:{now}".encode()).hexdigest()[:8]
        return cls(
            id=digest,
            type=type,
            text=text,
            created_at=now,
            last_access=now,
            stability=INITIAL_STABILITY[type],
            activation_at=now,
            payload=payload or {},
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "text": self.text,
            "created_at": self.created_at,
            "last_access": self.last_access,
            "stability": self.stability,
            "activation": self.activation,
            "activation_at": self.activation_at,
            "access_count": self.access_count,
            "tier": self.tier.value,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Memory":
        return cls(
            id=d["id"],
            type=MemoryType(d["type"]),
            text=d["text"],
            created_at=d["created_at"],
            last_access=d["last_access"],
            stability=d["stability"],
            activation=d["activation"],
            activation_at=d.get("activation_at", d["last_access"]),
            access_count=d["access_count"],
            tier=Tier(d["tier"]),
            payload=d["payload"],
        )
