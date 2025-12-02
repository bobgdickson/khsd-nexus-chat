from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from agents import Agent, Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.store import AttachmentStore, Store
from chatkit.types import ThreadMetadata, ThreadStreamEvent, UserMessageItem

from .config import settings
from .tools import query_ps_finance


class NexusChatServer(ChatKitServer[dict[str, Any]]):
    """ChatKitServer wired up to OpenAI via the Agents SDK."""

    def __init__(
        self,
        store: Store[dict[str, Any]],
        attachment_store: AttachmentStore[dict[str, Any]],
        *,
        instructions: str,
        history_limit: int,
    ) -> None:
        super().__init__(store, attachment_store)
        self.history_limit = history_limit
        self.assistant_agent = Agent[AgentContext](
            model=settings.model,
            name="KHSD Spark Chatbot",
            instructions=instructions,
            tools=[query_ps_finance],
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
        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=self.history_limit,
            order="desc",
            context=context,
        )
        thread_items = list(reversed(items_page.data))
        if input_user_message and (not thread_items or thread_items[-1].id != input_user_message.id):
            thread_items.append(input_user_message)
        agent_input = await simple_to_agent_input(thread_items) if thread_items else []
        result = Runner.run_streamed(
            self.assistant_agent,
            agent_input,
            context=agent_context,
        )
        async for event in stream_agent_response(agent_context, result):
            yield event
