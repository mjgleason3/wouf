from wouf import MemoryType, Wouf
from wouf.models import DAY


def make_world():
    """A store with plenty of specific memory plus a few laws."""
    w = Wouf()
    w.remember("Project Falcon is our payments service on Postgres", now=0.0)
    w.remember("Staging credentials live in the 1Password vault", now=0.0)
    w.remember_procedure("deploy-api", ["run tests", "push image", "verify"], now=0.0)
    w.law("Water flows downhill", now=0.0, confidence=0.95)
    w.law("When uncertain, prefer the action that is easiest to undo", now=0.0, confidence=0.9)
    w.law("Check the cheapest explanation before the expensive one", now=0.0, confidence=0.85)
    return w


def test_law_has_high_stability_and_confidence():
    w = Wouf()
    lid = w.law("Systems drift toward entropy without maintenance", now=0.0)
    m = w.get(lid)
    assert m.type == MemoryType.LAW
    assert m.stability == 365.0
    assert m.payload["confidence"] == 0.9


def test_novel_situation_falls_back_to_laws():
    """No specific memory covers the query -> top-confidence laws step in."""
    w = make_world()
    pack = w.recall("something is wrong with the new vendor and nobody knows why", now=1 * DAY)
    assert pack.novel
    law_texts = [m.text for m in pack.memories if m.type == MemoryType.LAW]
    assert "Water flows downhill" in law_texts  # highest confidence leads
    assert len(law_texts) <= 3


def test_familiar_ground_keeps_laws_out():
    w = make_world()
    pack = w.recall("how do I deploy the api?", now=1 * DAY)
    assert not pack.novel
    assert not any(m.type == MemoryType.LAW for m in pack.memories)


def test_lexical_match_surfaces_a_law_even_on_familiar_ground():
    w = make_world()
    w.remember("The water cooler on floor 3 is broken", now=0.0)
    pack = w.recall("where does water flow in the plumbing system?", now=1 * DAY)
    assert "Water flows downhill" in pack.markdown


def test_confirm_and_refute_manage_confidence():
    w = Wouf()
    lid = w.law("Moss favors the shaded side of trees", now=0.0, confidence=0.7)
    w.confirm(lid, now=1 * DAY)
    assert w.get(lid).payload["confidence"] > 0.7
    w.refute(lid, now=2 * DAY, note="dense canopy: moss grew all around")
    m = w.get(lid)
    assert m.payload["confidence"] < 0.73
    assert m.payload["exceptions"][0]["note"] == "dense canopy: moss grew all around"


def test_exception_renders_beneath_the_law():
    w = Wouf()
    lid = w.law("Prefer the reversible action", now=0.0)
    w.refute(lid, now=1 * DAY, note="the hotfix window was closing")
    pack = w.recall("a totally unfamiliar emergency", now=2 * DAY)
    assert "exception: the hotfix window was closing" in pack.markdown


def test_tension_is_surfaced_not_resolved():
    w = Wouf()
    a = w.law("When uncertain, prefer the reversible action", now=0.0, confidence=0.9)
    b = w.law("Strike while the window is open", now=0.0, confidence=0.88)
    w.link(a, b, "tension")
    pack = w.recall("unprecedented outage, no runbook exists", now=1 * DAY)
    assert a in pack.tensions and b in pack.tensions
    assert 'in tension with: "Strike while the window is open"' in pack.markdown


def test_repeated_refutation_repeals_but_never_deletes():
    w = Wouf()
    lid = w.law("The market always recovers within a quarter", now=0.0, confidence=0.6)
    for day in range(1, 5):
        w.refute(lid, now=day * DAY, note=f"failure {day}")
    w.tick(now=5 * DAY)
    assert w.get(lid) is None
    entry = next(e for e in w.archive if e["id"] == lid)
    assert entry["reason"] == "repealed"
    # a repealed law does not sneak back in via revival
    w.recall("will the market recover this quarter?", now=6 * DAY)
    assert w.get(lid) is None


def test_amending_a_law_versions_it():
    w = Wouf()
    v1 = w.law("Prefer simple solutions", now=0.0)
    v2 = w.correct(v1, now=1 * DAY, text="Prefer the simplest solution that could possibly work")
    assert w.get(v2).payload["version"] == 2
    pack = w.recall("brand new kind of design problem, no precedent", now=2 * DAY)
    ids = {m.id for m in pack.memories}
    assert v2 in ids and v1 not in ids


def test_standing_block_pins_laws_first():
    w = make_world()
    block = w.standing_block(now=1 * DAY)
    assert block.index("Guiding laws") < block.index("Stable knowledge")
    assert "Water flows downhill [95%]" in block
