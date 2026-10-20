from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemberType, Room, RoomMember, User


async def require_room(session: AsyncSession, room_id: uuid.UUID, user: User) -> Room:
    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    membership = await session.scalar(
        select(RoomMember.id).where(
            RoomMember.room_id == room_id,
            RoomMember.member_type == MemberType.USER,
            RoomMember.member_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a room member")
    return room
