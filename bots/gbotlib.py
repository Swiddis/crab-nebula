import sys, os
import galcon_entities as gents

def send(msg):
    sys.stdout.write(msg+"\n")
    sys.stdout.flush()

def log(msg):
    sys.stderr.write(msg+"\n")
    sys.stderr.flush()

def update(galaxy, data):
    fields = data[0]
    updates = {}
    for i in range(1, len(data), len(fields)+1):
        updates[int(data[i])] = tuple(map(float, data[i+1:i+len(fields)+1]))
    for n, update in updates.items():
        entity = galaxy.get_by_id(n)
        for field,value in zip(fields, update):
            if field == 'x': entity.x = value
            elif field == 'y': entity.y = value
            elif field == 's': entity.ships = value
            elif field == 'r': entity.radius = value
            elif field == 'o': entity.owner = int(value)
            elif field == 't': entity.target = int(value)

def tick(galaxy, line, bot):
    bot(galaxy)
    send('/TOCK')

def print(galaxy, line, bot):
    log('\t'.join(line[1:]))

def results(galaxy, line, bot):
    log('Result: ' + '\t'.join(line[1:]))

def reset_galaxy(galaxy, line, bot):
    galaxy.reset()

def init_user(galaxy, line, bot):
    user = gents.User(
        int(line[1]), 
        line[2], 
        int(line[3], 16), 
        int(line[4])
    )
    galaxy.users[user.n] = user

def init_planet(galaxy, line, bot):
    planet = gents.Planet(
        int(line[1]),
        int(line[2]), 
        float(line[3]), 
        float(line[4]), 
        float(line[5]), 
        float(line[6]), 
        float(line[7])
    )
    galaxy.planets[planet.n] = planet

def init_fleet(galaxy, line, bot):
    fleet = gents.Fleet(
        int(line[1]),
        int(line[2]),
        float(line[3]),
        float(line[4]),
        float(line[5]),
        int(line[6]),
        int(line[7]),
        float(line[8])
    )
    galaxy.fleets[fleet.n] = fleet

def destroy_entity(galaxy, line, bot):
    galaxy.del_by_id(int(line[1]))

def set_galaxy(galaxy, line, bot):
    if line[1] == 'you':
        galaxy.you = int(line[2])
    elif line[1] == 'state':
        galaxy.state = line[2]

def err(galaxy, line, bot):
    log('Error: ' + '\t'.join(line[1:]))

COMMANDS = {
    '/tick': tick,
    '/print': print,
    '/results': results,
    '/reset': reset_galaxy,
    '/set': set_galaxy,
    '/user': init_user,
    '/planet': init_planet,
    '/fleet': init_fleet,
    '/destroy': destroy_entity,
    '/error': err
}

def parse(galaxy, line, bot):
    line = line.lower().split('\t')
    if line[0][0] != '/':
        update(galaxy, line)
    elif line[0] in COMMANDS:
        COMMANDS[line[0]](galaxy, line, bot)
    else:
        log('Invalid Command: ' + '\t'.join(line))

def run(bot):
    galaxy = gents.Galaxy()
    while True:
        try:
            line = sys.stdin.readline()
        except:
            break
        if not line:
            break
        line = line.rstrip()
        if len(line) == 0:
            continue
        parse(galaxy, line, bot)

# Extra helper commands that are commonly used in bots
def categorize(galaxy, type, sep_neutral = False):
    entities = galaxy.planets.values() if type == 'planets' else galaxy.fleets.values()
    sep_neutral = False if type == 'fleets' else sep_neutral
    
    categorized = {'ally': [], 'enemy': []}
    if sep_neutral: categorized['neutral'] = []
    for entity in entities:
        if entity.owner == galaxy.you:
            categorized['ally'].append(entity)
        elif sep_neutral and entity.is_neutral(galaxy.users):
            categorized['neutral'].append(entity)
        else:
            categorized['enemy'].append(entity)
    return categorized

def send_ships(proportion, source, destination):
    send(f'/SEND {round(100 * proportion)} {source.n} {destination.n}')

def redir_fleet(fleet, destination):
    send(f'/REDIR {fleet.n} {destination.n}')
