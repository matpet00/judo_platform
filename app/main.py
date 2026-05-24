from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routers import branches, mail, parents, students, trainers


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Judo club", lifespan=lifespan)

app.include_router(trainers.router)
app.include_router(branches.router)
app.include_router(parents.router)
app.include_router(students.router)
app.include_router(mail.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
