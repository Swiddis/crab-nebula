import gbotlib as gbl

HOLD_PROP, COST_PROP = 0.20, 0.05

def bot(galaxy):
    if galaxy.state == 'play':
        planets = gbl.categorize(galaxy, 'planets')
        targets = sorted(planets['enemy'], key=lambda p: p.production / (p.ships + 1), reverse=True)
        for planet in planets['ally']:
            if 0 < (s := planet.ships):
                hold = HOLD_PROP * planet.production
                for target in targets:
                    cost = COST_PROP * target.production + target.ships
                    if s < hold + cost:
                        break
                    prop = cost / planet.ships
                    gbl.send(f'/SEND {round(100 * prop)} {planet.n} {target.n}')
                    s -= round(planet.ships * prop)

if __name__ == '__main__':
    gbl.run(bot)
