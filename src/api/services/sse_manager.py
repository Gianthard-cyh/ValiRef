"""SSE connection manager for real-time progress updates."""

import asyncio
from typing import Dict, List


class SSEManager:
    """Manages SSE connections and broadcasts messages to clients."""

    def __init__(self):
        self.connections: Dict[str, List[asyncio.Queue]] = {}

    async def connect(self, task_id: str) -> asyncio.Queue:
        """Register a new SSE connection for a task."""
        queue = asyncio.Queue()
        self.connections.setdefault(task_id, []).append(queue)
        return queue

    async def disconnect(self, task_id: str, queue: asyncio.Queue):
        """Unregister an SSE connection."""
        if task_id in self.connections:
            try:
                self.connections[task_id].remove(queue)
            except ValueError:
                pass
            if not self.connections[task_id]:
                del self.connections[task_id]

    async def broadcast(self, task_id: str, data: dict):
        """Broadcast a message to all connections for a task."""
        queues = self.connections.get(task_id, [])
        for queue in queues:
            try:
                await queue.put(data)
            except Exception:
                pass

    def get_connection_count(self, task_id: str) -> int:
        """Get the number of active connections for a task."""
        return len(self.connections.get(task_id, []))
