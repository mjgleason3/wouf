"""The benchmark scenario: 30 assistant sessions across 45 virtual days.

Every statement is made exactly once (that's the premise under test). Probes
carry a ground-truth set of item keys; an item counts as "in context" when its
needle string appears in the assembled context. Deterministic by construction.
"""

from __future__ import annotations

import random

from wouf.models import DAY

BUDGET = 600  # context token budget per session, all systems

# --- items: everything the user ever states, keyed --------------------------
# kind: fact | event | procedure | intention | correction
# needle: the distinctive substring that proves the item is present in context

ITEMS: dict[str, dict] = {
    "me": {"kind": "fact", "topic": "profile", "text": "My name is Nyx and I lead the platform team"},
    "boss": {"kind": "fact", "topic": "team", "subject": "me", "predicate": "boss",
             "text": "My boss is Priya Raman, VP of Engineering", "needle": "Priya Raman"},
    "daughter": {"kind": "fact", "topic": "family", "text": "My daughter's name is Ada and she is seven",
                 "needle": "Ada"},
    "editor": {"kind": "fact", "topic": "tooling", "text": "My preferred editor is Neovim with LazyVim",
               "needle": "Neovim"},
    "tz": {"kind": "fact", "topic": "profile", "text": "I work in the US/Eastern timezone",
           "needle": "US/Eastern"},
    "company": {"kind": "fact", "topic": "team", "text": "I work at Globex on the platform team",
                "needle": "Globex"},
    "project": {"kind": "fact", "topic": "falcon", "text": "Project Falcon is our payments service, backed by Postgres 16",
                "needle": "Postgres 16"},
    "creds": {"kind": "fact", "topic": "deploy", "text": "Staging credentials live in the 1Password vault named Eng-Staging",
              "needle": "Eng-Staging"},
    "ratelimit": {"kind": "fact", "topic": "falcon", "text": "The public API rate limit is 100 requests per minute per key",
                  "needle": "100 requests per minute"},
    "oncall": {"kind": "fact", "topic": "team", "text": "The on-call rotation swaps every Tuesday at 10am",
               "needle": "every Tuesday at 10am"},
    "dbname": {"kind": "fact", "topic": "falcon", "text": "The production database is falcon-prod on RDS",
               "needle": "falcon-prod"},
    "designdoc": {"kind": "fact", "topic": "falcon", "text": "The Falcon v2 design doc is in Notion under Platform/Falcon",
                  "needle": "Platform/Falcon"},
    "coffee-sam": {"kind": "event", "topic": "log", "salience": 0.7,
                   "text": "Had coffee with Sam from the infra team to talk caching strategy",
                   "needle": "coffee with Sam"},
    "deploy": {"kind": "procedure", "topic": "deploy", "name": "deploy-api",
               "text": "How to deploy the Falcon API",
               "steps": ["run the test suite", "build and push the image to the registry",
                         "apply the k8s manifests", "verify the health dashboard"],
               "needle": "apply the k8s manifests"},
    "weekly": {"kind": "procedure", "topic": "reports", "name": "weekly-report",
               "text": "How to write the weekly report",
               "steps": ["export sprint metrics from Linear", "summarize wins and risks",
                         "send to #eng-weekly by Friday noon"],
               "needle": "export sprint metrics from Linear"},
    "changelog": {"kind": "intention", "topic": "deploy", "trigger": "deploy",
                  "action": "update the changelog before pushing",
                  "text": "When I deploy, remind me to update the changelog before pushing",
                  "needle": "update the changelog"},
    "deploy-v2": {"kind": "correction", "topic": "deploy", "corrects": "deploy",
                  "text": "Correction: deploying the Falcon API now requires running smoke tests against staging after pushing the image",
                  "steps": ["run the test suite", "build and push the image to the registry",
                            "run smoke tests against staging", "apply the k8s manifests",
                            "verify the health dashboard"],
                  "needle": "smoke tests against staging"},
}

for key, item in ITEMS.items():
    item.setdefault("needle", item["text"])

# --- deterministic noise -----------------------------------------------------

_NOISE_TEMPLATES = [
    "CI run {n} flaked on test_billing and passed on retry",
    "Sprint planning ran long, moved retro to {day_name}",
    "Reviewed PR {n} for the ingestion service",
    "Lunch and learn on Rust ownership, {n} people showed up",
    "Pager test fired at {n}:00, acknowledged in two minutes",
    "Interview loop debrief for candidate {n} wrapped up",
    "Dependabot opened {n} bumps across the org",
    "Grafana dashboard {n} needs its alert threshold tuned",
    "Standup note: waiting on security review ticket SEC-{n}",
    "Docs sync: renamed the runbook index page, PR {n}",
]
_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _noise(rng: random.Random, counter: int) -> str:
    template = rng.choice(_NOISE_TEMPLATES)
    return template.format(n=100 + counter, day_name=rng.choice(_DAY_NAMES))


# --- sessions ----------------------------------------------------------------

SESSION_DAYS = [0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18, 20, 21,
                23, 25, 27, 28, 30, 32, 34, 35, 37, 39, 40, 42, 43, 44]

#: day -> item keys stated that day (facts trickle in, stated once)
_SAY_ON_DAY = {
    0: ["me", "boss", "daughter", "editor", "tz", "company", "project", "deploy", "weekly", "changelog"],
    1: ["coffee-sam"],
    2: ["creds"],
    5: ["ratelimit"],
    6: ["oncall"],
    8: ["dbname"],
    11: ["designdoc"],
    12: ["deploy-v2"],
}

#: day -> (probe query, required item keys)
_PROBE_ON_DAY = {
    3: ("who is my boss?", ["boss"]),
    5: ("which editor do I prefer to use?", ["editor"]),
    8: ("walk me through deploying the api", ["deploy", "changelog"]),
    14: ("walk me through deploying the api", ["deploy-v2"]),
    18: ("what is my daughter's name?", ["daughter"]),
    21: ("how do I write the weekly report?", ["weekly"]),
    25: ("where do the staging credentials live?", ["creds"]),
    28: ("what is the api rate limit?", ["ratelimit"]),
    32: ("which company do I work for and who is my boss?", ["company", "boss"]),
    37: ("where is the falcon design doc?", ["designdoc"]),
    40: ("what did I discuss with Sam over coffee?", ["coffee-sam"]),
    44: ("what is my daughter's name and which timezone am I in?", ["daughter", "tz"]),
}


def build_sessions() -> list[dict]:
    """Deterministic session script: say / probe / noise actions per session."""
    rng = random.Random(1234)
    sessions = []
    noise_counter = 0
    for day in SESSION_DAYS:
        actions: list[tuple] = [("say", key) for key in _SAY_ON_DAY.get(day, [])]
        for _ in range(rng.randint(2, 3)):
            noise_counter += 1
            actions.append(("noise", f"noise-{noise_counter}", _noise(rng, noise_counter)))
        if day in _PROBE_ON_DAY:
            query, required = _PROBE_ON_DAY[day]
            actions.append(("probe", query, required))
            session_query = query
        else:
            session_query = "daily briefing on project falcon"
        sessions.append({"day": day, "query": session_query, "actions": actions, "now": day * DAY})
    return sessions
