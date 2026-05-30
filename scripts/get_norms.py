import json
import os
import pathlib
import random
import statistics as st
from math import hypot

from galcon import Galaxy, parse
from tqdm import tqdm

GAMES = pathlib.Path("data/games")


def load_planets(gamefile):
    galaxy = Galaxy()
    with open(GAMES / gamefile, "r") as fp:
        for line in fp:
            parse(galaxy, line)
            if line == "/SET\tSTATE\tPLAY":
                break
    return list(i for i in galaxy.items.values() if i.type == "planet")


def main():
    ships, prod, dist = [], [], []
    for gamefile in tqdm(os.listdir(GAMES)):
        planets = load_planets(gamefile)
        for planet in random.sample(planets, 5):
            ships.append(planet.ships)
            prod.append(planet.production)
        for _ in range(5):
            a, b = random.sample(planets, 2)
            dist.append(hypot(a.x - b.x, a.y - b.y))

    print(
        json.dumps(
            {
                "ships": {"mean": st.mean(ships), "stdev": st.stdev(ships)},
                "prod": {"mean": st.mean(prod), "stdev": st.stdev(prod)},
                "dist": {"mean": st.mean(dist), "stdev": st.stdev(dist)},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
