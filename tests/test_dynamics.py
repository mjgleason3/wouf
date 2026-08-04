import math

from wouf import Memory, MemoryType
from wouf.dynamics import activation, reinforce, retrievability, spread
from wouf.models import DAY


def make(now=0.0, type=MemoryType.SEMANTIC):
    return Memory.new("the earth is a sphere", type, now)


def test_retrievability_decays_monotonically():
    m = make()
    values = [retrievability(m, t * DAY) for t in range(0, 60, 5)]
    assert all(a > b for a, b in zip(values, values[1:]))
    assert values[0] == 1.0


def test_stability_sets_decay_speed():
    fast = make(type=MemoryType.EPISODIC)  # S = 7d
    slow = make(type=MemoryType.SEMANTIC)  # S = 30d
    assert retrievability(fast, 10 * DAY) < retrievability(slow, 10 * DAY)


def test_reinforcement_grows_stability_and_resets_clock():
    m = make()
    s0 = m.stability
    reinforce(m, 10 * DAY)
    assert m.stability > s0
    assert m.last_access == 10 * DAY
    assert m.access_count == 1
    assert retrievability(m, 10 * DAY) == 1.0


def test_spacing_effect_rewards_rescuing_faded_memories():
    early, late = make(), make()
    reinforce(early, 1 * DAY)  # touched while fresh
    reinforce(late, 25 * DAY)  # rescued when nearly forgotten
    assert late.stability > early.stability


def test_repeated_use_slows_decay():
    m = make()
    for day in (5, 10, 15, 20):
        reinforce(m, day * DAY)
    untouched = make()
    assert retrievability(m, 40 * DAY) > retrievability(untouched, 40 * DAY)


def test_activation_decays_much_faster_than_retrievability():
    m = make()
    t = 2 * DAY
    assert activation(m, t) < 0.05
    assert retrievability(m, t) > 0.9


def test_spread_energizes_neighbor_without_touching_forgetting_curve():
    source, target = make(), make()
    t = 3 * DAY
    reinforce(source, t)
    r_before = retrievability(target, t)
    a_before = activation(target, t)
    spread(source, target, weight=1.0, now=t)
    assert activation(target, t) > a_before
    assert retrievability(target, t) == r_before
    assert target.last_access == 0.0
