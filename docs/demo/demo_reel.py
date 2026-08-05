"""The WOUF demo reel — a paced terminal walkthrough for the README clip.

Runs the real library. Regenerate the recording with:  vhs docs/demo/demo.tape
Set WOUF_DEMO_SPEED=0 to run instantly (useful for testing).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from wouf import Wouf
from wouf.models import DAY

SPEED = float(os.environ.get("WOUF_DEMO_SPEED", "1"))

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, BLUE = "\033[36m", "\033[32m", "\033[33m", "\033[34m"


def pause(seconds: float) -> None:
    time.sleep(seconds * SPEED)


def typewriter(text: str, per_char: float = 0.011) -> None:
    for char in text:
        print(char, end="", flush=True)
        time.sleep(per_char * SPEED)
    print()


def heading(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{text}{RESET}")
    pause(0.9)


def stored(note: str) -> None:
    print(f"{DIM}  ✓ {note}{RESET}")
    pause(0.55)


def block(markdown: str) -> None:
    pause(0.4)
    for line in markdown.splitlines():
        if line.startswith("#"):
            print(f"  {BOLD}{BLUE}{line}{RESET}")
        elif line.strip().startswith(("exception:", "in tension with:")):
            print(f"  {YELLOW}{line}{RESET}")
        else:
            print(f"  {line}")
        time.sleep(0.05 * SPEED)
    pause(1.6)


w = Wouf()

print(f"{BOLD}🐕 WOUF — Write Once, Use Forever{RESET}")
print(f"{DIM}An energetic memory system for LLM agents. Say it once.{RESET}")
pause(1.6)

heading("Day 0 — say it once")
typewriter('>>> w.remember("My daughter\'s name is Ada")')
w.remember("My daughter's name is Ada", now=0)
stored("semantic · stability 30d")
typewriter('>>> w.remember_procedure("deploy-api", ["run tests", "build image",')
typewriter('...     "run smoke tests against staging", "apply the k8s manifests"])')
w.remember_procedure(
    "deploy-api",
    ["run tests", "build image", "run smoke tests against staging", "apply the k8s manifests"],
    now=0,
)
stored("procedural · versioned")
typewriter('>>> w.intend(trigger="deploy", action="update the changelog first")')
w.intend(trigger="deploy", action="update the changelog first", now=0)
stored("prospective · armed")
typewriter('>>> w.law("When uncertain, prefer the action that is easiest to undo")')
w.law("When uncertain, prefer the action that is easiest to undo", now=60, confidence=0.9)
stored("law · confidence 90%")

heading("Three weeks of unrelated work…")
for day in range(1, 22):
    w.remember_event(f"standup note, day {day}", now=day * DAY, salience=0.1)
    w.tick(now=day * DAY)
    print(f"\r{DIM}  day {day:>2} · {day} noise events accrued, nothing repeated{RESET}",
          end="", flush=True)
    time.sleep(0.09 * SPEED)
print()

heading('Day 21 — "what\'s my daughter\'s name?"')
pack = w.recall("what's my daughter's name?", now=21 * DAY)
block(pack.markdown)

heading('Day 22 — "time to deploy the api"')
pack = w.recall("time to deploy the api", now=22 * DAY)
block(pack.markdown)
print(f"{GREEN}  ⚡ the intention fired — once, exactly when it mattered{RESET}")
pause(1.6)

heading('Day 23 — novel ground: "vendor outage nobody has seen before"')
pack = w.recall("vendor outage nobody has seen before, where do I start?", now=23 * DAY)
block(pack.markdown)
print(f"{GREEN}  ⚖ no specific memory covers it → laws step in as priors{RESET}")
pause(2.0)

print(f"\n{BOLD}Benchmark, 30 sessions vs full-context & flat-files:{RESET}")
print(f"  {GREEN}0 re-statements{RESET} · probe recall {GREEN}1.00{RESET} · "
      f"{GREEN}~3×{RESET} cheaper context via cache-stable prefixes")
print(f"\n{DIM}github.com/mjgleason3/wouf{RESET}")
pause(3.0)
