from __future__ import annotations

import asyncio
import json


class SSEBroker:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: dict) -> None:
        serialized = json.dumps(event)
        stale: list[asyncio.Queue[str]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(serialized)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)


async def sse_generator(queue: asyncio.Queue[str]):
    yield "event: ready\ndata: {}\n\n"
    while True:
        payload = await queue.get()
        yield f"data: {payload}\n\n"
