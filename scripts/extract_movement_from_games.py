import json
import math
import os
import pathlib
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any
from uuid import UUID

from galcon import Galaxy, Item, parse
from tqdm import tqdm

GAMES = pathlib.Path("data/games")
RECORDS = pathlib.Path("data/fleet_movements.json")

Record = dict[str, Any]


def make_record(gid: UUID, t: float, fleet: Item, source: Item, target: Item) -> Record:
    return {
        "game_id": str(gid),
        "fleet_id": str(fleet.entity_id),
        "source_x": source.x,
        "source_y": source.y,
        "source_r": source.radius,
        "target_x": target.x,
        "target_y": target.y,
        "target_r": target.radius,
        "source_target_dist": round(
            math.hypot(source.x - target.x, source.y - target.y), 4
        ),
        "t_global": round(t, 4),
        "fleet_ships": fleet.ships,
        "fleet_x": fleet.x,
        "fleet_y": fleet.y,
        "fleet_r": fleet.radius,
    }


def current_tick_records(g: Galaxy):
    fleets = [f for f in g.items.values() if f.type == "fleet"]
    for fleet in fleets:
        source, target = g.items[fleet.source], g.items[fleet.target]
        yield make_record(g.game_id, g.t, fleet, source, target)


def enrich(records: list[Record]):
    initial_sizes = defaultdict(lambda: 0.0)
    initial_t = defaultdict(lambda: math.inf)
    for record in records:
        initial_sizes[record["fleet_id"]] = max(
            initial_sizes[record["fleet_id"]], record["fleet_ships"]
        )
        initial_t[record["fleet_id"]] = min(
            initial_t[record["fleet_id"]], record["t_global"]
        )
    for record in records:
        record["fleet_size"] = initial_sizes[record["fleet_id"]]
        record["t"] = record["t_global"] - initial_t[record["fleet_id"]]


def prune(records: list[Record], galaxy: Galaxy):
    # prune fleets that existed at the end of the game (can't extract complete movement data from them since they never finished)
    survivor_fleets = set(str(i.entity_id) for i in galaxy.items.values())
    # prune any fleets that were very short lived
    ctr = Counter(rec["fleet_id"] for rec in records)
    unique_fleets = set()
    for id, ct in ctr.items():
        if ct <= 4:
            unique_fleets.add(str(id))
    # prune fleets that were redirected
    tgts = {}
    redir_fleets = set()
    for rec in records:
        if rec["fleet_id"] not in tgts:
            tgts[rec["fleet_id"]] = (rec["target_x"], rec["target_y"])
        elif (rec["target_x"], rec["target_y"]) != tgts[rec["fleet_id"]]:
            redir_fleets.add(rec["fleet_id"])

    prune_fleets = survivor_fleets | unique_fleets | redir_fleets
    return filter(lambda r: r["fleet_id"] not in prune_fleets, records)


def load_records(gamefile):
    galaxy = Galaxy()
    records: list[Record] = []
    with open(GAMES / gamefile, "r") as fp:
        for line in fp:
            parse(galaxy, line)
            if line.startswith("/TICK"):
                records.extend(current_tick_records(galaxy))
    enrich(records)
    return list(map(lambda r: json.dumps(r) + "\n", prune(records, galaxy)))


def main():
    record_cts = []

    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ppe:
        futs = [ppe.submit(load_records, gamefile) for gamefile in os.listdir(GAMES)]
        with open(RECORDS, "w") as recordfile:
            for fut in tqdm(as_completed(futs), total=len(futs)):
                res = fut.result()
                record_cts.append(len(res))
                recordfile.writelines(res)
    print(
        f"extracted {sum(record_cts)} records ({round(sum(record_cts) / len(record_cts), 1)}/game)"
    )


if __name__ == "__main__":
    main()
