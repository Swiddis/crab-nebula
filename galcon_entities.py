class User:
    def __init__(self, n, name, color, team):
        self.n = n
        self.name = name
        self.color = color
        self.team = team

class Planet:
    def __init__(self, n, owner, ships, x, y, production, radius):
        self.n = n
        self.owner = owner
        self.ships = ships
        self.x = x
        self.y = y
        self.production = production
        self.radius = radius
    
    def distance(self, entity):
        return max(((self.x - entity.x) ** 2 + (self.y - entity.y) ** 2) - (self.radius + entity.radius), 0)
    
    def is_neutral(self, users):
        return users[self.owner].team == 0

class Fleet:
    def __init__(self, n, owner, ships, x, y, source, target, radius):
        self.n = n
        self.owner = owner
        self.ships = ships
        self.x = x
        self.y = y
        self.source = source
        self.target = target
        self.radius = radius
    
    def travel_time(self, distance):
        return distance / 40
    
    def distance(self, entity):
        return max(((self.x - entity.x) ** 2 + (self.y - entity.y) ** 2) - (self.radius + entity.radius), 0)

class Galaxy:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = ''
        self.you = 0
        self.users = {}
        self.planets = {}
        self.fleets = {}

    def get_by_id(self, n):
        if n in self.users:
            return self.users[n]
        elif n in self.planets:
            return self.planets[n]
        elif n in self.fleets:
            return self.fleets[n]
        else:
            return None

    def del_by_id(self, n):
        if n in self.users:
            return self.users.pop(n)
        elif n in self.planets:
            return self.planets.pop(n)
        elif n in self.fleets:
            return self.fleets.pop(n)
        else:
            return None
