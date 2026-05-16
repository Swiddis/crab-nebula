import gbotlib as gbl
import math
from knapsack01.BBKnapsack import BBKnapsack

def send_ships(proportion, source, target):
    gbl.send(f'/SEND {math.ceil(proportion)} {source.n} {target.n}')

def knapsack(planets, capacity):
    plist = list(planets.items())
    plist.sort(key=lambda p:p[1][1])
    profits = [p[1][0] for p in plist]
    weights = [p[1][1] for p in plist]
    solution = BBKnapsack(capacity, profits, weights).maximize()[1]
    return [planet for planet, i in zip((p[0] for p in plist), solution) if i > 0]

# Categorize all planets into ally, neutral, or enemy.
def process_planets(galaxy):
    planets = {
        'ally': [],
        'enemy': [],
        'neutral': []
    }
    for planet in galaxy.planets.values():
        if planet.owner == galaxy.you:
            planets['ally'].append(planet)
        elif planet.is_neutral(galaxy.users):
            planets['neutral'].append(planet)
        else:
            planets['enemy'].append(planet)
    return planets

# Determine how many ships of each player are going to each planet.
def process_fleets(galaxy):
    movements = {planet.n: [0,0] for planet in galaxy.planets.values()}
    for fleet in galaxy.fleets.values():
        if fleet.owner == galaxy.you:
            movements[fleet.target][0] += fleet.ships
        else:
            movements[fleet.target][1] += fleet.ships             
    return movements

# Last-resort strategy: send all ships to affordable neutral planets, maximizing production.
# This is equivalent to the knapsack problem, but for speed purposes we just go in order of production
def hail_mary(planets):
    available_ships = sum(planet.ships for planet in planets['ally'])
    targets = knapsack({p: (p.production, p.ships + 1) for p in planets['neutral']}, available_ships)
    
    for target in targets:
        percent = min(100 * (target.ships + 1) / available_ships, 100)
        for planet in planets['ally']:
            send_ships(percent, planet, target)
            available_ships -= percent * planet.ships
            if available_ships <= 0:
                return

# After determining what planets are in danger that can be saved, run a defense
def enact_defense(planets, scores):
    planets.sort(key=lambda p: p.production, reverse=True) # Prioritize higher production
    for planet in planets:
        if planet.n in scores and scores[planet.n] < 0:
            friends = sorted(
                [friend for friend in planets if scores[friend.n] > 0],
                key=lambda friend: planet.distance(friend)
            )
            for friend in friends:
                prop = min(100 *  min(scores[friend.n], planet.ships) / max(friend.ships, 0.01), 100)
                scores[friend.n] -= friend.ships * prop / 100
                scores[planet.n] += friend.ships * prop / 100
                send_ships(prop, friend, planet)
                if scores[planet.n] >= 0:
                    break
    return scores


# If planets are under attack with more ships than they have available, send aide
def defend(planets, movements):
    scores = {}
    for planet in planets['ally']:
        scores[planet.n] = planet.ships + movements[planet.n][0] - movements[planet.n][1]
    while sum(scores.values()) < 0: # If we cannot defend everything, sacrifice some planets
        sacrifice = min([planet for planet in planets['ally'] if planet.n in scores], key=lambda p: -scores[p.n] / p.production)
        del scores[sacrifice.n]

    if len(scores) == 0: # If no allied planets are defendable
        hail_mary(planets)
        return None
    else:
        resources = enact_defense(planets['ally'], scores)
        return resources if sum(resources.values()) > 0 else None

def invade(planets, resources, movements):
    scores = {}
    for planet in planets['neutral']:
        scores[planet.n] = planet.ships - movements[planet.n][0] + movements[planet.n][1] + 1
    for planet in planets['enemy']:
        scores[planet.n] = planet.ships + movements[planet.n][0] + movements[planet.n][1] + planet.production / 5
    
    targets = knapsack({p: (p.production, scores[p.n]) for p in planets['neutral'] + planets['enemy']}, sum(resources.values()))
    targets.sort(key=lambda p: p.production, reverse=True)

    for target in targets:
        attackers = sorted(
                [attacker for attacker in planets['ally'] if attacker.n in resources and resources[attacker.n] > 0],
                key=lambda a: a.distance(target)
            )
        for attacker in attackers:
            prop = min(100 * min(resources[attacker.n], target.ships) / max(attacker.ships, 0.01), 100)
            resources[attacker.n] -= attacker.ships * prop / 100
            scores[target.n] -= attacker.ships * prop / 100
            send_ships(prop, attacker, target)
            if scores[target.n] < 0:
                break

def bot(galaxy):
    try:
        planets = process_planets(galaxy)
        movements = process_fleets(galaxy)
        resources = defend(planets, movements)
        if resources is not None:
            invade(planets, resources, movements)
    except Exception as e:
        gbl.log('Encountered exception: ' + repr(e))

if __name__ == '__main__':
    gbl.run(bot)
