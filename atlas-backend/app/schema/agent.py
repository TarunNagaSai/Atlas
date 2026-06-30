"""Agent streaming-event schema.

``Gemini.stream_agent_turn_async`` emits one event per part as the model
streams, and ``run_agent`` forwards these (plus tool-result events) straight to
the SSE client so the frontend sees the whole reason→act loop: the model's
thought summaries, the tool calls it makes, the results those return, the final
answer, and token usage. These models give that wire a typed, validated shape
instead of bare dicts so the agent loop can ``isinstance``-dispatch and access
fields by attribute, and the route can ``model_dump`` each into an SSE frame.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class TextEvent(BaseModel):
    """A streamed text chunk — part of the model's final answer."""

    type: Literal["text"] = "text"
    text: str = Field(min_length=1)


class PlanEvent(BaseModel):
    """A streamed chunk of the agent's upfront plan.

    Before the ReAct loop runs, the agent does one planning turn: it abstracts
    the big picture — what the question is really asking, what it needs to find,
    and the approach it will take — without calling any tool or answering yet.
    These chunks stream first so the UI can show the agent "thinking through the
    problem" as the opening step, distinct from the live ``ThoughtEvent``s that
    Gemini emits during each subsequent turn.
    """

    type: Literal["plan"] = "plan"
    text: str = Field(min_length=1)


class ThoughtEvent(BaseModel):
    """A streamed chunk of the model's summarized reasoning.

    Emitted only when thinking is on (``include_thoughts``); Gemini exposes
    *summarized* thoughts, not the raw chain-of-thought.
    """

    type: Literal["thought"] = "thought"
    text: str = Field(min_length=1)


class ToolCallEvent(BaseModel):
    """A native function call the model emitted mid-stream."""

    # ``part`` is a raw ``google.genai`` ``types.Part``, not a pydantic model,
    # so the model must permit arbitrary types.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: Literal["tool_call"] = "tool_call"
    name: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    # The original function-call Part. It is echoed back verbatim on the next
    # turn so the Gemini 3.x ``thought_signature`` survives; excluded from any
    # dump/serialization since it is an SDK object, not data.
    part: Any = Field(default=None, exclude=True, repr=False)


class ToolResultEvent(BaseModel):
    """The result of a tool the model called, surfaced back to the client.

    The same ``result`` string is also fed back to the model as the function
    response on the next turn; this event is the client-facing copy.
    """

    type: Literal["tool_result"] = "tool_result"
    name: str = Field(min_length=1)
    result: str


class UsageEvent(BaseModel):
    """Token usage. ``scope="turn"`` is one Gemini call; ``scope="total"`` is
    the aggregate across every turn of the agent run, emitted once at the end.
    """

    type: Literal["usage"] = "usage"
    scope: Literal["turn", "total"] = "turn"
    prompt_tokens: int = 0
    thoughts_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


# Discriminated union: validates any variant by its ``type`` tag.
AgentEvent = Annotated[
    Union[PlanEvent, TextEvent, ThoughtEvent, ToolCallEvent, ToolResultEvent, UsageEvent],
    Field(discriminator="type"),
]
