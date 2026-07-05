import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.reminders import reminder_loop
from app.routers import (
    branches,
    chat,
    events,
    mail,
    notifications,
    parents,
    students,
    trainers,
    training_groups,
    training_sessions,
)
from app.security import WRITE_METHODS, check_api_write_key, is_public_write_path


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


app = FastAPI(title="Judo club", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_write_key_middleware(request: Request, call_next):
    if request.method in WRITE_METHODS and not is_public_write_path(request.url.path):
        try:
            check_api_write_key(request.headers.get("X-API-Key"))
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


app.include_router(trainers.router)
app.include_router(branches.router)
app.include_router(parents.router)
app.include_router(students.router)
app.include_router(mail.router)
app.include_router(training_groups.router)
app.include_router(training_sessions.router)
app.include_router(notifications.router)
app.include_router(chat.router)
app.include_router(events.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
