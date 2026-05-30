import math
from math import hypot

import galcon_entities as ge
import gbotlib as gbl
import knapsack

"""
Knapbot is a bot that works in 3 phases:

Phase 1: Knapsack Optimization
    The bot takes all currently available ships (planets and fleets) as capacity.
    The goal is to find the set of planets which, given this capacity, maximizes our production.
    The cost of controlled planets is equal to the number of enemy ships attacking it.
    The cost of enemy planets is the planet's ships + any enemy ships reinforcing it + padding for production.
    For neutral planets, for the math to work, we assume they're controlled by us but treat their ships as an additional incoming attack.

Phase 2: Shuffle
    Given the set of planets and capacity allocations, we want to perform the quickest actions to reach that state.
    Diffs are tallied: planets which have positive capacity are sources and planets with negative capacity are drains.
    Fleets are treated as sources that can't be split.
    We want to balance the accounting by directing all source surplus to all drains, minimizing the distance spent.
    In the future this might be globally optimized, for now we just do this greedily.

Phase 3: Execution
    Mostly self-explanatory.
    To improve the logistics of reallocating fleets later, we break any SEND actions into increments of 5.
"""

PROD_RATE = 1 / 50  # ships/sec
SHIP_V = 40  # units/sec

COST_PADDING = 3


# Center of all our owned planets
def center_of_constellation(galaxy: ge.Galaxy) -> tuple[float, float]:
    tx, ty, n = 0.0, 0.0, 0.0
    for p in galaxy.planets.values():
        if p.owner == galaxy.you:
            tx += p.x
            ty += p.y
            n += 1
    if n == 0:
        # we're probably dead
        return (0.0, 0.0)
    return (tx / n, ty / n)


def estimate_time_to_travel(source: tuple[float, float], target: ge.Planet):
    return hypot(source[0] - target.x, source[1] - target.y) / SHIP_V


def earnings_in_time(t: float, planet: ge.Planet) -> float:
    return max(0, t * planet.production * PROD_RATE)


def phase_1(galaxy: ge.Galaxy) -> tuple[float, dict[int, float]]:
    p_to_idx, idx_to_p, costs, prods, capacity = {}, {}, [], [], 0
    center = center_of_constellation(galaxy)  # for production math

    for i, (pid, planet) in enumerate(galaxy.planets.items()):
        p_to_idx[pid] = i
        idx_to_p[i] = pid
        # the value of a planet is the amount it can earn us by the end of the game
        prods.append(
            -planet.ships + earnings_in_time(60.0 - galaxy.t, planet)
            if planet.owner != galaxy.you
            else earnings_in_time(60.0 - galaxy.t, planet)
        )
        if planet.owner == galaxy.you:
            costs.append(0)
            capacity += planet.ships
        elif galaxy.users[planet.owner].team == 0:
            costs.append(planet.ships)
        else:
            est_production_cost = earnings_in_time(
                estimate_time_to_travel(center, planet), planet
            )
            costs.append(planet.ships + math.ceil(est_production_cost))
    for i, fleet in enumerate(galaxy.fleets.values()):
        if fleet.owner == galaxy.you:
            capacity += fleet.ships
        else:
            costs[p_to_idx[fleet.target]] += fleet.ships
    costs = [c + COST_PADDING for c in costs]

    expected_production, goal = knapsack.knapsack(costs, prods).solve(capacity)

    return expected_production, {idx_to_p[idx]: costs[idx] for idx in goal}


# returns: set of actions in terms of source, target, quantity
def phase_2(
    galaxy: ge.Galaxy, target_set: dict[int, float]
) -> list[tuple[int, int, int]]:
    action_queue = []

    targets = [galaxy.planets[t] for t in target_set]
    our_planets = [p for p in galaxy.planets.values() if p.owner == galaxy.you]
    center = center_of_constellation(galaxy)
    # prioritize high-value planets that are closer to our center
    targets.sort(key=lambda t: (-t.production, hypot(center[0] - t.x, center[1] - t.y)))

    # every planet contributes to its own cost
    for planet in our_planets:
        if planet.n in target_set:
            target_set[planet.n] -= planet.ships
        else:
            target_set[planet.n] = -planet.ships

    # since fleets aren't able to be broken down, greedily assign each fleet to its closest target that has space in the plan for it
    for fleet in galaxy.fleets.values():
        if fleet.owner != galaxy.you:
            continue
        if fleet.target in target_set and target_set[fleet.target] > 0:
            # don't redirect if we can help it
            target_set[fleet.target] -= fleet.ships
            continue
        f_targs = sorted(targets, key=lambda t: hypot(t.x - fleet.x, t.y - fleet.y))
        for target in f_targs:
            if target_set[target.n] >= fleet.ships:
                action_queue.append((fleet.n, target.n, fleet.ships))
                target_set[target.n] -= fleet.ships
                break

    # now proceed in order of highest-production, recruiting ships from neighbors
    for target in targets:
        if target_set[target.n] <= 0:
            continue
        neighbors = sorted(
            our_planets, key=lambda p: hypot(p.x - target.x, p.y - target.y)
        )
        for neighbor in neighbors:
            if target_set[neighbor.n] >= 0 or neighbor.ships == 0:
                continue
            to_send = min(-target_set[neighbor.n], target_set[target.n])
            action_queue.append((neighbor.n, target.n, to_send))
            target_set[neighbor.n] += to_send
            target_set[target.n] -= to_send

    return action_queue


def execute(galaxy, action_queue):
    for actor, target, amount in action_queue:
        if fleet := galaxy.fleets.get(actor, None):
            if target == fleet.target:
                continue
            gbl.send(f"/REDIR\t{fleet.n}\t{target}")
        elif planet := galaxy.planets.get(actor, None):
            if amount == 0:
                continue
            elif planet.ships < amount:
                gbl.log(f"error: received invalid amount ({amount} > {planet.ships})")
                continue
            pct = round(100 * amount / planet.ships)

            if amount >= 10:
                pct1, pct2 = math.floor(pct / 2), math.ceil(pct / 2)
                gbl.send(f"/SEND\t{pct1}\t{planet.n}\t{target}")
                gbl.send(f"/SEND\t{pct2}\t{planet.n}\t{target}")
            else:
                gbl.send(f"/SEND\t{pct}\t{planet.n}\t{target}")
        else:
            gbl.log("error: received an action for an entity which doesn't exist")


def bot(galaxy: ge.Galaxy):
    if galaxy.state != "play":
        return
    _expected_production, target_set = phase_1(galaxy)
    action_queue = phase_2(galaxy, target_set)
    execute(galaxy, action_queue)


if __name__ == "__main__":
    gbl.run(bot)
