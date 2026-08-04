<div align="center">

# 🐕 WOUF

### **W**rite **O**nce, **U**se **F**orever

*An energetic memory system for LLM agents — say it once, and the model never needs it repeated.*

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![zero dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)
![tests](https://img.shields.io/badge/tests-27%20passing-brightgreen)
![license MIT](https://img.shields.io/badge/license-MIT-lightgrey)

</div>

LLM agents forget. Keeping everything in the prompt gets expensive and silently truncates; notes-in-files have no ranking or lifecycle; vector RAG is stateless — nothing strengthens, nothing fades, contradictions pile up. WOUF treats memory the way brains do: as an **energetic system** where memories carry strength, *use* reinforces, *disuse* decays, and related memories pull each other into focus. And it adds one insight unique to LLMs: **order context by mutation rate, so the prompt prefix stays stable and the KV cache keeps paying for it.**

On a 30-session benchmark against the two default strategies (details below):

| | 🐕 WOUF | full-context | flat-files |
|---|---:|---:|---:|
| Times the user had to **repeat themselves** | **0** | 10 | 9 |
| Probe recall (needed memory was in context) | **1.00** | 0.33 | 0.42 |
| Effective context tokens / session¹ | **127** | 392 | 8² |

¹ after prompt-cache discount &nbsp;&nbsp;² cheap because it retrieves almost nothing — it misses 58% of probes

---

## How it works

```mermaid
flowchart LR
    subgraph write ["say it once"]
        A["remember()<br/>remember_event()<br/>remember_procedure()<br/>intend()"]
    end
    subgraph memory ["five memory classes"]
        E[episodic]
        P[procedural]
        S[semantic]
        F[prospective]
    end
    subgraph physics ["energetic dynamics"]
        D["decay · reinforcement<br/>spreading activation"]
    end
    subgraph tiers ["storage tiers"]
        HOT["HOT — cache-stable<br/>prompt block"]
        WARM["WARM — JSONL<br/>+ MEMORY.md"]
        COLD["COLD — archive,<br/>revivable by cue"]
    end
    W["working memory<br/>= the context pack"]
    A --> memory
    memory <--> D
    D --> tiers
    HOT --> W
    W -->|"recall() reinforces"| D
```

Five classes, one lifecycle — all share the same decay physics, differing in payload and initial stability:

| Class | Holds | Behavior |
|---|---|---|
| 🕐 **Episodic** | timestamped events | sparse focus — only a salient subset in context per session |
| 🔧 **Procedural** | multi-step processes | versioned; corrections supersede, history preserved via `refines` edges |
| 💡 **Semantic** | concise facts | slowest decay; contradictions detected and demoted on write |
| 🎯 **Prospective** | trigger → action intentions | fire into context when a session matches the trigger |
| ⚡ **Working** | current attention set | ephemeral — it *is* the token-budgeted context pack |

A typed graph (`depends_on`, `refines`, `contradicts`, `about`, `triggers`) connects memories across classes, so recalling the deploy procedure also surfaces the credentials fact it depends on — even with zero keyword overlap.

## The physics

Every memory has **stability** *S* (long-term strength, in days) and **activation** *A* (short-term energy). Retrievability follows the Ebbinghaus curve, and every use strengthens:

```text
R = exp(−Δt / S)                      # forgetting curve
S ← S × (1 + α·(1−R))   on use       # spacing effect: rescuing a fading
                                      #   memory teaches the most
```

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/decay_dark.svg">
  <img alt="Retrievability over 35 days: a fact recalled twice decays ever slower, an unused fact slides toward the archive threshold" src="docs/assets/decay_light.svg" width="100%">
</picture>

Memories that fade below threshold aren't deleted — they're compressed into a **COLD archive** and revive on a strong cue (*"what did Sam and I discuss over coffee?"* — even months later). Write once, **use forever**.

## The cache trick

The rendered memory block is deterministic: **stability selects, arrival orders.** Long-lived memories fill the front of the block and new churn appends at the back — so the prompt prefix barely changes between sessions, which is exactly what prompt caches bill ~90% less for. In the benchmark, WOUF's standing block kept a **0.74 stable-prefix ratio** between sessions (vs 0.28 for a sliding window), cutting effective context cost to about a third.

## Benchmark

Thirty simulated assistant sessions across 45 virtual days: facts stated **once**, procedures taught then corrected mid-stream, daily noise accruing, and 12 probe queries checking whether the memory each answer *needs* is actually in context. Same 600-token budget for all three systems. Every miss forces the user to repeat themselves — the failure WOUF is named after.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/quality_dark.svg">
  <img alt="Grouped bars: WOUF recall 1.00, precision 0.60, F1 0.71 — far ahead of full-context (F1 0.06) and flat-files (F1 0.30)" src="docs/assets/quality_light.svg" width="100%">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/tokens_dark.svg">
  <img alt="Context tokens per session: full-context grows until it saturates the 600-token budget, WOUF plateaus around 400, flat-files stays under 100" src="docs/assets/tokens_light.svg" width="100%">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/cost_dark.svg">
  <img alt="Scatter of probe recall versus effective cost: WOUF sits in the cheap-and-reliable corner with zero re-statements" src="docs/assets/cost_light.svg" width="100%">
</picture>

Reproduce every number and chart (fixed seed, no API keys):

```bash
python -m benchmarks.run     # metrics table + benchmarks/out/results.json
python -m benchmarks.charts  # regenerates docs/assets/*.svg
```

## Quickstart

```bash
git clone <this-repo> && cd wouf
pip install -e .             # pure stdlib — no dependencies
```

```python
from wouf import Wouf
import time

w = Wouf(".wouf")            # WARM layer: human-readable JSONL + MEMORY.md
now = time.time()

# say it once
w.remember("My daughter's name is Ada", now=now)
w.remember_procedure("deploy-api",
    ["run tests", "build image", "run smoke tests", "apply manifests"], now=now)
w.intend(trigger="deploy", action="update the changelog first", now=now)

# ...weeks later, in any session:
pack = w.recall("time to deploy", now=time.time(), budget=800)
print(pack.markdown)          # → paste into the prompt; recall reinforces

print(w.standing_block(now))  # → cache-stable preamble to pin in the system prompt
w.tick(now); w.save()         # decay pass + persist
```

`ContextPack.markdown` is the integration seam for any agent framework — WOUF never calls a model itself.

## Examples

| Script | What it shows |
|---|---|
| [`examples/01_personal_assistant.py`](examples/01_personal_assistant.py) | facts stated Monday, still in context three weeks later; an intention firing on "time to deploy" |
| [`examples/02_procedural_learning.py`](examples/02_procedural_learning.py) | a deploy fails → one correction → v2 supersedes, v1 preserved but never recalled |
| [`examples/03_decay_and_revival.py`](examples/03_decay_and_revival.py) | rehearsed vs ignored memories, archival, and revival by cue |

```text
 day   rehearsed fact   ignored event
   0     1.00 (S=30d)            1.00
  10     1.00 (S=35d)            0.24      ← recall boosted stability
  20     1.00 (S=40d)            0.06
  25     0.88 (S=40d)        archived      ← nothing is deleted
                                             ...day 40: revived by cue
```

## Project layout

```text
wouf/          the package — models, dynamics, graph, relevance, recall, render, store, facade
tests/         27 tests: physics, recall pipeline, lifecycle, persistence, cache stability
benchmarks/    the 30-session scenario, 3 systems, metrics + chart generation
examples/      three runnable demos
docs/SPEC.md   the full design specification
```

Design details — the recall scoring formula, tiering thresholds, edge semantics, benchmark protocol — live in **[docs/SPEC.md](docs/SPEC.md)**.

## License

MIT
