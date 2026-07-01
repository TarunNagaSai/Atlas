from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import aclosing
from pathlib import Path

import logfire
from google.genai import types

from app.agent.cancellation import GenerationCancelled, get_cancellation_registry
from app.llm.gemini import get_gemini
from app.observability.langfuse import get_langfuse_client
from app.schema.agent import (
    AgentEvent,
    PlanEvent,
    TextEvent,
    ToolCallEvent,
    ToolResultEvent,
    UsageEvent,
)
from app.schema.llm_settings import ModelSettings
from app.tools.tools import GRAPH_SEARCH_TOOL, RETRIEVE_TOOL, execute_tool_call

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_PROMPT_PATH = _PROMPTS_DIR / "react_prompt.txt"
_PLAN_PROMPT_PATH = _PROMPTS_DIR / "plan_prompt.txt"
_FORCE_PROMPT_PATH = _PROMPTS_DIR / "force_answer_prompt.txt"
_FALLBACK_PROMPT = (
    "You are a helpful assistant. Use the `retrieve` function to search the "
    "indexed documents before answering. When you have enough context, write the "
    "final answer directly. Never emit text before calling a function."
)
_FALLBACK_PLAN_PROMPT = (
    "Before answering, briefly think through the question: restate what is being "
    "asked, what you need to find, and how you will approach it. Do not answer "
    "or call any tool yet — just lay out the plan in 3-5 sentences."
)
_FALLBACK_FORCE_PROMPT = (
    "You have no tools available now and cannot search again. Write your final "
    "answer using only the information already retrieved earlier in this "
    "conversation. Quote figures exactly and cite their sources; state plainly "
    "what you could not find, and never invent a figure that isn't in the "
    "retrieved passages."
)
def _load_prompt() -> str:
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text()
    return _FALLBACK_PROMPT


def _load_plan_prompt() -> str:
    if _PLAN_PROMPT_PATH.exists():
        return _PLAN_PROMPT_PATH.read_text()
    return _FALLBACK_PLAN_PROMPT


def _load_force_prompt() -> str:
    if _FORCE_PROMPT_PATH.exists():
        return _FORCE_PROMPT_PATH.read_text()
    return _FALLBACK_FORCE_PROMPT


def _accumulate(total: UsageEvent, turn: UsageEvent) -> None:
    """Fold one turn's token counts into the running ``scope="total"`` tally."""
    total.prompt_tokens += turn.prompt_tokens
    total.thoughts_tokens += turn.thoughts_tokens
    total.output_tokens += turn.output_tokens
    total.total_tokens += turn.total_tokens


async def run_agent(
    message: str,
    *,
    session_id: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    book_id: str | None = None,
    attachment_parts: list[types.Part] | None = None,
    history: list[dict[str, str]] | None = None,
) -> AsyncIterator[AgentEvent]:
    """Streaming ReAct agent over Gemini native function calling.

    Yields typed :class:`AgentEvent`\\ s so the caller can stream the whole
    reason→act loop, not just the answer: ``PlanEvent`` (the upfront big-picture
    plan, streamed once before the loop), ``ThoughtEvent`` (summarized reasoning
    during each turn), ``TextEvent`` (preamble or the final answer),
    ``ToolCallEvent`` (the function the model called), ``ToolResultEvent`` (what
    it returned), and ``UsageEvent`` (per turn, plus one ``scope="total"``
    aggregate at the end).

    Before the loop, one tool-less **planning turn** runs: the model abstracts
    the big picture (what is asked, what to find, how to approach it) and that
    text streams as ``PlanEvent``\\ s and is appended to ``contents`` so every
    subsequent turn is conditioned on the plan.

    Per turn: a ``tool_call`` event means run ``retrieve`` and loop with the
    result appended; a turn with no tool call is the final answer.

    If ``session_id`` is given, the loop polls the cancellation registry at two
    gates and raises :class:`GenerationCancelled` when the matching stream has
    been cancelled (e.g. the user clicked stop and the route hit ``/chat/cancel``).

    ``api_key`` is the caller's own Gemini key (BYO-key flow): it powers both the
    generation calls and the ``retrieve`` tool's query embedding, so the whole
    turn runs on that key. When ``None``, the server key is used.

    ``model`` overrides the generation model for this run (the frontend's model
    picker); ``None`` falls back to the server default. Every turn of the run
    uses the same model. Embeddings always use the fixed ``embed_model`` — it
    must match the space the stored vectors live in, so it is never user-selectable.

    ``book_id`` is the book the user selected in the frontend; it scopes every
    ``retrieve`` call to that book's embeddings only. ``None`` searches all books.

    ``attachment_parts`` are pre-built Gemini parts for files the user attached
    this turn (images/PDF as inline binary, Word/Excel as extracted text). They
    are prepended to the user message so the model sees the files, then reads the
    question. They persist in ``contents`` across every hop, so a retrieved-then-
    reason loop can still refer back to the attachment. ``None`` is a plain turn.

    ``history`` is the prior conversation as ``{"role", "content"}`` turns (oldest
    first, excluding this message): in DB storage mode the route loads it from
    Postgres, in client-side mode the browser replays it in the request body.
    It is prepended to ``contents`` so the agent has multi-turn memory; ``None``
    or empty is a fresh, single-turn conversation. (Trimming/sliding-window of
    this history is handled upstream — the agent replays whatever it is given.)
    """
    gemini = get_gemini(api_key)
    # Agent turns are deterministic (temperature 0.0); only the model is variable.
    turn_settings = ModelSettings(model=model, temperature=0.0)
    turn_model = turn_settings.model or gemini.s.gen_model
    langfuse = get_langfuse_client()
    registry = get_cancellation_registry()
    system = _load_prompt()
    plan_system = _load_plan_prompt()
    force_system = _load_force_prompt()
    max_hops = gemini.s.agent_max_hops
    # Prior conversation first (so the agent has multi-turn memory), then this
    # turn. Gemini speaks ``user``/``model``; map the stored ``assistant`` role.
    contents: list[types.Content] = [
        types.Content(
            role="model" if m.get("role") == "assistant" else "user",
            parts=[types.Part(text=m.get("content", ""))],
        )
        for m in (history or [])
        if m.get("content")
    ]
    # Attachments first, then the question — the model reads the files, then the
    # instruction acting on them.
    user_parts: list[types.Part] = list(attachment_parts or [])
    user_parts.append(types.Part(text=message))
    contents.append(types.Content(role="user", parts=user_parts))
    # Running token totals across every turn; emitted once the run finishes.
    totals = UsageEvent(scope="total")

    def _stop_requested() -> bool:
        # No session id (internal callers) ⇒ never cancellable.
        return session_id is not None and registry.is_cancelled(session_id)

    # One span per agent invocation; each turn nests inside it so a trace shows
    # the whole reason->act loop, not just the HTTP request envelope. The Langfuse
    # ``agent.run`` span mirrors the Logfire one and nests under the route's
    # ``agent-stream`` generation; each turn opens its own Langfuse generation so
    # the trace breaks token usage down per Gemini call (and tool spans, which
    # ``@observe`` themselves, nest under the turn that requested them).
    with logfire.span("agent.run", message=message) as span, \
            langfuse.start_as_current_observation(
                name="agent.run", as_type="span", input=message
            ) as run_obs:
        # Planning step: one tool-less turn where the model abstracts the big
        # picture before acting — what is really being asked, what it needs to
        # find, and how it will approach it. Its text streams to the client as
        # ``PlanEvent``s (the UI's opening "thinking" step) and is appended to
        # ``contents`` as a model turn, so every subsequent ReAct turn is
        # conditioned on the plan it just laid out. It runs once per agent run.
        plan_parts: list[str] = []
        with logfire.span("agent.plan"), \
                langfuse.start_as_current_observation(
                    name="agent.plan", as_type="generation", model=turn_model
                ) as plan_obs:
            async with aclosing(
                gemini.stream_agent_turn_async(
                    contents, [], system=plan_system, settings=turn_settings
                )
            ) as plan_events:
                async for event in plan_events:
                    if _stop_requested():
                        span.set_attribute("outcome", "cancelled")
                        run_obs.update(output="(cancelled)")
                        raise GenerationCancelled
                    if isinstance(event, UsageEvent):
                        _accumulate(totals, event)
                        plan_obs.update(
                            usage_details={
                                "input": event.prompt_tokens,
                                "output": event.output_tokens + event.thoughts_tokens,
                                "total": event.total_tokens,
                            }
                        )
                        yield event  # plan-turn usage (folded into totals)
                        continue
                    # The plan's *text* is the deliverable, so surface it as a
                    # PlanEvent. Native ThoughtEvents here are the model's private
                    # scratch for writing the plan — drop them so the UI shows one
                    # reasoning stream for this step, not two.
                    if isinstance(event, TextEvent):
                        plan_parts.append(event.text)
                        yield PlanEvent(text=event.text)
            plan_text = "".join(plan_parts).strip()
            plan_obs.update(output=plan_text or "(no plan)")
            if plan_text:
                # Append as the model's own turn so the loop continues from its
                # plan straight into acting/answering.
                contents.append(
                    types.Content(role="model", parts=[types.Part(text=plan_text)])
                )

        # Reason->act loop that runs until the model stops calling tools and
        # streams a final answer. ``max_hops`` is a high safety backstop, not a
        # functional limit: on the final allowed turn the agent drops its tools
        # and swaps in ``force_system``, so instead of failing with "max hops
        # exhausted" it is compelled to answer from whatever it has already
        # gathered. The other exit is cancellation (stop / disconnect, caught at
        # the gates below).
        hop = 0
        while True:
            hop += 1
            # Outer gate: catches a stop that arrived while the previous turn's
            # tool call was running (the inner gate wasn't executing to see it).
            if _stop_requested():
                span.set_attribute("outcome", "cancelled")
                run_obs.update(output="(cancelled)")
                raise GenerationCancelled

            # Final allowed turn: withhold the tools and force an answer from the
            # context gathered so far, rather than letting the loop run forever.
            forced = hop >= max_hops
            if forced:
                logfire.warn(
                    "agent hit max hops ({max_hops}); forcing an answer from "
                    "gathered context", max_hops=max_hops
                )
            turn_tools = [] if forced else [RETRIEVE_TOOL, GRAPH_SEARCH_TOOL]
            turn_system = force_system if forced else system

            with logfire.span("agent.step", step=hop, forced=forced), \
                    langfuse.start_as_current_observation(
                        name=f"agent.turn-{hop}", as_type="generation", model=turn_model
                    ) as turn_obs:
                tool_call: ToolCallEvent | None = None
                turn_text: list[str] = []
                # ``aclosing`` guarantees the Gemini generator (and its socket) is
                # torn down the instant we leave this block — the final-answer
                # ``return`` or the ``GenerationCancelled`` raise.
                async with aclosing(
                    gemini.stream_agent_turn_async(
                        contents,
                        turn_tools,
                        system=turn_system,
                        settings=turn_settings,
                    )
                ) as events:
                    async for event in events:
                        # Inner gate: stops the *current* answer mid-stream, so a
                        # click halts at the next token rather than the last one.
                        if _stop_requested():
                            span.set_attribute("outcome", "cancelled")
                            run_obs.update(output="(cancelled)")
                            raise GenerationCancelled
                        if isinstance(event, UsageEvent):
                            _accumulate(totals, event)
                            # Thoughts bill as output; fold them in so input +
                            # output == total in the turn's Langfuse generation.
                            turn_obs.update(
                                usage_details={
                                    "input": event.prompt_tokens,
                                    "output": event.output_tokens + event.thoughts_tokens,
                                    "total": event.total_tokens,
                                }
                            )
                            yield event  # per-turn usage
                            continue
                        if isinstance(event, ToolCallEvent):
                            # Record the first call, surface it, but keep draining
                            # the turn so its trailing UsageEvent still arrives (a
                            # break would tear the socket down before usage).
                            if tool_call is None:
                                tool_call = event
                                yield event
                            continue
                        # ThoughtEvent streams live — it's always reasoning, never
                        # mistaken for the answer. TextEvent is NOT streamed here:
                        # until the turn finishes we can't tell whether it's the
                        # final answer or a preamble the model wrote before a
                        # tool call further down the same turn (it does this
                        # despite being told not to). Buffer it and only forward
                        # to the client once we know this turn had no tool call.
                        if isinstance(event, TextEvent):
                            turn_text.append(event.text)
                            continue
                        yield event

                # Final-answer turn: no tool call this turn means the model
                # already streamed its answer above — we're done.
                if tool_call is None:
                    answer = "".join(turn_text)
                    if answer:
                        yield TextEvent(text=answer)
                    turn_obs.update(output=answer)
                    run_obs.update(output=answer)
                    span.set_attribute("steps_used", hop)
                    span.set_attribute(
                        "outcome", "forced_answer" if forced else "final_answer"
                    )
                    yield totals
                    return

                # This turn chose to act: record the call as the generation's output.
                turn_obs.update(
                    output={"tool_call": tool_call.name, "args": tool_call.args}
                )
                # Tool turn: the tools module runs the tool (handling failures)
                # and returns the result plus the conversation turns to append,
                # so the next turn has the retrieved context (or an error to
                # recover from) and the client sees what the tool returned. Run
                # inside the turn span so the tool's own @observe span nests here.
                result, turns = await execute_tool_call(
                    tool_call, api_key=api_key, book_id=book_id
                )
                yield ToolResultEvent(name=tool_call.name, result=result)
                contents.extend(turns)
