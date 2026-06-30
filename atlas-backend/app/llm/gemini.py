from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Type, TypeVar

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from app.schema.agent import (
    AgentEvent,
    TextEvent,
    ThoughtEvent,
    ToolCallEvent,
    UsageEvent,
)
from app.schema.llm_settings import ModelSettings, Settings, get_settings

T = TypeVar("T")


class Gemini:
    def __init__(self, settings: Settings | None = None, api_key: str | None = None):
        self.s = settings or get_settings()
        # A per-request key (a visitor's own key, BYO-key flow) takes precedence
        # over the server key; ``require_key`` only runs when neither is given.
        self.client = genai.Client(api_key=api_key or self.s.require_key())

    async def generate_content_stream_async(
        self, prompt: str, settings: ModelSettings | None = None
    ) -> AsyncIterator[str]:
        """Async version — yields chunks without blocking the event loop."""
        s = settings or ModelSettings()
        stream = await self.client.aio.models.generate_content_stream(
            model=s.model or self.s.gen_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=s.system,
                temperature=s.temperature,
                max_output_tokens=s.max_output_tokens,
            ),
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text

    async def stream_agent_turn_async(
        self,
        contents: list[types.Content],
        tools: list[types.Tool],
        *,
        system: str | None = None,
        settings: ModelSettings | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Stream one agent turn with native function calling.

        Yields typed events (``app.schema.agent``) as parts arrive (no
        whole-turn buffering), so the final answer streams token-by-token:
          ``ThoughtEvent``  — a chunk of summarized reasoning (thinking on)
          ``TextEvent``     — a text chunk
          ``ToolCallEvent`` — a function call (carries the raw part)
          ``UsageEvent``    — one per turn, emitted last, with token counts

        A turn is either a tool-call turn or a text (final-answer) turn; the
        caller forwards thoughts on every turn and the answer on the final turn.
        """
        s = settings or ModelSettings(temperature=0.0)
        # A tool-less turn (e.g. the agent's planning step) passes ``tools=[]``;
        # don't send ``tools``/``tool_config`` then — Gemini rejects an empty
        # tools list alongside a function-calling ``tool_config``.
        tool_config = (
            types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            )
            if tools
            else None
        )
        stream = await self.client.aio.models.generate_content_stream(
            model=s.model or self.s.gen_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=tools or None,
                tool_config=tool_config,
                # Surface the model's reasoning as ``thought`` parts so the agent
                # can stream it. Gemini returns *summarized* thoughts here.
                thinking_config=types.ThinkingConfig(
                    include_thoughts=self.s.include_thoughts
                ),
                temperature=s.temperature,
            ),
        )
        # ``aclosing`` guarantees ``stream.aclose()`` runs whenever this generator
        # is torn down — normal exit, or a caller that stops iterating early (a
        # cooperative cancel or a client disconnect). That tears down the
        # underlying httpx connection to Gemini so generation actually stops and
        # we stop paying for tokens, instead of leaking the socket until GC.
        # Usage arrives on ``usage_metadata`` (cumulative across the turn, often
        # only populated on the final chunk); keep the latest snapshot and emit
        # one ``UsageEvent`` once the turn's parts have all streamed.
        usage: types.GenerateContentResponseUsageMetadata | None = None
        async with aclosing(stream) as guarded:
            async for chunk in guarded:
                if chunk.usage_metadata:
                    usage = chunk.usage_metadata
                if not chunk.candidates:
                    continue
                cand = chunk.candidates[0]
                if not cand.content or not cand.content.parts:
                    continue
                for part in cand.content.parts:
                    if part.thought and part.text:
                        # A summarized-reasoning part. Check this *before* the
                        # plain-text branch: thought parts also carry ``text``.
                        yield ThoughtEvent(text=part.text)
                    elif part.function_call:
                        # Pass the raw part through: Gemini 3.x attaches a
                        # ``thought_signature`` to function-call parts that MUST be
                        # echoed back verbatim next turn, so the caller re-appends
                        # this exact part rather than rebuilding it from name+args.
                        yield ToolCallEvent(
                            name=part.function_call.name,
                            args=dict(part.function_call.args or {}),
                            part=part,
                        )
                    elif part.text:
                        yield TextEvent(text=part.text)

        if usage is not None:
            yield UsageEvent(
                scope="turn",
                prompt_tokens=usage.prompt_token_count or 0,
                thoughts_tokens=usage.thoughts_token_count or 0,
                output_tokens=usage.candidates_token_count or 0,
                total_tokens=usage.total_token_count or 0,
            )

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, max=20))
    def generate_structured(
        self, prompt: str, schema: Type[T], settings: ModelSettings | None = None
    ) -> T:
        """Constrained decoding into a Pydantic model."""
        s = settings or ModelSettings(temperature=0.0)
        resp = self.client.models.generate_content(
            model=s.model or self.s.gen_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=s.system,
                temperature=s.temperature,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        parsed = resp.parsed
        if isinstance(parsed, schema):
            return parsed
        return schema.model_validate_json(resp.text)


_gemini: Gemini | None = None


def get_gemini(api_key: str | None = None) -> Gemini:
    """Gemini client. With ``api_key`` (a visitor's own key) a fresh, uncached
    client is built per call so the key is never retained process-wide; without
    it, the shared server-key singleton is returned."""
    if api_key:
        return Gemini(api_key=api_key)
    global _gemini
    if _gemini is None:
        _gemini = Gemini()
    return _gemini
