from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Services
from app.db import get_session
from app.models import User


def get_services(request: Request) -> Services:
    return request.app.state.services


async def get_current_user(
    services: Annotated[Services, Depends(get_services)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = await session.scalar(
        select(User).where(User.username == services.settings.default_user_name)
    )
    if user is None:
        raise RuntimeError("Preset user is missing; database initialization failed")
    return user


ServicesDep = Annotated[Services, Depends(get_services)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
