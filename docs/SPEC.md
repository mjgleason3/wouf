# WOUF Specification

**W**rite **O**nce, **U**se **F**orever — an energetic memory system for LLM agents.

> Say it once. The system handles persistence, relevance, decay, reinforcement,
> and context assembly, so you never have to repeat yourself to the model again —
> unless you're editing it.

This document is the normative design specification for the WOUF prototype.
The README is the tour; this is the blueprint.

---

## 1. Problem

LLM agents forget. Every mitigation in common use trades one failure for another:

| Approach | Failure mode |
|---|---|
| Keep everything in the prompt | Context grows without bound; cost grows linearly with history; eventually truncation silently drops facts |
| Notes in local files | No relevance ranking, no lifecycle — the file either bloats or a human curates it by hand |
| Vector DB / RAG | Retrieval is stateless: nothing strengthens with use, nothing fades, contradictions accumulate, and every session re-pays the token cost of the same immutable facts |

Human memory solves the same problem with an *energetic* design: memories carry
strength, strengthen when used, decay when idle, and associate with each other.
WOUF applies that design to agent memory — and adds one insight unique to LLMs:
**context should be ordered by mutation rate so the prompt prefix stays stable
and the KV cache keeps paying for it** (§6.1).

## 2. Design goals

1. **Write once.** A fact, process, or event is stated exactly once. Repetition is a system failure, measured by the benchmark's *re-statement count*.
2. **Use forever.** Nothing is ever deleted. Cold memories are compressed and archived, and can be revived by cue.
3. **Energetic lifecycle.** Use strengthens; disuse decays. Managed by explicit, inspectable math — not a black box.
4. **Concise memories.** Each memory is a short canonical statement. Long content lives in the payload; the statement is what enters context.
5. **Cache-native context.** The rendered memory block is deterministic and stability-ordered, maximizing prompt-cache (KV-cache) reuse across sessions.
6. **Zero-dependency core.** Pure Python stdlib. Deterministic under an injected clock. Anyone can clone and reproduce every number in the README.

## 3. Memory classes

Five classes, one lifecycle. All classes share the same record shape and decay
physics; they differ in payload, initial stability, and recall behavior.

| Class | Holds | Payload | Initial stability | Special behavior |
|---|---|---|---|---|
| **Episodic** | Timestamped events — what happened | `when`, `salience` | 7 days | Sparse focus: only a salience- and recency-ranked subset is in focus per session |
| **Procedural** | Multi-step processes — how to do things | `steps[]`, `version`, `outcomes` | 21 days | Versioned; `feedback()` and `correct()` refine steps over time, linked by `refines` edges |
| **Semantic** | Concise facts — what is true | `subject`, `predicate` | 30 days | Slowest decay; contradiction detection on write (same subject+predicate, different statement) |
| **Working** | The current session's attention set | — | ephemeral | Not persisted: it *is* the assembled context pack, token-budgeted |
| **Prospective** | Future intentions — trigger → action | `trigger`, `action`, `expires` | until fired/expired | Fires into context when a session's query matches its trigger cue |

### 3.1 Memory record

```python
@dataclass
class Memory:
    id: str            # 8-char content hash
    type: MemoryType   # EPISODIC | PROCEDURAL | SEMANTIC | PROSPECTIVE
    text: str          # concise canonical statement (≲ 200 chars encouraged)
    created_at: float  # epoch seconds (injected clock)
    last_access: float
    stability: float   # S — decay time constant, in days
    activation: float  # A ∈ [0, 1] — short-term energy
    access_count: int
    tier: Tier         # HOT | WARM | COLD
    payload: dict      # class-specific fields (§3)
```

Working memory has no record: it is the output of `recall()` (§5).

## 4. Dynamics — the physics

Time is always an explicit parameter (`now`). The system never reads the wall
clock, which makes every behavior reproducible under a virtual clock.

### 4.1 Retrievability (decay)

Ebbinghaus-style exponential forgetting. For memory *m* at time *t*:

```
R(m, t) = exp( −(t − m.last_access) / m.stability )
```

`R ∈ (0, 1]` is the probability-like ease of retrieval. Stability `S` is the
time constant, in days: a memory with `S = 30` retains `R ≈ 0.72` after 10 idle
days; a memory with `S = 7` drops to `R ≈ 0.24` in the same span.

### 4.2 Reinforcement (the spacing effect)

Whenever a memory is *used* — included in a recalled context pack, or
explicitly reinforced — it is rewarded:

```
S ← S × (1 + α × (1 − R))     # stability grows; α is the learning rate
A ← 1.0                        # activation resets to full
last_access ← now
access_count += 1
```

The `(1 − R)` factor is the spacing effect: rescuing a nearly-forgotten memory
(`R` low) grows stability far more than touching a fresh one (`R ≈ 1`).
Frequently-used memories therefore decay ever more slowly — exactly the
"reduced weight decay" behavior of well-rehearsed human memory. `α` defaults
to 0.6, tunable per class.

### 4.3 Activation (session energy)

Activation is short-term energy with a fast time constant (`τ_A = 0.5 days`):

```
A(m, t) = m.activation × exp( −(t − m.last_access) / τ_A )
```

Activation makes *recently touched* memories easy to surface within and across
adjacent sessions, independent of long-term stability.

### 4.4 Spreading activation

Recalling a memory pumps energy into its graph neighbors:

```
for edge (m → n, weight w):
    A_n ← min(1.0, A_n + spread × w × A_m)      # spread = 0.5, one hop
```

This is how a query about "deploy" also surfaces the semantic fact the deploy
procedure depends on, even when that fact shares no keywords with the query.

### 4.5 Tiering — the archive, not the trash

After each `tick(now)` (decay pass):

| Condition | Transition |
|---|---|
| `R < 0.05` and tier is WARM | → **COLD**: statement compressed to a one-line summary; full record preserved in the archive |
| COLD memory matched by a recall cue | → **WARM** (revival): stability bumped, activation reset — "oh right, *that*" |

Nothing is deleted. *Use forever* is literal.

## 5. Recall pipeline

`recall(query, budget, now)` → `ContextPack`

1. **Score** every non-COLD memory:
   `score = relevance(query, m) × (0.6 · R(m) + 0.3 · A(m) + 0.1 · log1p(access_count))`
   where `relevance` is BM25-lite lexical scoring (stdlib implementation) over the statement text.
2. **Spread**: top-scoring seeds propagate activation to graph neighbors (§4.4); neighbors are rescored with their boosted activation, pulling in related memories that don't lexically match the query.
3. **Fire prospective triggers**: any prospective memory whose trigger cue matches the query is force-included and marked fired.
4. **Assemble** the pack within `budget` tokens (estimated at 4 chars/token), best-scored first, then rendered in cache-stable order (§6.1).
5. **Reinforce** every included memory (§4.2) — inclusion *is* use. This closes the energetic loop: what gets recalled gets stronger.
6. **Probe the archive**: if the query strongly matches a COLD summary, revive it (§4.5).

The returned `ContextPack` has `.markdown` (the renderable block), `.memories`
(the included records), and `.tokens` (estimated cost).

## 6. Storage layers

Three tiers, matched to how LLMs actually consume context:

```
┌─ HOT ────────────────────────────────────────────┐
│ Rendered markdown memory block, stability-ordered │  → pasted into the prompt;
│ deterministic; prefix-stable across sessions      │    KV-cache friendly
├─ WARM ───────────────────────────────────────────┤
│ .wouf/memories.jsonl   one record per line        │  → grep-able, git-friendly,
│ .wouf/edges.jsonl      the graph                  │    human-auditable
│ .wouf/MEMORY.md        rendered human view        │
├─ COLD ───────────────────────────────────────────┤
│ .wouf/archive.jsonl    compressed summaries +     │  → revivable by cue;
│                        full frozen records        │    never deleted
└──────────────────────────────────────────────────┘
```

### 6.1 Cache-stable rendering — order context by mutation rate

The HOT block is rendered deterministically, sections in fixed order, and
memories within each section sorted by **descending stability, then id**:

```markdown
# MEMORY (WOUF)
## Stable knowledge      ← semantic + procedural, most stable first
## Recent context        ← episodic in-focus set
## Active intentions     ← fired prospective memories
```

High-stability memories change rarely — by definition. Sorting them first means
the *front* of the rendered block (and therefore the prompt prefix) is nearly
identical between consecutive sessions, while churn (new events, fresh facts)
accumulates at the *back*. Prompt caches bill cached prefix tokens at ~10% of
the fresh-token price, so prefix stability converts directly into cost:

```
est_cost_ratio = 1 − 0.9 × stable_prefix_ratio
```

The benchmark measures `stable_prefix_ratio` between consecutive sessions for
WOUF's stability ordering vs. naive recency ordering (§8).

## 7. The graph

Typed, weighted edges connect memories across classes:

| Edge | Meaning | Typical endpoints |
|---|---|---|
| `relates_to` | generic association | any ↔ any |
| `depends_on` | needs to be true/known | procedural → semantic |
| `refines` | new version supersedes | procedural v(n+1) → v(n) |
| `contradicts` | mutually exclusive | semantic ↔ semantic |
| `about` | event concerns fact/entity | episodic → semantic |
| `triggers` | intention invokes process | prospective → procedural |

Edges are created explicitly via `link()`, or automatically: on `remember()`,
lexical similarity against existing memories proposes `relates_to` edges above
a threshold; `correct()` on a procedure creates `refines`; contradiction
detection creates `contradicts` and demotes the older fact's stability.

## 8. Benchmark protocol

**Scenario**: 30 simulated assistant sessions across 45 virtual days, driven by
a seeded script. Facts are stated once, early. Procedures are taught, then
corrected mid-stream. Events accrue daily, most of them noise. Probe queries
arrive throughout — each with a ground-truth *required set* of memories that a
competent assistant would need in context to answer.

**Systems under test** (all given the same per-session token budget):

| System | Description |
|---|---|
| **WOUF** | full pipeline as specified |
| **full-context** | every remembered item concatenated, oldest first, truncated to budget — the "just keep it in the prompt" baseline |
| **flat-files** | memories appended to per-topic files; retrieval loads whole files whose names match query keywords — the "notes directory" baseline |

**Metrics**:

1. **Context tokens per session** — cost of the assembled context over time.
2. **Probe F1** — precision/recall of required memories present in context at probe time.
3. **Re-statement count** — probes that fail because a required memory is absent; each failure means the user must repeat themselves. WOUF's design target is ~0.
4. **Stable-prefix ratio** — common prefix between consecutive rendered contexts, and the estimated cost ratio under prompt-cache pricing (§6.1).

All numbers in the README are produced by `benchmarks/run.py` from a fixed seed.

## 9. Public API

```python
from wouf import Wouf

w = Wouf(".wouf")                                   # opens or creates the store

w.remember("Ada is Nyx's daughter", now=t)          # semantic (default)
w.remember_event("Shipped v2.1", now=t, salience=0.8)
w.remember_procedure("deploy-api",
    steps=["run tests", "build image", "push", "migrate", "verify"], now=t)
w.intend(trigger="deploy", action="run smoke tests first", now=t)

pack = w.recall("how do I deploy?", budget=800, now=t)
pack.markdown                                        # → paste into the prompt

w.correct(proc_id, steps=[...], now=t)               # version++, refines edge
w.feedback(proc_id, success=False, note="step 3 failed", now=t)
w.link(a_id, b_id, "depends_on")
w.tick(now=t)                                        # decay + tiering pass
w.save()                                             # flush WARM layer to disk
```

## 10. Non-goals (v0)

- **Embeddings / vector search.** Lexical BM25-lite keeps the core
  dependency-free and the results reproducible; the `relevance()` function is
  the single seam where an embedding scorer would slot in.
- **Native LLM API integration.** The benchmark harness simulates the agent
  loop deterministically. `ContextPack.markdown` is the integration point for
  any real agent.
- **Multi-agent shared memory, concurrency, encryption.** Out of scope for the
  prototype.

## 11. Module map

```
wouf/
  models.py     # Memory, Edge, MemoryType, Tier — data shapes only
  dynamics.py   # retrievability, reinforcement, activation, spreading — pure functions
  graph.py      # edge store, neighbor queries
  relevance.py  # BM25-lite lexical scoring
  recall.py     # the recall pipeline (§5)
  render.py     # cache-stable HOT-layer rendering (§6.1)
  store.py      # WARM/COLD persistence (JSONL + MEMORY.md)
  wouf.py       # the Wouf facade (§9)
```

Each module is importable and testable alone; `wouf.py` is the only module
that composes them.
