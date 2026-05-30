import gbotlib as gbl
from galcon_entities import Planet, Fleet
from knapsack01 import BBKnapsack as Knapsack

ship_cost_scale, influence_cost_scale = 1.0, 0.5

def build_cdict(galaxy):
    cdict = {}
    for planet in galaxy.planets.values():
        if planet.owner == galaxy.you:
            cdict[planet.n] = 'a'
        elif planet.is_neutral(galaxy.users):
            cdict[planet.n] = 'n'
        else:
            cdict[planet.n] = 'e'
    for fleet in galaxy.fleets.values():
        if fleet.owner == galaxy.you:
            cdict[fleet.n] = 'a'
        else:
            cdict[fleet.n] = 'e'
    return cdict

def eval_costs(planets, fleets, cdict):
    costs = []
    for planet in planets:
        cost = ship_cost_scale * (
            (planet.ships + 1) if cdict[planet.n] != 'a' else -planet.ships
        )
        cost += influence_cost_scale * sum(
            (1 if cdict[inf.n] == 'e' else (-1 if cdict[inf.n] == 'a' else 0)) 
            * inf.ships / (planet.distance(inf)+1) 
            for inf in planets + fleets if inf.n != planet.n
        )
        costs.append(round(cost))
    return costs

def eval_profits(planets, fleets, cdict):
    profits = []
    for planet in planets:
        profits.append(planet.production)
    return profits

def eval_capacity(planets, fleets, cdict):
    return sum(e.ships for e in planets + fleets if cdict[e.n] == 'a')

# Returns a list of planets to target, sorted by value (approx. production / ships)
def knapsack(planets, fleets, cdict):
    # Heuristic knapsack solver performs better if list is approximately sorted by efficiency
    planets.sort(key=lambda p:p.production/(p.ships+1), reverse=True)
    weights = eval_costs(planets, fleets, cdict)
    profits = eval_profits(planets, fleets, cdict)
    capacity = eval_capacity(planets, fleets, cdict)
    solution = Knapsack(capacity, profits, weights).maximize()
    return {
        'plan': [planet for planet, include in zip(planets, solution) if include],
        'costs': {planet.n: cost for planet, cost, include in zip(planets, weights, solution) if include}
    }

# Greedily send nearest ships to targets in plan
def execute_plan(planets, fleets, cdict, costs, plan):
    entities = [e for e in planets + fleets if cdict[e.n] == 'a']
    tagged = {p.n: p.ships for p in planets if cdict[p.n] == 'a'}
    for planet in plan:
        if len(entities) == 0:
            return
        entities.sort(key=lambda e:e.distance(planet))
        sent = 0
        while sent < costs[planet.n] and len(entities) > 0:
            e = entities[0]
            if isinstance(e, Planet):
                if costs[planet.n] >= tagged[e.n]:
                    gbl.send_ships(1, e, planet)
                    sent += tagged[e.n]
                    tagged[e.n] = 0
                else:
                    gbl.send_ships(costs[planet.n] / e.ships, e, planet)
                    sent += costs[planet.n]
                    tagged[e.n] -= costs[planet.n]
                if tagged[e.n] <= 0:
                    entities.pop(0)
                    continue
            elif isinstance(e, Fleet):
                gbl.redir_fleet(e, planet)
                sent += e.ships
                entities.pop(0)

def bot(galaxy):
    if galaxy.state == 'play':
        cdict, planets, fleets = build_cdict(galaxy), list(galaxy.planets.values()), list(galaxy.fleets.values())
        solution = knapsack(planets, fleets, cdict)
        plan, costs = solution['plan'], solution['costs']
        execute_plan(planets, fleets, cdict, costs, plan)

if __name__ == '__main__':
    gbl.run(bot)
