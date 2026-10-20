from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import WebSocket

from app.models import MemberType, now_ms

logger = logging.getLogger(__name__)


def make_event(
    event_type: str,
    room_id: uuid.UUID,
    payload: dict[str, Any],
    *,
    seq: int | None = None,
) -> dict[str, Any]:
    return {
        "type": event_type,
        "room_id": str(room_id),
        "seq": seq,
        "payload": payload,
        "ts": now_ms(),
    }


class RealtimeHub:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(room_id, set()).add(websocket)

    async def disconnect(self, room_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(room_id)
            if sockets is not None:
                sockets.discard(websocket)
                if not sockets:
                    self._connections.pop(room_id, None)

    async def broadcast(
        self,
        room_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        seq: int | None = None,
    ) -> None:
        event = make_event(event_type, room_id, payload, seq=seq)
        async with self._lock:
            sockets = list(self._connections.get(room_id, ()))
        if not sockets:
            return

        results = await asyncio.gather(
            *(self._send(socket, event) for socket in sockets),
            return_exceptions=True,
        )
        for socket, result in zip(sockets, results, strict=True):
            if result is not None:
                await self.disconnect(room_id, socket)

    @staticmethod
    async def _send(websocket: WebSocket, event: dict[str, Any]) -> None:
        try:
            await asyncio.wait_for(websocket.send_json(event), timeout=3)
        except Exception as exc:  # noqa: BLE001 - a dead socket must not break fanout
            logger.debug("WebSocket send failed: %s", exc)
            raise


__all__ = ["MemberType", "RealtimeHub", "make_event"]
