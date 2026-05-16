import gbotlib as gbl
import math
import statistics
import random

SEND_COUNT = 1
HOLD_PROP = 0.1

def send_ships(proportion, source, target):
    proportion = min(max(proportion, 0), 1)
    percentage = round(100 * proportion)
    gbl.send(f'/SEND {percentage} {source.n} {target.n}')

def heuristic(planet, source, data):
    if planet.n == source.n:
        return (-1, 0)
    d = data[planet.n]
    if d[1] <= -HOLD_PROP * d[0]:
        return (0, 0)
    else:
        return (d[0] / (d[1] + HOLD_PROP * d[0]), 1 / planet.distance(source))

def categorize(entities, you):
    cats = {
        'ally': [],
        'enemy': []
    }
    for entity in entities:
        if entity.owner == you:
            cats['ally'].append(entity)
        else:
            cats['enemy'].append(entity)
    return cats

def simplify(planets, fleets):
    data = {}
    for planet in planets['ally']:
        data[planet.n] = [int(planet.production), -int(planet.ships)]
    for planet in planets['enemy']:
        data[planet.n] = [int(planet.production), int(planet.ships)]
    for fleet in fleets['ally']:
        data[fleet.target][1] -= fleet.ships
    for fleet in fleets['enemy']:
        data[fleet.target][1] += fleet.ships
    return data

def analyze(galaxy):
    planets = categorize(galaxy.planets.values(), galaxy.you)
    fleets = categorize(galaxy.fleets.values(), galaxy.you)
    return simplify(planets, fleets), planets, fleets

def act(data, planets, fleets):
    for source in planets['ally']:
        while data[source.n][1] < -HOLD_PROP * data[source.n][0] and source.ships > 0.0:
            target = max(planets['ally'] + planets['enemy'], key=lambda p:heuristic(p, source, data))
            prop = SEND_COUNT / source.ships
            send_ships(prop, source, target)
            data[source.n][1] += SEND_COUNT
            data[target.n][1] -= SEND_COUNT

def bot(galaxy):
    data = analyze(galaxy)
    act(*data)

if __name__ == '__main__':
    gbl.run(bot)

