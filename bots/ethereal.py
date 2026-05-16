import gbotlib as gbl

SEND_PROP, DELTA_PROP, HOLD_PROP = 0.350, 0.600, 0.150

def send_ships(prop, s, d):
    gbl.send(f'/SEND {round(100 * prop)} {s.n} {d.n}')

def redirect(fleet, new_target):
    gbl.send(f'/REDIR {fleet.n} {new_target.n}')

def send_planets(planets):
    for planet in planets['ally']:
        ships, ti = planet.ships, 0
        while ships > HOLD_PROP * planet.production and ships > 0:
            t = planets['enemy'][ti % len(planets['enemy'])]
            prop = SEND_PROP if len(planets['ally']) > 1 else max(SEND_PROP, (t.ships + 1) / ships)
            send_ships(prop, planet, t)
            ships, ti = ships * DELTA_PROP, ti + 1

def redirect_fleets(fleets, planets):
    pdict = {p.n: p for p in planets['enemy'] + planets['ally']}
    for fleet in fleets:
        ft, ftdist = pdict[fleet.target], pdict[fleet.target].distance(fleet)
        ntlist = [nt for nt in planets['enemy'] if nt.distance(fleet) < ftdist]
        if len(ntlist) == 0:
            break
        nt = max(ntlist, key=lambda p: p.production / (p.ships + 1))
        if nt.production / (nt.ships + 1) > ft.production / (ft.ships + 1):
            redirect(fleet, nt)

def bot(galaxy):
    if galaxy.state == 'play':
        planets = gbl.categorize(galaxy, 'planets')
        if len(planets['enemy']) == 0: return
        fleets = gbl.categorize(galaxy, 'fleets')['ally']
        send_planets(planets)
        redirect_fleets(fleets, planets)

if __name__ == '__main__':
    gbl.run(bot)
