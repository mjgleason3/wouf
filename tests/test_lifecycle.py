from wouf import EdgeKind, MemoryType, Wouf
from wouf.models import DAY, Tier


def test_contradiction_demotes_and_supersedes_old_fact():
    w = Wouf()
    old = w.remember("Nyx works at Initech", now=0.0, subject="nyx", predicate="employer")
    new = w.remember("Nyx works at Globex", now=1 * DAY, subject="nyx", predicate="employer")
    assert w.get(old).payload["superseded"]
    kinds = {e.kind for e in w.graph.edges_of(new)}
    assert EdgeKind.CONTRADICTS in kinds
    pack = w.recall("where does Nyx work?", now=2 * DAY)
    assert new in {m.id for m in pack.memories}
    assert old not in {m.id for m in pack.memories}


def test_correct_versions_procedure_and_recall_prefers_new():
    w = Wouf()
    v1 = w.remember_procedure("deploy-api", ["run tests", "push", "verify"], now=0.0)
    v2 = w.correct(v1, now=5 * DAY, steps=["run tests", "run smoke tests", "push", "verify"])
    assert w.get(v2).payload["version"] == 2
    kinds = {e.kind for e in w.graph.edges_of(v2)}
    assert EdgeKind.REFINES in kinds
    pack = w.recall("how do I deploy the api?", now=6 * DAY)
    ids = {m.id for m in pack.memories}
    assert v2 in ids and v1 not in ids
    assert "smoke tests" in pack.markdown


def test_feedback_records_outcomes():
    w = Wouf()
    proc = w.remember_procedure("weekly-report", ["gather metrics", "write summary"], now=0.0)
    w.feedback(proc, success=False, now=1 * DAY, note="metrics dashboard moved")
    outcomes = w.get(proc).payload["outcomes"]
    assert len(outcomes) == 1 and outcomes[0]["success"] is False


def test_tick_archives_faded_memories_but_keeps_them_forever():
    w = Wouf()
    mid = w.remember_event("coffee with Sam from the platform team", now=0.0)
    w.tick(now=60 * DAY)  # episodic S=7d, R at 60d is ~0.0002
    assert w.get(mid) is None
    assert any(e["id"] == mid for e in w.archive)


def test_archived_memory_revives_on_strong_cue():
    w = Wouf()
    mid = w.remember_event("coffee with Sam from the platform team", now=0.0)
    w.tick(now=60 * DAY)
    pack = w.recall("what did I discuss with Sam over coffee?", now=61 * DAY)
    assert mid in {m.id for m in pack.memories}
    assert w.get(mid).tier == Tier.WARM
    assert not any(e["id"] == mid for e in w.archive)


def test_superseded_versions_do_not_revive():
    w = Wouf()
    v1 = w.remember_procedure("deploy-api", ["run tests", "push", "verify"], now=0.0)
    w.correct(v1, now=1 * DAY, steps=["run tests", "smoke", "push", "verify"])
    w.tick(now=2 * DAY)  # superseded v1 gets archived
    assert w.get(v1) is None
    w.recall("how do I deploy the api? run tests push verify", now=3 * DAY)
    assert w.get(v1) is None  # strong cue, still stays archived


def test_expired_intention_is_archived():
    w = Wouf()
    mid = w.intend("standup", "mention the outage", now=0.0, expires=2 * DAY)
    w.tick(now=3 * DAY)
    assert w.get(mid) is None
    assert any(e["id"] == mid for e in w.archive)
