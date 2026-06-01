import logging
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum

import glicko2
from fastapi import BackgroundTasks, Depends, FastAPI
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
logger = logging.Logger(__name__)


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
    win_score: float | None
    loss_score: float | None


class Player(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    model_version: int = Field(index=True)
    name: str = Field(index=True, unique=True)
    rating: int
    rd: int
    vol: float
    model: dict = Field(sa_type=JSONB)


class MatchResult(BaseModel):
    winner: int
    duration: float
    win_score: float
    loss_score: float
    opponent: str


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
    state_hash: str,
    model_version: int,
    opponent: str,
    db: AsyncSession = Depends(get_db),
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
            .where(func.abs(Player.rating - paired_player.rating) < 50)
        )
        result = await db.execute(select_opponent)
        maybe_opponents = list(result.scalars().all())
        opp = random.choice(maybe_opponents)
        if opp.id is None:
            raise ValueError("fatal: received missing primary key")

        paired_match.match_state = MatchState.PLAY
        paired_match.modify_time = datetime.now()
        paired_match.player2 = opp.id
        db.add(paired_match)
        await db.commit()
        return {
            "player": 2,
            "model": opp.model,
        }
    else:
        maybe_opponent = await db.execute(
            select(Player)
            .where(Player.model_version == 0)
            .where(Player.name == opponent)
        )
        opp = maybe_opponent.scalars().first()
        if opp is not None:
            # TODO: figure out how to make sure this is guaranteed to hit something
            select_match_players = (
                select(Player)
                .where(Player.model_version == model_version)
                .order_by(func.abs(Player.rating - opp.rating))
                .limit(32)
            )
        else:
            select_match_players = (
                select(Player)
                .where(Player.model_version == model_version)
                .order_by(Player.rd.desc(), Player.rating.desc())
                .limit(32)
            )
        result = await db.execute(select_match_players)
        maybe_players = list(result.scalars().all())
        if opp is not None:
            thresh = 2 * abs(maybe_players[0].rating - opp.rating)
            maybe_players = [
                p for p in maybe_players if abs(p.rating - opp.rating) < 2 * thresh
            ]
        player = random.choice(maybe_players)
        paired_match.modify_time = datetime.now()
        paired_match.player1 = player.id
        if opp is not None:
            paired_match.player2 = opp.id
        db.add(paired_match)
        await db.commit()
        return {
            "player": 1,
            "model": player.model,
        }


async def rate_match(db: AsyncSession, m: MatchRecord) -> bool:
    if m.player1 is None or m.player2 is None:
        return False
    # no deadlock plz
    p_low_id, p_high_id = (
        min(m.player1, m.player2),
        max(m.player1, m.player2),
    )
    low_result = await db.execute(
        select(Player).where(Player.id == p_low_id).with_for_update(skip_locked=True)
    )
    locked_low = low_result.scalar_one_or_none()
    if locked_low is None:
        return False

    high_result = await db.execute(
        select(Player).where(Player.id == p_high_id).with_for_update(skip_locked=True)
    )
    locked_high = high_result.scalar_one_or_none()
    if locked_high is None:
        return False

    p1 = locked_low if m.player1 == p_low_id else locked_high
    p2 = locked_high if m.player1 == p_low_id else locked_low
    g2_p1 = glicko2.Player(rating=p1.rating, rd=p1.rd, vol=p1.vol)
    g2_p2 = glicko2.Player(rating=p2.rating, rd=p2.rd, vol=p2.vol)
    p1_score = m.win_score if m.winner == 1 else m.loss_score
    p2_score = m.win_score if m.winner == 2 else m.loss_score
    g2_p1.update_player([p2.rating], [p2.rd], [p1_score])
    g2_p2.update_player([p1.rating], [p1.rd], [p2_score])

    p1.rating = g2_p1.getRating()
    p1.rd = round(g2_p1.getRd())
    p1.vol = g2_p1.vol
    p2.rating = g2_p2.getRating()
    p2.rd = round(g2_p2.getRd())
    p2.vol = g2_p2.vol

    m.match_state = MatchState.RATED
    m.modify_time = datetime.now()

    db.add(p1)
    db.add(p2)
    db.add(m)
    await db.commit()
    return True


@app.post("/match/{state_hash}/complete")
async def complete_match(
    state_hash: str,
    result: MatchResult,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    match_record = await get_match_record(state_hash, db)
    if not match_record:
        raise ValueError("attempted to complete a nonexistent match")

    if match_record.match_state in (MatchState.DONE, MatchState.RATED):
        return {"acknowledged": True}  # already counted

    if match_record.player2 is None:
        opp_exec = await db.execute(
            select(Player).where(Player.name == result.opponent)
        )
        opp = opp_exec.scalars().first()
        if opp is None:
            return {"acknowledged": False, "reason": "opponent is not registered"}
        match_record.player2 = opp.id

    match_record.match_state = MatchState.DONE
    match_record.winner = result.winner
    match_record.duration = result.duration
    match_record.modify_time = datetime.now()
    match_record.win_score = result.win_score
    match_record.loss_score = result.loss_score
    db.add(match_record)
    await db.commit()

    bg.add_task(rate_match, db, match_record)

    return {"acknowledged": True}


@app.post("/player")
async def make_player(player: MakePlayerRequest, db: AsyncSession = Depends(get_db)):
    mp = Player(
        model_version=player.model_version,
        name=player.name,
        model=player.model,
        rating=1500,
        rd=300,
        vol=0.06,
    )
    db.add(mp)
    await db.commit()
    return {"acknowledged": True}


@app.get("/player")
async def get_players(model_version: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Player).where(Player.model_version == model_version))
    return res.scalars().all()
