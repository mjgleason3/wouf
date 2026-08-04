from wouf import MemoryType, Wouf
from wouf.models import DAY


def test_recall_surfaces_relevant_memory():
    w = Wouf()
    target = w.remember("Nyx's daughter is named Ada", now=0.0)
    w.remember("the deploy pipeline runs on GitHub Actions", now=0.0)
    pack = w.recall("what is my daughter's name?", now=1 * DAY)
    ids = {m.id for m in pack.memories}
    assert target in ids
    assert "Ada" in pack.markdown


def test_recall_respects_token_budget():
    w = Wouf()
    for i in range(200):
        w.remember(f"fact number {i} about the project alpha codebase details", now=0.0)
    pack = w.recall("project alpha codebase", now=1.0, budget=100)
    assert pack.tokens <= 100


def test_irrelevant_memories_stay_out():
    w = Wouf()
    w.remember("Nyx's favorite editor is Neovim", now=0.0)
    noise = w.remember("the quarterly budget review moved to Thursday", now=0.0)
    pack = w.recall("which editor do I use?", now=1.0)
    assert noise not in {m.id for m in pack.memories}


def test_graph_pulls_in_memory_with_no_keyword_overlap():
    w = Wouf()
    proc = w.remember_procedure(
        "deploy-api", ["run tests", "build image", "push to registry"], now=0.0
    )
    fact = w.remember("staging credentials live in 1Password vault Eng", now=0.0)
    w.link(proc, fact, "depends_on")
    pack = w.recall("walk me through deploy", now=1.0)
    assert fact in {m.id for m in pack.memories}


def test_sparse_focus_caps_episodic_memories():
    w = Wouf()
    for i in range(20):
        w.remember_event(f"standup meeting note {i} about the sprint work", now=0.0)
    pack = w.recall("standup meeting sprint", now=1.0, budget=4000)
    episodic = [m for m in pack.memories if m.type == MemoryType.EPISODIC]
    assert len(episodic) <= 5


def test_prospective_fires_on_trigger_and_is_spent():
    w = Wouf()
    w.intend(trigger="deploy", action="run smoke tests first", now=0.0)
    pack = w.recall("time to deploy the api", now=1.0)
    assert len(pack.fired) == 1
    assert "smoke tests" in pack.markdown
    again = w.recall("time to deploy the api", now=2.0)
    assert not again.fired  # once-intentions are spent after firing


def test_inclusion_reinforces_the_energetic_loop():
    w = Wouf()
    mid = w.remember("the API rate limit is 100 requests per minute", now=0.0)
    w.recall("what is the API rate limit?", now=1 * DAY)
    m = w.get(mid)
    assert m.access_count == 1
    assert m.stability > 30.0
