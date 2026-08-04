"""Laws: priors for unmapped territory.

Drop an agent into a situation it has zero specific memory about, and laws —
cross-domain tendencies like "water flows downhill" — step in as guidance.
Give it a familiar task, and the laws politely stay out of the way.

Run:  python examples/04_laws.py
"""

from wouf import Wouf
from wouf.models import DAY

w = Wouf()

# --- a store full of day-job specifics --------------------------------------
w.remember("Project Falcon is our payments service, backed by Postgres", now=0)
w.remember_procedure("deploy-api", ["run tests", "push image", "verify dashboard"], now=0)

# --- and a small body of law ------------------------------------------------
water = w.law("Water flows downhill", now=0, confidence=0.95)
reversible = w.law("When uncertain, prefer the action that is easiest to undo", now=60, confidence=0.9)
window = w.law("Strike while the window of opportunity is open", now=120, confidence=0.85)
moss = w.law("Moss favors the shaded side of trees", now=180, confidence=0.8)
w.link(reversible, window, "tension")  # they collide in real crises — say so

print("=" * 64)
print("Novel ground: 'lost in an unfamiliar forest, need to find water'")
print("=" * 64)
pack = w.recall("lost in an unfamiliar forest, need to find water", now=1 * DAY)
print(pack.markdown)
print(f"\n(novel situation: {pack.novel} — laws stepped in as priors)")

print()
print("=" * 64)
print("Familiar ground: 'how do I deploy the api?'")
print("=" * 64)
pack = w.recall("how do I deploy the api?", now=1 * DAY)
print(pack.markdown)
print(f"\n(novel situation: {pack.novel} — specific memory covers it, no laws)")

print()
print("=" * 64)
print("Crisis with no runbook — two laws collide, tension is surfaced")
print("=" * 64)
pack = w.recall("unprecedented production emergency, no runbook for this", now=2 * DAY)
print(pack.markdown)

# --- laws are managed, not immutable ----------------------------------------
w.refute(moss, now=3 * DAY, note="dense canopy: moss grew on every side")
print()
print("=" * 64)
print("After refuting the moss law once (exception now travels with it)")
print("=" * 64)
pack = w.recall("moss on the trees — which way is north?", now=4 * DAY)
print(pack.markdown)
