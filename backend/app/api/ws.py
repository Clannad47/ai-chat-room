from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.models import MemberType, Room, RoomMember, User

router = APIRouter(prefix="/ws", tags=["realtime"])


@router.websocket("/rooms/{room_id}")
async def room_socket(websocket: WebSocket, room_id: uuid.UUID) -> None:
    services = websocket.app.state.services
    async with services.session_factory() as session:
        room = await session.get(Room, room_id)
        user = await session.scalar(
            select(User).where(User.username == services.settings.default_user_name)
        )
        member = None
        if user is not None:
            member = await session.scalar(
                select(RoomMember.id).where(
                    RoomMember.room_id == room_id,
                    RoomMember.member_type == MemberType.USER,
                    RoomMember.member_id == user.id,
                )
            )

    if room is None or member is None:
        await websocket.close(code=4404)
        return

    await services.hub.connect(room_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "room_id": str(room_id), "payload": {}})
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong", "room_id": str(room_id)})
    except WebSocketDisconnect:
        pass
    finally:
        await services.hub.disconnect(room_id, websocket)
