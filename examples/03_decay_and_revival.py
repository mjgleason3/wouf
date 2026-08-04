"""Watch memories decay, strengthen with use, sink to the archive, and revive.

Run:  python examples/03_decay_and_revival.py
"""

from wouf import Wouf
from wouf.dynamics import retrievability
from wouf.models import DAY

w = Wouf()

rehearsed = w.remember("The API rate limit is 100 requests per minute", now=0)
ignored = w.remember_event("Had coffee with Sam to talk caching strategy", now=0, salience=0.7)

print(f"{'day':>4}  {'rehearsed fact':>15}  {'ignored event':>14}")
for day in range(0, 36, 5):
    now = day * DAY
    w.tick(now)
    if day in (10, 20):  # the fact gets used; the event never does
        w.recall("api rate limit", now=now)
    fact = w.get(rehearsed)
    event = w.get(ignored)
    fact_r = f"{retrievability(fact, now):.2f} (S={fact.stability:.0f}d)"
    event_r = f"{retrievability(event, now):.2f}" if event else "archived"
    print(f"{day:>4}  {fact_r:>15}  {event_r:>14}")

print("\nDay 40 — a strong cue probes the archive:")
pack = w.recall("what did Sam and I discuss over coffee?", now=40 * DAY)
print(pack.markdown)
print(f"\nRevived: {[m.text for m in pack.revived]}")
