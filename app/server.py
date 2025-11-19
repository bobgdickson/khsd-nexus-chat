from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from agents import Agent, Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.types import ThreadMetadata, ThreadStreamEvent, UserMessageItem

from .config import settings
from .stores import InMemoryAttachmentStore, InMemoryStore


class NexusChatServer(ChatKitServer[dict[str, Any]]):
    """ChatKitServer wired up to OpenAI via the Agents SDK."""

    def __init__(
        self,
        store: InMemoryStore,
        attachment_store: InMemoryAttachmentStore,
    ) -> None:
        super().__init__(store, attachment_store)
        self.assistant_agent = Agent[AgentContext](
            model=settings.model,
            name="Assistant",
            instructions=(
                "You are a helpful assistant for the KHSD Nexus Chat experience. "
                "Respond concisely and clearly."
            ),
        )

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        agent_context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )
        agent_input = (
            await simple_to_agent_input(input_user_message) if input_user_message else []
        )
        result = Runner.run_streamed(
            self.assistant_agent,
            agent_input,
            context=agent_context,
        )
        async for event in stream_agent_response(agent_context, result):
            yield event
