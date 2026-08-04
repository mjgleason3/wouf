"""A procedure fails, gets corrected once, and the old version never resurfaces.

Run:  python examples/02_procedural_learning.py
"""

from wouf import Wouf
from wouf.models import DAY

w = Wouf()

v1 = w.remember_procedure(
    "deploy-api",
    ["run the test suite", "build and push the image", "apply the k8s manifests"],
    now=0,
)
print("Day 0  — taught deploy-api v1")

w.feedback(v1, success=True, now=2 * DAY, note="clean deploy")
w.feedback(v1, success=False, now=5 * DAY, note="staging broke: nobody smoke-tested")
print("Day 5  — deploy failed; feedback recorded:",
      w.get(v1).payload["outcomes"][-1]["note"])

v2 = w.correct(
    v1,
    now=5 * DAY,
    steps=["run the test suite", "build and push the image",
           "run smoke tests against staging", "apply the k8s manifests"],
)
print(f"Day 5  — corrected once: v{w.get(v2).payload['version']} supersedes v1\n")

pack = w.recall("how do I deploy the api?", now=6 * DAY)
print("Day 6 — 'how do I deploy the api?'")
print(pack.markdown)

assert "smoke tests" in pack.markdown
assert v1 not in {m.id for m in pack.memories}, "superseded versions stay out of recall"
print("\nOld version is preserved in history (refines edge), but never recalled.")
