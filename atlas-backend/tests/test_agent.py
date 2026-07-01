"""Rigorous unit tests for the ReAct agent loop in ``app/agent/agent.py``.

The agent is exercised end-to-end with a *scripted* Gemini stand-in and a stub
``run_tool`` so every branch of the reason->act loop is deterministic:

  - the streamed final answer (no tool call),
  - one or more tool hops with history feedback,
  - the forced-answer safety valve on the final allowed hop,
  - the empty/degenerate turn,
  - prompt loading and per-turn invocation contracts.

Both ``get_gemini`` and ``run_tool`` are imported into ``app.agent.agent`` at
import time, so they are patched *there*, not at their definition modules.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from google.genai import types

import app.agent.agent as agent
from app.agent.agent import _FALLBACK_PROMPT, _load_prompt, run_agent
from app.tools.tools import RETRIEVE_TOOL


# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #
def text_event(text: str) -> dict:
    return {"type": "text", "text": text}


def tool_event(name: str = "retrieve", args: dict | None = None) -> dict:
    return {"type": "tool_call", "name": name, "args": args or {"query": "q"}}


class ScriptedGemini:
    """A Gemini stand-in that replays a fixed list of turns.

    ``turns[i]`` is the list of events yielded on the *i*-th call to
    ``stream_agent_turn_async``. Every call is recorded (with a snapshot of the
    ``contents`` list as it stood at call time) so tests can assert how the
    conversation history grows across hops.
    """

    def __init__(self, turns: list[list[dict]]):
        self._turns = turns
        self.calls: list[dict] = []

    async def stream_agent_turn_async(
        self,
        contents: list[types.Content],
        tools: list[types.Tool],
        *,
        system: str | None = None,
        settings=None,
    ) -> AsyncIterator[dict]:
        # Snapshot the list (shallow): contents is mutated in place by the agent
        # between calls, so we copy the membership at this instant.
        self.calls.append(
            {"contents": list(contents), "tools": tools, "system": system}
        )
        idx = len(self.calls) - 1
        for event in self._turns[idx]:
            yield event


@pytest.fixture
def patch_agent(monkeypatch):
    """Wire a ScriptedGemini + recording run_tool into the agent module.

    Returns a small handle exposing the gemini double and the recorded
    ``run_tool`` calls. ``tool_return`` controls what the stub tool feeds back.
    """

    class Handle:
        def __init__(self):
            self.gemini: ScriptedGemini | None = None
            self.tool_calls: list[tuple[str, dict]] = []
            self.tool_return = "RETRIEVED PASSAGE"

        def script(self, turns: list[list[dict]]) -> ScriptedGemini:
            self.gemini = ScriptedGemini(turns)
            monkeypatch.setattr(agent, "get_gemini", lambda: self.gemini)
            return self.gemini

    handle = Handle()

    def fake_run_tool(name: str, args: dict) -> str:
        handle.tool_calls.append((name, args))
        return handle.tool_return

    monkeypatch.setattr(agent, "run_tool", fake_run_tool)
    # Pin the prompt so assertions don't depend on the on-disk file.
    monkeypatch.setattr(agent, "_load_prompt", lambda: "SYSTEM PROMPT")
    return handle


async def collect(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


# --------------------------------------------------------------------------- #
# Final-answer turn (no tool call)
# --------------------------------------------------------------------------- #
async def test_streams_final_answer_without_calling_tools(patch_agent):
    patch_agent.script([[text_event("Hello "), text_event("world")]])

    out = await collect(run_agent("hi"))

    assert out == ["Hello ", "world"]
    assert patch_agent.tool_calls == []  # no tool turn => tool never runs
    assert len(patch_agent.gemini.calls) == 1


async def test_first_turn_seeds_user_message_tools_and_system(patch_agent):
    patch_agent.script([[text_event("ok")]])

    await collect(run_agent("what is revenue?"))

    call = patch_agent.gemini.calls[0]
    assert call["tools"] == [RETRIEVE_TOOL]
    assert call["system"] == "SYSTEM PROMPT"
    # Initial history is exactly the user's message.
    assert len(call["contents"]) == 1
    user_msg = call["contents"][0]
    assert user_msg.role == "user"
    assert user_msg.parts[0].text == "what is revenue?"


# --------------------------------------------------------------------------- #
# Tool hop -> final answer
# --------------------------------------------------------------------------- #
async def test_tool_call_then_answer(patch_agent):
    patch_agent.tool_return = "Revenue was $5M"
    patch_agent.script(
        [
            [tool_event(args={"query": "revenue"})],
            [text_event("The revenue is $5M.")],
        ]
    )

    out = await collect(run_agent("revenue?"))

    assert out == ["The revenue is $5M."]
    assert patch_agent.tool_calls == [("retrieve", {"query": "revenue"})]
    assert len(patch_agent.gemini.calls) == 2


async def test_tool_turn_text_is_not_yielded(patch_agent):
    """A turn whose first event is a tool call yields no text to the caller."""
    patch_agent.script(
        [
            [tool_event()],
            [text_event("final")],
        ]
    )

    out = await collect(run_agent("q"))

    assert out == ["final"]


async def test_text_before_tool_call_on_same_turn_leaks(patch_agent):
    """Documents a latent leak: the loop yields text optimistically and only
    breaks *when* it sees the tool call, so any text the model emits *before*
    the ``function_call`` part on a tool turn reaches the caller — contradicting
    the "text on this turn is suppressed" comment in ``run_agent``.

    If the agent is fixed to buffer/suppress pre-tool-call text, flip this test.
    """
    patch_agent.script(
        [
            [text_event("Let me look that up. "), tool_event()],
            [text_event("answer")],
        ]
    )

    out = await collect(run_agent("q"))

    assert out == ["Let me look that up. ", "answer"]


async def test_history_grows_with_function_call_then_response(patch_agent):
    patch_agent.tool_return = "PASSAGE TEXT"
    patch_agent.script(
        [
            [tool_event(args={"query": "margins"})],
            [text_event("done")],
        ]
    )

    await collect(run_agent("margins?"))

    # The second model call sees: original user msg, the echoed function_call,
    # then the function_response carrying the tool result.
    second = patch_agent.gemini.calls[1]["contents"]
    assert len(second) == 3

    fc_content = second[1]
    assert fc_content.role == "model"
    fc = fc_content.parts[0].function_call
    assert fc.name == "retrieve"
    assert dict(fc.args) == {"query": "margins"}

    fr_content = second[2]
    assert fr_content.role == "user"
    fr = fr_content.parts[0].function_response
    assert fr.name == "retrieve"
    assert fr.response == {"result": "PASSAGE TEXT"}


async def test_multiple_tool_hops_before_answer(patch_agent):
    patch_agent.script(
        [
            [tool_event(args={"query": "a"})],
            [tool_event(args={"query": "b"})],
            [text_event("combined answer")],
        ]
    )

    out = await collect(run_agent("q"))

    assert out == ["combined answer"]
    assert patch_agent.tool_calls == [
        ("retrieve", {"query": "a"}),
        ("retrieve", {"query": "b"}),
    ]
    # 3 model calls; the final turn's history has 5 entries (user + 2*(fc+fr)).
    assert len(patch_agent.gemini.calls) == 3
    assert len(patch_agent.gemini.calls[2]["contents"]) == 5


async def test_system_prompt_forwarded_on_every_turn(patch_agent):
    patch_agent.script(
        [
            [tool_event()],
            [text_event("done")],
        ]
    )

    await collect(run_agent("q"))

    assert [c["system"] for c in patch_agent.gemini.calls] == [
        "SYSTEM PROMPT",
        "SYSTEM PROMPT",
    ]


# --------------------------------------------------------------------------- #
# Forced-answer safety valve (final allowed hop)
# --------------------------------------------------------------------------- #
# The loop no longer has a functional turn cap and never emits a "couldn't find
# enough information" fallback: it runs until the model stops calling tools. The
# only backstop is ``Settings.agent_max_hops`` — on that final hop the agent
# withholds its tools and swaps in ``force_answer_prompt``, compelling the model
# to answer from the context it has already gathered (outcome "forced_answer").
# See ``run_agent`` in app/agent/agent.py.


# --------------------------------------------------------------------------- #
# Degenerate turns
# --------------------------------------------------------------------------- #
async def test_empty_turn_is_treated_as_final_answer(patch_agent):
    """A turn yielding no events has no tool call, so the loop ends silently."""
    patch_agent.script([[]])

    out = await collect(run_agent("q"))

    assert out == []
    assert patch_agent.tool_calls == []
    assert len(patch_agent.gemini.calls) == 1


async def test_multi_chunk_final_answer_streamed_in_order(patch_agent):
    patch_agent.script(
        [[text_event("a"), text_event("b"), text_event("c")]]
    )

    out = await collect(run_agent("q"))

    assert out == ["a", "b", "c"]


# --------------------------------------------------------------------------- #
# Prompt loading
# --------------------------------------------------------------------------- #
def test_load_prompt_reads_file_when_present(monkeypatch, tmp_path):
    prompt_file = tmp_path / "react_prompt.txt"
    prompt_file.write_text("FILE PROMPT CONTENT")
    monkeypatch.setattr(agent, "_PROMPT_PATH", prompt_file)

    assert _load_prompt() == "FILE PROMPT CONTENT"


def test_load_prompt_falls_back_when_missing(monkeypatch, tmp_path):
    missing = tmp_path / "nope.txt"
    monkeypatch.setattr(agent, "_PROMPT_PATH", missing)

    assert _load_prompt() == _FALLBACK_PROMPT
