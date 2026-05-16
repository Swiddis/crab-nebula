from collections import defaultdict

import galcon_entities as ge
import gbotlib as gbl

SEND_PROP, DELTA_PROP, HOLD_PROP, SWITCH_PROP = 0.425, 0.300, 0.200, 0.300


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

    for planet in planets["ally"]:
        i, s = 0, planet.ships
        while s >= HOLD_PROP * planet.production and i < len(targets):
            target = targets[i]
            if (
                ingress[target][0] - ingress[target][1]
                > (1.0 + SWITCH_PROP) * target.ships
            ):
                i += 1
                continue

            gbl.send(f"/SEND {round(SEND_PROP * 100)} {planet.n} {target.n}")
            i, s = i + 1, s * DELTA_PROP


if __name__ == "__main__":
    gbl.run(bot)
