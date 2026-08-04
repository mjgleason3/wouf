"""Run the WOUF benchmark: 30 sessions, 3 systems, one honest scoreboard.

Usage:  python -m benchmarks.run
Writes: benchmarks/out/results.json
"""

from __future__ import annotations

import json
from pathlib import Path

from wouf.render import estimate_tokens, estimated_cost_ratio, stable_prefix_ratio

from .scenario import BUDGET, ITEMS, build_sessions
from .systems import FlatFilesSystem, FullContextSystem, WoufSystem

OUT = Path(__file__).parent / "out"


def probe_scores(context: str, required: list[str], stated: set[str]) -> dict:
    present = {k for k in stated if ITEMS[k]["needle"] in context}
    hit = present & set(required)
    missing = sorted(set(required) - present)
    precision = len(hit) / len(present) if present else 0.0
    recall = len(hit) / len(required)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "missing": missing}


def main() -> dict:
    systems = [WoufSystem(BUDGET), FullContextSystem(BUDGET), FlatFilesSystem(BUDGET)]
    sessions = build_sessions()

    stated: set[str] = set()
    restatements = {s.name: 0 for s in systems}
    previous_context = {s.name: "" for s in systems}
    session_rows, probe_rows = [], []

    for index, session in enumerate(sessions):
        now = session["now"]
        for system in systems:
            system.start_session(now)

        for action in session["actions"]:
            if action[0] == "say":
                key = action[1]
                stated.add(key)
                for system in systems:
                    system.state(key, ITEMS[key], now)
            elif action[0] == "noise":
                for system in systems:
                    system.noise(action[2], now)
            elif action[0] == "probe":
                _, query, required = action
                row = {"day": session["day"], "query": query, "required": required, "systems": {}}
                for system in systems:
                    scores = probe_scores(system.probe_context(query, now), required, stated)
                    # every miss forces the user to say it again — the failure
                    # WOUF is named after
                    for key in scores["missing"]:
                        system.state(key, ITEMS[key], now)
                        restatements[system.name] += 1
                    row["systems"][system.name] = scores
                probe_rows.append(row)

        # Session-level cost and cache metrics use a fixed daily query so the
        # measurement isolates how the standing prompt evolves, not probe churn.
        row = {"day": session["day"], "session": index + 1, "tokens": {}, "prefix": {}}
        for system in systems:
            context = system.context("daily briefing on project falcon", now)
            row["tokens"][system.name] = estimate_tokens(context)
            row["prefix"][system.name] = stable_prefix_ratio(previous_context[system.name], context)
            previous_context[system.name] = context
        session_rows.append(row)

    names = [s.name for s in systems]
    prefix_avgs = {  # skip session 1: there is no previous prompt to cache against
        n: sum(r["prefix"][n] for r in session_rows[1:]) / (len(session_rows) - 1) for n in names
    }
    summary = {
        "budget": BUDGET,
        "sessions": len(session_rows),
        "probes": len(probe_rows),
        "avg_tokens": {n: sum(r["tokens"][n] for r in session_rows) / len(session_rows) for n in names},
        "avg_precision": {n: sum(p["systems"][n]["precision"] for p in probe_rows) / len(probe_rows) for n in names},
        "avg_recall": {n: sum(p["systems"][n]["recall"] for p in probe_rows) / len(probe_rows) for n in names},
        "avg_f1": {n: sum(p["systems"][n]["f1"] for p in probe_rows) / len(probe_rows) for n in names},
        "restatements": restatements,
        "avg_prefix_ratio": prefix_avgs,
        "est_context_cost_ratio": {n: estimated_cost_ratio(prefix_avgs[n]) for n in names},
    }

    results = {"summary": summary, "sessions": session_rows, "probes": probe_rows}
    OUT.mkdir(exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    print(f"{'':<14}{'wouf':>10}{'full-context':>14}{'flat-files':>12}")
    for label, metric, fmt in [
        ("avg tokens", "avg_tokens", "{:.0f}"),
        ("precision", "avg_precision", "{:.2f}"),
        ("recall", "avg_recall", "{:.2f}"),
        ("F1", "avg_f1", "{:.2f}"),
        ("re-statements", "restatements", "{}"),
        ("prefix ratio", "avg_prefix_ratio", "{:.2f}"),
        ("cost ratio", "est_context_cost_ratio", "{:.2f}"),
    ]:
        values = summary[metric]
        print(f"{label:<14}" + "".join(
            f"{fmt.format(values[n]):>{w}}" for n, w in zip(names, (10, 14, 12))
        ))
    return results


if __name__ == "__main__":
    main()
