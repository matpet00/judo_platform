import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.reminders import reminder_loop
from app.routers import (
    admin,
    branches,
    chat,
    events,
    mail,
    notifications,
    parents,
    public_share,
    registration,
    students,
    trainers,
    training_groups,
    training_sessions,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    await init_db()
    reminder_task = asyncio.create_task(reminder_loop())
    try:
        yield
    finally:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass


_docs_url = "/docs" if settings.enable_api_docs else None
_redoc_url = "/redoc" if settings.enable_api_docs else None
_openapi_url = "/openapi.json" if settings.enable_api_docs else None

app = FastAPI(
    title="Judo klub Orlová",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(admin.router)
app.include_router(trainers.router)
app.include_router(branches.router)
app.include_router(parents.router)
app.include_router(registration.router)
app.include_router(students.router)
app.include_router(mail.router)
app.include_router(training_groups.router)
app.include_router(training_sessions.router)
app.include_router(notifications.router)
app.include_router(chat.router)
app.include_router(events.router)
app.include_router(public_share.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
