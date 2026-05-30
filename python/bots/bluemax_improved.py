from collections import defaultdict
from math import hypot

import galcon_entities as ge
import gbotlib as gbl

SEND_PROP, DELTA_PROP, HOLD_PROP, SWITCH_SCALE = 0.425, 0.300, 0.200, 1.5


def est_prod_growth(p1: ge.Planet, p2: ge.Planet):
    return (p2.production / 50.0) * hypot(p1.x - p2.x, p1.y - p2.y) / 40.0


def bot(galaxy: ge.Galaxy):
    if galaxy.state != "play":
        return
    planets = gbl.categorize(galaxy, "planets")
    if len(planets["enemy"]) == 0:
        return
    targets = sorted(
        planets["enemy"], key=lambda p: p.production / (p.ships + 1), reverse=True
    )

    ingress = defaultdict(lambda: [0.0, 0.0])
    for fleet in galaxy.fleets.values():
        if fleet.owner == galaxy.you:
            ingress[fleet.target][0] += fleet.ships
        else:
            ingress[fleet.target][1] += fleet.ships

    pships = {planet.n: planet.ships for planet in planets["ally"]}

    for target in targets:
        planets["ally"].sort(key=lambda p: hypot(p.x - target.x, p.y - target.y))
        for planet in planets["ally"]:
            if ingress[target.n][0] - ingress[target.n][1] > (SWITCH_SCALE) * (
                target.ships + est_prod_growth(planet, target)
            ):
                break
            if pships[planet.n] < HOLD_PROP * planet.production:
                continue
            gbl.send(f"/SEND {round(SEND_PROP * 100)} {planet.n} {target.n}")
            ingress[target.n][0] += round(SEND_PROP * pships[planet.n])
            pships[planet.n] -= round(SEND_PROP * pships[planet.n])


if __name__ == "__main__":
    gbl.run(bot)
