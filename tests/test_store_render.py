from wouf import Wouf
from wouf.models import DAY
from wouf.render import estimated_cost_ratio, stable_prefix_ratio


def test_store_round_trip(tmp_path):
    path = tmp_path / ".wouf"
    w = Wouf(path)
    fact = w.remember("Nyx's timezone is US/Eastern", now=0.0)
    proc = w.remember_procedure("release", ["tag", "build", "announce"], now=0.0)
    w.link(fact, proc, "relates_to")
    w.tick(now=0.0)
    w.save()

    w2 = Wouf(path)
    assert w2.get(fact).text == "Nyx's timezone is US/Eastern"
    assert w2.get(proc).payload["steps"] == ["tag", "build", "announce"]
    assert len(w2.graph.edges) == len(w.graph.edges)
    assert (path / "MEMORY.md").exists()


def test_render_is_deterministic():
    w = Wouf()
    w.remember("fact one about kubernetes clusters", now=0.0)
    w.remember("fact two about kubernetes ingress", now=0.0)
    a = w.recall("kubernetes", now=1.0).markdown
    b = w.recall("kubernetes", now=1.0).markdown
    assert a == b


def test_stable_ordering_keeps_prefix_stable_as_memories_accrue():
    """New (low-stability) memories should land at the back of the block."""
    w = Wouf()
    for i in range(6):
        w.remember(f"core project fact {i}: service alpha uses postgres", now=0.0)
    # rehearse the core facts so they earn stability
    for day in (1, 2, 3):
        w.recall("service alpha postgres", now=day * DAY)

    before = w.recall("service alpha postgres fact", now=4 * DAY).markdown
    w.remember("service alpha fact: new cache layer added yesterday", now=5 * DAY)
    after = w.recall("service alpha postgres fact", now=5 * DAY).markdown

    ratio = stable_prefix_ratio(before, after)
    assert ratio > 0.5
    assert "cache layer" in after


def test_standing_block_is_stable_across_sessions_as_events_accrue():
    w = Wouf()
    w.remember("Nyx works at Globex on the platform team", now=0.0)
    w.remember_procedure("release", ["tag", "build", "announce"], now=0.0)
    day3 = w.standing_block(now=3 * DAY)
    w.remember_event("CI flaked on test_billing again", now=4 * DAY)
    w.remember_event("sprint planning moved to Wednesday", now=4 * DAY)
    day4 = w.standing_block(now=4 * DAY)
    assert day4.startswith(day3)  # new events land at the back, prefix intact
    assert stable_prefix_ratio(day3, day4) > 0.5


def test_standing_block_does_not_reinforce():
    w = Wouf()
    mid = w.remember("ambient fact about the build cache", now=0.0)
    w.standing_block(now=1 * DAY)
    assert w.get(mid).access_count == 0


def test_cost_ratio_maps_prefix_stability_to_cache_pricing():
    assert estimated_cost_ratio(0.0) == 1.0
    assert abs(estimated_cost_ratio(1.0) - 0.1) < 1e-9
    assert estimated_cost_ratio(0.5) == 0.55
