import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum

import glicko2
from fastapi import Depends, FastAPI
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm.decl_api import declarative_base
from sqlmodel import Field, SQLModel, select

# todo: probably don't hardcode, but since this only runs on localhost i don't really care for now
DATABASE_URL = (
    "postgresql+asyncpg://matchserv_user:matchserv_pass@localhost:5432/matchserv"
)


class MatchState(str, Enum):
    INIT = "init"
    PLAY = "play"
    DONE = "done"


class MatchRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    match_state: MatchState = Field(index=True)
    state_hash: str = Field(index=True)
    create_time: datetime = Field(index=True)
    modify_time: datetime = Field(index=True)
    player1: int
    player2: int
    duration: float
    winner: int


class MatchPlayer(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    model_version: int = Field(index=True)
    name: str = Field(index=True)
    rating: int
    rd: float
    model: dict = Field(sa_type=JSONB)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()
_server_start_time = time.time()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@app.get("/")
async def health(db: AsyncSession = Depends(get_db)):
    global _server_start_time

    try:
        _res = await db.execute(text("SELECT 1"))
        await db.commit()
        db_healthy = True
    except Exception:
        db_healthy = False

    return {
        "whoami": "matchserv",
        "matchserv_healthy": True,
        "db_healthy": db_healthy,
        "uptime": round(time.time() - _server_start_time, 1),
    }


@app.post("/match/{state_hash}")
async def make_match(
    state_hash: str, model_version: int, db: AsyncSession = Depends(get_db)
):
    now = datetime.now()
    select_paired_match = (
        select(MatchRecord)
        .where(MatchRecord.state_hash == state_hash)
        .where(MatchRecord.create_time > now - timedelta(minutes=1))
        .limit(1)
        .with_for_update()
    )
    result = await db.execute(select_paired_match)
    if paired_match := result.scalars().first():
        paired_player = await db.get_one(MatchPlayer, paired_match.player1)
        select_opponent = (
            select(MatchPlayer)
            .where(MatchPlayer.model_version == model_version)
            .where(MatchPlayer.id != paired_player.id)
            .where(MatchPlayer.id != 0)
            .order_by(func.abs(MatchPlayer.rating - paired_player.rating))
            .limit(10)
        )
        result = await db.execute(select_opponent)
        maybe_opponents = list(result.scalars().all())
        opponent = random.choice(maybe_opponents)
        if opponent.id is None:
            raise ValueError("fatal: received missing primary key")

        paired_match.match_state = MatchState.PLAY
        paired_match.modify_time = datetime.now()
        paired_match.player2 = opponent.id
        db.add(paired_match)
        await db.commit()
        return {
            "player": 2,
            "model": opponent.model_config,
        }
    else:
        select_match_players = (
            select(MatchPlayer)
            .where(MatchPlayer.model_version == model_version)
            .where(MatchPlayer.id != 0)
            .where(func.random() < 0.5)
            .order_by(-MatchPlayer.rd)
            .limit(64)
        )
        result = await db.execute(select_match_players)
        maybe_players = list(result.scalars().all())
        player = random.choices(
            maybe_players, weights=[1 / (p.rd + 1) for p in maybe_players]
        )[0]
        paired_match = MatchRecord(
            match_state=MatchState.INIT,
            state_hash=state_hash,
            create_time=datetime.now(),
            modify_time=datetime.now(),
            player1=player.id or 0,
            player2=0,
            duration=0.0,
            winner=0,
        )
        db.add(paired_match)
        await db.commit()
        return {
            "player": 1,
            "model": player.model_config,
        }
