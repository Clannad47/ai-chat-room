from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.api.common import require_room
from app.dependencies import CurrentUser, ServicesDep, SessionDep
from app.models import Run, RunStatus, Task, TaskStatus, now_ms
from app.schemas import RunOut, TaskDetail, TaskOut

router = APIRouter(tags=["tasks"])


def _task_detail(task: Task) -> TaskDetail:
    return TaskDetail(
        **TaskOut.model_validate(task).model_dump(),
        assignee_name=task.assignee.name,
        runs=[RunOut.model_validate(run) for run in task.runs],
    )


@router.get("/rooms/{room_id}/tasks", response_model=list[TaskOut])
async def list_tasks(
    room_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[TaskOut]:
    await require_room(session, room_id, user)
    tasks = (
        await session.scalars(
            select(Task)
            .where(Task.room_id == room_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [TaskOut.model_validate(task) for task in tasks]


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> TaskDetail:
    task = await session.scalar(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.runs).selectinload(Run.tool_calls))
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await require_room(session, task.room_id, user)
    return _task_detail(task)


@router.post("/tasks/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(
    task_id: uuid.UUID,
    user: CurrentUser,
    services: ServicesDep,
    session: SessionDep,
) -> TaskOut:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await require_room(session, task.room_id, user)
    if task.status not in {TaskStatus.QUEUED, TaskStatus.RUNNING}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is already {task.status.value}",
        )

    task.status = TaskStatus.CANCELLED
    task.error = "Cancelled by user"
    task.finished_at = now_ms()
    await session.execute(
        update(Run)
        .where(Run.task_id == task.id, Run.status == RunStatus.RUNNING)
        .values(status=RunStatus.CANCELLED, error="Cancelled by user", finished_at=now_ms())
    )
    await session.commit()
    await services.hub.broadcast(
        task.room_id,
        "task.updated",
        {"task": TaskOut.model_validate(task).model_dump(mode="json")},
    )
    services.scheduler.cancel(task.id)
    return TaskOut.model_validate(task)
