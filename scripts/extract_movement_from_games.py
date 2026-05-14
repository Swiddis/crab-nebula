import json
import math
import os
import pathlib
from uuid import UUID

from galcon import Galaxy, Item, parse
from tqdm import tqdm

GAMES = pathlib.Path("data/games")
RECORDS = pathlib.Path("data/fleet_movements.json")


def make_record(gid: UUID, t: float, fleet: Item, source: Item, target: Item):
    return {
        "gid": str(gid),
        "t": t,
        "fleet_id": fleet.n,
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
        "source_target_dist": math.hypot(source.x - target.x, source.y - target.y),
    }


def load_records(g: Galaxy, records: list[dict]):
    fleets = [f for f in g.items.values() if f.type == "fleet"]
    for fleet in fleets:
        source, target = g.items[fleet.source], g.items[fleet.target]
        records.append(make_record(g.game_id, g.t, fleet, source, target))


def flush(records: list[dict]):
    with open(RECORDS, "a") as fp:
        for record in records:
            json.dump(record, fp)
            fp.write("\n")
    records.clear()


def main():
    g = Galaxy()
    records = []
    with open(RECORDS, "w") as fp:
        pass  # clear

    for gamefile in tqdm(os.listdir(GAMES)):
        with open(GAMES / gamefile, "r") as fp:
            for line in fp:
                parse(g, line)
                if line.startswith("/TICK"):
                    load_records(g, records)
        if len(records) >= 65536:
            flush(records)
    flush(records)


if __name__ == "__main__":
    main()
