import json
import math
import os
import pathlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from uuid import UUID

from galcon import Galaxy, Item, parse
from tqdm import tqdm

GAMES = pathlib.Path("data/games")
RECORDS = pathlib.Path("data/fleet_movements.json")


def make_record(gid: UUID, t: float, fleet: Item, source: Item, target: Item):
    return {
        "game_id": str(gid),
        "fleet_id": str(fleet.entity_id),
        "t": round(t, 4),
        "fleet_ships": fleet.ships,
        "fleet_x": fleet.x,
        "fleet_y": fleet.y,
        "fleet_r": fleet.radius,
        "source_x": source.x,
        "source_y": source.y,
        "source_r": source.radius,
        "target_x": target.x,
        "target_y": target.y,
        "target_r": target.radius,
        "source_target_dist": round(
            math.hypot(source.x - target.x, source.y - target.y), 4
        ),
    }


def current_tick_records(g: Galaxy):
    fleets = [f for f in g.items.values() if f.type == "fleet"]
    for fleet in fleets:
        source, target = g.items[fleet.source], g.items[fleet.target]
        yield make_record(g.game_id, g.t, fleet, source, target)


def load_records(gamefile):
    galaxy = Galaxy()
    records = []
    with open(GAMES / gamefile, "r") as fp:
        for line in fp:
            parse(galaxy, line)
            if line.startswith("/TICK"):
                records.extend(current_tick_records(galaxy))
    # TODO: we should do game-level pruning here. any fleets that only exist for one tick, any fleets present at the last tick, etc.
    return list(map(lambda r: json.dumps(r) + "\n", records))


def main():
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ppe:
        futs = [ppe.submit(load_records, gamefile) for gamefile in os.listdir(GAMES)]
        with open(RECORDS, "w") as recordfile:
            for fut in tqdm(as_completed(futs), total=len(futs)):
                recordfile.writelines(fut.result())


if __name__ == "__main__":
    main()
