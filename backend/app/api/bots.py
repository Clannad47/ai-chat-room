from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, ServicesDep, SessionDep
from app.models import Bot
from app.schemas import BotCreate, BotOut

router = APIRouter(prefix="/bots", tags=["bots"])


@router.get("", response_model=list[BotOut])
async def list_bots(user: CurrentUser, session: SessionDep) -> list[BotOut]:
    bots = (
        await session.scalars(select(Bot).where(Bot.owner_id == user.id).order_by(Bot.created_at))
    ).all()
    return [BotOut.model_validate(bot) for bot in bots]


@router.post("", response_model=BotOut, status_code=status.HTTP_201_CREATED)
async def create_bot(
    payload: BotCreate,
    user: CurrentUser,
    session: SessionDep,
    services: ServicesDep,
) -> BotOut:
    name = payload.name.strip()
    existing = await session.scalar(select(Bot.id).where(func.lower(Bot.name) == name.lower()))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Bot name already exists")

    unknown = [tool for tool in payload.allowed_tools if tool not in services.registry.names()]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown tools: {', '.join(unknown)}")

    bot = Bot(
        id=uuid.uuid4(),
        owner_id=user.id,
        name=name,
        description=payload.description.strip(),
        persona=payload.persona.strip(),
        model=payload.model.strip() if payload.model else None,
        temperature=payload.temperature,
        allowed_tools=list(dict.fromkeys(payload.allowed_tools)),
        max_steps=payload.max_steps,
    )
    session.add(bot)
    await session.commit()
    return BotOut.model_validate(bot)
