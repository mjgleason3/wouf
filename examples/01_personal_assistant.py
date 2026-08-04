"""Say it once on Monday; the assistant still knows it weeks later.

Run:  python examples/01_personal_assistant.py
"""

from wouf import Wouf
from wouf.models import DAY


def show(title: str, body: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}\n{body}")


w = Wouf()

# --- Monday, day 0: say everything exactly once -----------------------------
w.remember("My daughter's name is Ada and she is seven", now=0)
w.remember("My boss is Priya Raman, VP of Engineering", now=0)
w.remember("Staging credentials live in the 1Password vault Eng-Staging", now=0)
w.remember_procedure(
    "deploy-api",
    ["run the test suite", "build and push the image", "apply the k8s manifests", "verify the dashboard"],
    now=0,
)
w.intend(trigger="deploy", action="update the changelog before pushing", now=0)

# --- three weeks of unrelated chatter ---------------------------------------
for day in range(1, 21):
    w.remember_event(f"Standup note for day {day}, nothing memorable", now=day * DAY, salience=0.1)
    w.tick(now=day * DAY)

# --- day 21: never repeated, still there ------------------------------------
pack = w.recall("what's my daughter's name?", now=21 * DAY)
show("Day 21 — 'what's my daughter's name?'", pack.markdown)

pack = w.recall("time to deploy the api", now=22 * DAY)
show("Day 22 — 'time to deploy the api' (note the intention firing)", pack.markdown)

show("Day 22 — the standing block (pin this in the system prompt)", w.standing_block(now=22 * DAY))
