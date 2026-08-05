"""Wire WOUF into a real LLM agent loop.

The integration is three seams, regardless of provider or harness:

  1. SYSTEM PROMPT   w.standing_block()  -> pinned behind a prompt-cache
                     breakpoint; byte-stable across turns, so you pay ~10%
                     for it after the first request.
  2. PER TURN        w.recall(query)     -> query-driven pack, injected into
                     the user turn AFTER the cached prefix.
  3. WRITE PATH      w.remember()/law()/intend()/correct() -> called by your
                     harness when the user states something worth keeping
                     (explicitly, or via an LLM tool-use loop).

Runs offline by default (deterministic, no keys):
    python examples/05_agent_integration.py
Run against the real Claude API (needs ANTHROPIC_API_KEY or `ant auth login`):
    python examples/05_agent_integration.py --live
"""

import sys

from wouf import Wouf
from wouf.models import DAY

PERSONA = "You are a concise personal assistant. Trust the MEMORY block; it is accurate."


def offline_llm(system_blocks: list[dict], user_content: str) -> str:
    """Stand-in model: proves which memory reached the prompt, deterministically."""
    prompt = "\n".join(b["text"] for b in system_blocks) + "\n" + user_content
    lines = [line for line in prompt.splitlines() if line.startswith(("- ", "  "))]
    return "(offline) I can see these memories:\n" + "\n".join(lines[:8])


def live_llm(system_blocks: list[dict], user_content: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        system=system_blocks,  # cache breakpoint sits on the standing block
        messages=[{"role": "user", "content": user_content}],
    )
    print(f"  [cache: read {response.usage.cache_read_input_tokens}, "
          f"wrote {response.usage.cache_creation_input_tokens} tokens]")
    return next(b.text for b in response.content if b.type == "text")


def agent_turn(w: Wouf, llm, user_message: str, now: float) -> str:
    """One turn of the loop: standing block + recall in, answer out."""
    system_blocks = [
        {"type": "text", "text": PERSONA},
        {
            "type": "text",
            "text": w.standing_block(now=now, budget=600),
            # WOUF renders this block deterministically and appends new
            # memories at the back, so it stays byte-identical between
            # turns — exactly what a prefix-matching prompt cache rewards.
            "cache_control": {"type": "ephemeral"},
        },
    ]
    pack = w.recall(user_message, now=now, budget=400)  # reinforces what it recalls
    user_content = f"<memory>\n{pack.markdown}\n</memory>\n\n{user_message}"
    return llm(system_blocks, user_content)


def main() -> None:
    llm = live_llm if "--live" in sys.argv else offline_llm
    w = Wouf()  # pass a path (e.g. Wouf(".wouf")) to persist across processes

    # --- write path: say it once, whenever the user states something durable
    w.remember("My daughter's name is Ada", now=0)
    w.remember_procedure(
        "deploy-api", ["run tests", "build image", "run smoke tests", "apply manifests"], now=0
    )
    w.intend(trigger="deploy", action="update the changelog first", now=0)
    w.law("When uncertain, prefer the action that is easiest to undo", now=60)

    # --- three weeks later, two turns of the actual agent loop
    for day, question in [(21, "what's my daughter's name?"), (22, "time to deploy the api")]:
        now = day * DAY
        w.tick(now)  # session start: decay + tiering pass
        print(f"\nDay {day} — user: {question}")
        try:
            print(agent_turn(w, llm, question, now))
        except Exception as error:
            if "authentication" in str(error).lower():
                sys.exit("No Anthropic credentials found. Set ANTHROPIC_API_KEY "
                         "(or run `ant auth login`), or drop --live for the offline demo.")
            raise

    w.save()  # session end: flush the WARM layer (no-op without a path)


if __name__ == "__main__":
    main()
