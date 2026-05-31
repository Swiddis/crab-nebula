import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum

import glicko2
from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm.decl_api import declarative_base
from sqlmodel import Field, SQLModel, select

# todo: probably don't hardcode, but since this only runs on localhost i don't really care for now
DATABASE_URL = (
    "postgresql+asyncpg://matchserv_user:matchserv_pass@localhost:5432/matchserv"
)


class MatchState(str, Enum):
    # the match hasn't started yet / a bot hasn't registered to the match yet
    INIT = "init"
    # both bots have registered to the match and it's allegedly in progress
    PLAY = "play"
    # the winning bot has reported its result, but rating updates haven't been tallied yet
    DONE = "done"
    # the match is concluded and has been accounted for in rating calculations
    RATED = "rated"


class MatchRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    match_state: MatchState = Field(index=True)
    state_hash: str = Field(index=True, unique=True)
    create_time: datetime = Field(index=True)
    modify_time: datetime = Field(index=True)
    player1: int | None
    player2: int | None
    duration: float | None
    winner: int | None


class Player(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    model_version: int = Field(index=True)
    name: str = Field(index=True)
    rating: int
    rd: float
    model: dict = Field(sa_type=JSONB)


class MatchResult(BaseModel):
    winner: int
    duration: float


class MakePlayerRequest(BaseModel):
    model_version: int
    name: str
    model: dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)
engine = create_async_engine(DATABASE_URL)
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


async def reserve_state_record(state_hash: str, db: AsyncSession):
    insert_stmt = (
        insert(MatchRecord)
        .values(
            match_state=MatchState.INIT,
            state_hash=state_hash,
            create_time=datetime.now(),
            modify_time=datetime.now(),
        )
        .on_conflict_do_nothing(index_elements=["state_hash"])
    )
    await db.execute(insert_stmt)
    await db.commit()
    return


async def get_match_record(state_hash: str, db: AsyncSession):
    # the entropy for random small maps isn't _that_ high,
    # we might have a collision eventually if we don't time-bind matches
    select_paired_match = (
        select(MatchRecord)
        .where(MatchRecord.state_hash == state_hash)
        .limit(1)
        .with_for_update()
    )
    result = await db.execute(select_paired_match)
    return result.scalars().first()


@app.post("/match/{state_hash}")
async def make_match(
    state_hash: str, model_version: int, db: AsyncSession = Depends(get_db)
):
    await reserve_state_record(state_hash, db)
    paired_match = await get_match_record(state_hash, db)
    if paired_match is None:
        raise ValueError("fatal: reserved record does not exist")
    if paired_match.player1 is not None:
        paired_player = await db.get_one(Player, paired_match.player1)
        select_opponent = (
            select(Player)
            .where(Player.model_version == model_version)
            .where(Player.id != paired_player.id)
            .order_by(func.abs(Player.rating - paired_player.rating))
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
            "model": opponent.model,
        }
    else:
        select_match_players = (
            select(Player)
            .where(Player.model_version == model_version)
            .order_by(-Player.rd)
            .limit(32)
            .with_for_update(skip_locked=True, read=True)
        )
        result = await db.execute(select_match_players)
        maybe_players = list(result.scalars().all())
        player = random.choices(
            maybe_players, weights=[1 / (p.rd + 1) for p in maybe_players]
        )[0]
        paired_match.modify_time = datetime.now()
        paired_match.player1 = player.id
        db.add(paired_match)
        await db.commit()
        return {
            "player": 1,
            "model": player.model,
        }


@app.post("/match/{state_hash}/complete")
async def complete_match(
    state_hash: str, result: MatchResult, db: AsyncSession = Depends(get_db)
):
    match_record = await get_match_record(state_hash, db)
    if not match_record:
        raise ValueError("attempted to complete a nonexistent match")
    match_record.match_state = MatchState.DONE
    match_record.winner = result.winner
    match_record.duration = result.duration
    match_record.modify_time = datetime.now()
    db.add(match_record)
    await db.commit()
    return {"acknowledged": True}


@app.post("/player")
async def make_player(player: MakePlayerRequest, db: AsyncSession = Depends(get_db)):
    mp = Player(
        model_version=player.model_version,
        name=player.name,
        model=player.model,
        rating=1500,
        rd=300,
    )
    db.add(mp)
    await db.commit()
    return {"acknowledged": True}
