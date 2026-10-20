from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, func, select

from app.api.common import require_room
from app.dependencies import CurrentUser, ServicesDep, SessionDep
from app.models import (
    Bot,
    MemberType,
    Room,
    RoomMember,
    SenderType,
    Task,
    TaskStatus,
)
from app.schemas import (
    BotOut,
    MessageCreate,
    MessageOut,
    RoomCreate,
    RoomDetail,
    RoomOut,
)

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomOut])
async def list_rooms(user: CurrentUser, session: SessionDep) -> list[RoomOut]:
    rooms = (
        await session.scalars(
            select(Room)
            .join(
                RoomMember,
                (RoomMember.room_id == Room.id) & (RoomMember.member_type == MemberType.USER),
            )
            .where(RoomMember.member_id == user.id)
            .order_by(Room.created_at.desc())
        )
    ).all()
    return [RoomOut.model_validate(room) for room in rooms]


async def _room_detail(session, room: Room) -> RoomDetail:
    bots = (
        await session.scalars(
            select(Bot)
            .join(
                RoomMember,
                (RoomMember.member_id == Bot.id) & (RoomMember.member_type == MemberType.BOT),
            )
            .where(RoomMember.room_id == room.id)
            .order_by(Bot.name)
        )
    ).all()
    pending = await session.scalar(
        select(func.count(Task.id)).where(
            Task.room_id == room.id,
            Task.status.in_([TaskStatus.QUEUED, TaskStatus.RUNNING]),
        )
    )
    return RoomDetail(
        **RoomOut.model_validate(room).model_dump(),
        bots=[BotOut.model_validate(bot) for bot in bots],
        tasks_pending=pending or 0,
    )


@router.post("", response_model=RoomDetail, status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: RoomCreate,
    user: CurrentUser,
    session: SessionDep,
) -> RoomDetail:
    bot_ids = list(dict.fromkeys(payload.bot_ids))
    bots: list[Bot] = []
    if bot_ids:
        bots = list((await session.scalars(select(Bot).where(Bot.id.in_(bot_ids)))).all())
        if len(bots) != len(bot_ids):
            raise HTTPException(status_code=422, detail="One or more bots do not exist")

    room = Room(
        id=uuid.uuid4(),
        name=payload.name.strip(),
        description=payload.description.strip(),
        created_by=user.id,
    )
    session.add(room)
    await session.flush()
    session.add(
        RoomMember(
            room_id=room.id,
            member_type=MemberType.USER,
            member_id=user.id,
        )
    )
    for bot in bots:
        session.add(
            RoomMember(
                room_id=room.id,
                member_type=MemberType.BOT,
                member_id=bot.id,
            )
        )
    await session.commit()
    return await _room_detail(session, room)


@router.get("/{room_id}", response_model=RoomDetail)
async def get_room(
    room_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> RoomDetail:
    room = await require_room(session, room_id, user)
    return await _room_detail(session, room)


@router.post("/{room_id}/bots/{bot_id}", response_model=RoomDetail)
async def add_bot(
    room_id: uuid.UUID,
    bot_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> RoomDetail:
    room = await require_room(session, room_id, user)
    bot = await session.get(Bot, bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    existing = await session.scalar(
        select(RoomMember.id).where(
            RoomMember.room_id == room_id,
            RoomMember.member_type == MemberType.BOT,
            RoomMember.member_id == bot_id,
        )
    )
    if existing is None:
        session.add(
            RoomMember(
                room_id=room_id,
                member_type=MemberType.BOT,
                member_id=bot_id,
            )
        )
        await session.commit()
    return await _room_detail(session, room)


@router.delete("/{room_id}/bots/{bot_id}", response_model=RoomDetail)
async def remove_bot(
    room_id: uuid.UUID,
    bot_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> RoomDetail:
    room = await require_room(session, room_id, user)
    await session.execute(
        delete(RoomMember).where(
            RoomMember.room_id == room_id,
            RoomMember.member_type == MemberType.BOT,
            RoomMember.member_id == bot_id,
        )
    )
    await session.commit()
    return await _room_detail(session, room)


@router.get("/{room_id}/messages", response_model=list[MessageOut])
async def list_messages(
    room_id: uuid.UUID,
    user: CurrentUser,
    services: ServicesDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    after_seq: Annotated[int | None, Query(ge=0)] = None,
) -> list[MessageOut]:
    await require_room(session, room_id, user)
    messages = await services.chat.list_messages(room_id, limit=limit, after_seq=after_seq)
    return [MessageOut.model_validate(message) for message in messages]


@router.post(
    "/{room_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    room_id: uuid.UUID,
    payload: MessageCreate,
    user: CurrentUser,
    services: ServicesDep,
    session: SessionDep,
) -> MessageOut:
    await require_room(session, room_id, user)
    result = await services.chat.post_message(
        room_id,
        sender_type=SenderType.USER,
        sender_id=user.id,
        sender_name=user.display_name,
        content=payload.content,
    )
    return MessageOut.model_validate(result.message)
