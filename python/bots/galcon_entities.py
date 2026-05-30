from math import hypot


class User:
    n: int
    name: str
    color: str
    team: int

    def __init__(self, n, name, color, team):
        self.n = n
        self.name = name
        self.color = color
        self.team = team


class Planet:
    n: int
    owner: int
    ships: float
    x: float
    y: float
    production: float
    radius: float

    def __init__(self, n, owner, ships, x, y, production, radius):
        self.n = n
        self.owner = owner
        self.ships = ships
        self.x = x
        self.y = y
        self.production = production
        self.radius = radius

    def __str__(self) -> str:
        return (
            f"Planet(n={self.n} o={self.owner} s={round(self.ships)} "
            + f"x={round(self.x)} y={round(self.y)} "
            + f"p={round(self.production)} r={round(self.radius)})"
        )

    def distance(self, entity: Planet | Fleet):
        return hypot(self.x - entity.x, self.y - entity.y)

    def is_neutral(self, users):
        return users[self.owner].team == 0


class Fleet:
    n: int
    owner: int
    ships: float
    x: float
    y: float
    source: int
    target: int
    radius: float

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
        return max(
            ((self.x - entity.x) ** 2 + (self.y - entity.y) ** 2)
            - (self.radius + entity.radius),
            0,
        )


class Galaxy:
    users: dict[int, User]
    planets: dict[int, Planet]
    fleets: dict[int, Fleet]
    t: float
    state: str
    you: int
    frame: int

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = "INIT"
        self.you = 0
        self.t = 0.0
        self.frame = 0
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
